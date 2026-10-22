# Kalender-Abo

Zwei abonnierbare Kalender fürs iPhone, gebaut aus `data/*.toml`:

| Kalender | Datei | Abo-Link |
|---|---|---|
| Müllabfuhr | `data/muell.toml` | `webcal://<USER>.github.io/kalender-abo/muell.ics` |
| Gottesdienste | `data/gottesdienste.toml` | `webcal://<USER>.github.io/kalender-abo/gottesdienste.ics` |

## Ablauf
1. Termine in `data/*.toml` eintragen und committen.
2. Die GitHub-Action führt `build.py` aus und schreibt `docs/*.ics`.
3. GitHub Pages veröffentlicht `docs/`, und das iPhone ruft die Kalender alle paar Stunden ab.

Außerdem läuft die Action täglich, damit eine externe Quelle (`quelle_ics`) aktuell bleibt.

## Einmalige Einrichtung
- Repo `kalender-abo` anlegen (öffentlich, sonst geht Pages im Free-Plan nicht).
- Settings → Pages → Source: *Deploy from a branch*, Branch `main`, Ordner `/docs`.
- Settings → Actions → General → Workflow permissions: *Read and write*.

## iPhone
Einstellungen → Apps → Kalender → Accounts → Account hinzufügen → Andere → *Kalenderabo hinzufügen* → Link einfügen.

## Lokal bauen
```
python3 build.py
```
