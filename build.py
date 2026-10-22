#!/usr/bin/env python3
"""Erzeugt iCalendar-Abos (.ics) aus den TOML-Dateien in data/.

Jede Datei in data/ wird zu einem eigenen Kalender in docs/<name>.ics.
Getrennte Kalender lassen sich auf dem iPhone einzeln ein-/ausblenden und farbig markieren.
Nur Standardbibliothek (Python >= 3.11), keine Abhaengigkeiten.
"""
from __future__ import annotations

import hashlib
import sys
import tomllib
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "docs"
PRODID = "-//Edwin Bergen//kalender-abo//DE"

VTIMEZONE_BERLIN = """BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def fold(line: str) -> str:
    """RFC 5545: Zeilen > 75 Oktette falten."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, chunk = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(chunk) + len(b) > (75 if not parts else 74):
            parts.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += b
    parts.append(chunk.decode("utf-8"))
    return "\r\n ".join(parts)


def uid(*parts: str) -> str:
    """Stabile UID: gleicher Termin = gleiche UID, damit das iPhone aktualisiert statt doppelt."""
    h = hashlib.sha1("|".join(parts).encode()).hexdigest()[:20]
    return f"{h}@kalender-abo"


def build_event(cal: dict, ev: dict, stamp: str) -> list[str]:
    title = ev["titel"]
    lines = ["BEGIN:VEVENT"]
    d = ev["datum"]
    if isinstance(d, datetime):
        d = d.date()
    if "zeit" in ev:  # Termin mit Uhrzeit
        hh, mm = map(int, str(ev["zeit"]).split(":"))
        start = datetime(d.year, d.month, d.day, hh, mm)
        dauer = int(ev.get("dauer_min", cal.get("dauer_min", 60)))
        end = start + timedelta(minutes=dauer)
        lines += [f"DTSTART;TZID=Europe/Berlin:{start:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Europe/Berlin:{end:%Y%m%dT%H%M%S}"]
        key = f"{d.isoformat()}T{hh:02d}{mm:02d}"
    else:  # ganztaegig
        lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                  "TRANSP:TRANSPARENT"]
        key = d.isoformat()
    lines += [f"UID:{uid(cal['name'], key, ev.get('ort', ''), title)}",
              f"DTSTAMP:{stamp}",
              f"SUMMARY:{esc(title)}"]
    if ev.get("ort"):
        lines.append(f"LOCATION:{esc(ev['ort'])}")
    if ev.get("notiz"):
        lines.append(f"DESCRIPTION:{esc(ev['notiz'])}")
    # Erinnerung: Minuten vor Beginn (ganztaegig: vor 00:00 des Tages)
    erinnerung = ev.get("erinnerung_min", cal.get("erinnerung_min"))
    if erinnerung is not None:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(title)}",
                  f"TRIGGER:-PT{int(erinnerung)}M", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def fetch_external(url: str) -> list[str]:
    """VEVENT-Bloecke aus einer externen .ics uebernehmen (z. B. Export des Kreises)."""
    with urllib.request.urlopen(url, timeout=30) as r:
        text = r.read().decode("utf-8", errors="replace")
    text = text.replace("\r\n ", "").replace("\r\n\t", "").replace("\n ", "")
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("BEGIN:VEVENT"):
            inside = True
        if inside:
            out.append(line)
        if line.startswith("END:VEVENT"):
            inside = False
    return out


def build_calendar(src: Path) -> tuple[str, int]:
    cal = tomllib.loads(src.read_text(encoding="utf-8"))
    cal.setdefault("name", src.stem)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    body: list[str] = []
    events = list(cal.get("termin", []))
    # Kompakte Form: eine Serie mit gemeinsamem Titel und Liste von Daten
    for serie in cal.get("serie", []):
        extra = {k: v for k, v in serie.items() if k != "daten"}
        events += [{**extra, "datum": d} for d in serie["daten"]]
    for ev in sorted(events, key=lambda e: (str(e["datum"]), str(e.get("zeit", "")))):
        body += build_event(cal, ev, stamp)
    count = len(events)
    if cal.get("quelle_ics"):
        ext = fetch_external(cal["quelle_ics"])
        body += ext
        count += sum(1 for l in ext if l.startswith("BEGIN:VEVENT"))
    head = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
            f"X-WR-CALNAME:{esc(cal.get('titel', cal['name']))}",
            "X-WR-TIMEZONE:Europe/Berlin",
            "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    if cal.get("farbe"):
        head.append(f"X-APPLE-CALENDAR-COLOR:{cal['farbe']}")
    lines = head + VTIMEZONE_BERLIN.splitlines() + body + ["END:VCALENDAR"]
    return "\r\n".join(fold(l) for l in lines) + "\r\n", count


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for src in sorted(DATA.glob("*.toml")):
        ics, n = build_calendar(src)
        (OUT / f"{src.stem}.ics").write_text(ics, encoding="utf-8", newline="")
        print(f"{src.stem}.ics: {n} Termine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
