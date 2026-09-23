# Tinkellect AI Radar

Wöchentlicher KI-Modell-Radar (Benchmarks, Use Cases, n8n-Relevanz) als E-Mail im Tinkellect-Branding – erzeugt von einer Claude-Code-**Cloud-Routine**. Der Inhalt entsteht jede Woche neu (Recherche), Layout und Charts kommen deterministisch aus den Skripten in diesem Repo.

## Warum die Routine bisher nicht lief

Der Lauf vom 23.09.2026 ist in der Cloud gestartet (`/home/user`), aber der Routine war **kein Repository angehängt** – und dieses Repo existierte noch nicht. Cloud-Routinen kennen keinen lokalen Ordner; sie klonen bei jedem Lauf die angehängten GitHub-Repos.

## Einrichten (einmalig, ca. 15 Minuten)

1. **Repo anlegen:** auf GitHub ein Repo `airadar` unter `tamertinkcidev` erstellen – **öffentlich** (Gmail lädt die Chart-Bilder per Raw-URL; private Repos gehen nicht). Inhalt dieses Ordners pushen:
   ```bash
   git init -b main && git add . && git commit -m "Tinkellect AI Radar: Grundgerüst"
   git remote add origin git@github.com:tamertinkcidev/airadar.git && git push -u origin main
   ```
   Anderer Repo-Name oder Account? Dann `assets_base_url` in `config.json` und die Repo-Zeile im Routine-Prompt anpassen.
2. **Routine bearbeiten:** claude.ai/code/routines → `weekly-ai-newsletter` → Menü → **Edit**:
   - **Repositories:** `tamertinkcidev/airadar` hinzufügen.
   - **Instructions:** kompletten Inhalt von `ROUTINE-PROMPT.md` einfügen (ersetzt den alten Text; der Empfänger steht in der Zeile `EMPFÄNGER:`).
   - **Connectors:** Gmail muss enthalten sein; Google-Drive, Google-Calendar, Claude-Docs, visualize können raus.
   - **Environment:** Default (Trusted) reicht – Netzwerk für pip/GitHub ist erlaubt, Gmail läuft über den Connector.
   - **Model:** ist aktuell nicht gesetzt (Default). Bei Bedarf Opus wählen.
   - **Schedule:** steht auf Sonntag 13:00 UTC = 15:00 Berlin (Sommerzeit). Ggf. anpassen.
3. **Run now** klicken. Der erste Lauf ist die **Baseline** (Roster und Werte werden komplett aufgebaut, kein Delta-Chart). Dauer 10–20 Minuten. Danach im Postfach prüfen: Bilder sichtbar? Betreff korrekt? Im Run-Log: beide Pushes auf `main` erfolgreich?

## Branding anpassen

`brand.json` ist die einzige Stelle: Farben (`header_bg`, `accent`, …), `logo_url` (öffentliche PNG-URL, z. B. `https://raw.githubusercontent.com/tamertinkcidev/airadar/main/assets/logo.png`), Display-Font für die Charts (`assets/fonts/BrunoAce-Regular.ttf` ablegen – Bruno Ace ist unter der SIL Open Font License frei nutzbar). Web-Fonts und Glassmorphism funktionieren in Mail-Clients nicht; die Mail nutzt deshalb dunklen Header + hellen Textkörper mit System-Schriften.

## Dateien

| Datei | Zweck |
|---|---|
| `CLAUDE.md` | Redaktions-Spezifikation (Regeln, Roster, Benchmarks, Aufbau, Ablauf) – liest die Routine bei jedem Lauf |
| `ROUTINE-PROMPT.md` | Der Text für das Feld „Instructions" der Routine |
| `brand.json`, `config.json` | Branding · Asset-URL, Footer, Limits |
| `bootstrap.sh`, `requirements.txt` | Installiert matplotlib, legt Ordner an |
| `charts.py` | `charts.json` → PNGs (hbar / delta / scatter) |
| `diff_benchmarks.py` | Wochendeltas gegen den letzten Snapshot |
| `build_newsletter.py` | `content.json` + Charts → `newsletter.html`, `newsletter.txt`, `preview.html`, `meta.json` (validiert Pflichtfelder, Quellen, Größe) |
| `verify_urls.py` | Prüft nach dem Push, ob die Bilder öffentlich erreichbar sind |
| `send_mail.py` | Nur für lokale Läufe: SMTP-Versand mit Inline-Bildern (`.env`) |
| `data/models.json`, `data/benchmarks.json`, `data/history/` | Zustand – Roster, Benchmark-Registry, Snapshots |
| `charts/DATUM/` | Veröffentlichte Chart-PNGs (URLs bleiben dauerhaft gültig) |
| `archive/DATUM/`, `archive/LOG.md` | Versendete Ausgaben und Versand-Log |
| `examples/` | Formatbeispiele für `charts.json` und `content.json` (Werte erfunden) |
| `.claude/settings.json` | Berechtigungen für den lokalen Fallback |

## Lokal testen

```bash
bash bootstrap.sh
python3 charts.py --spec examples/charts.example.json --out charts/2026-09-27
python3 build_newsletter.py --content examples/content.example.json --charts charts/2026-09-27 --out out/2026-09-27
open out/2026-09-27/preview.html            # Windows: start out\2026-09-27\preview.html
python3 send_mail.py --meta out/2026-09-27/meta.json --dry-run   # erzeugt newsletter.eml, sendet nichts
```

## Alternative: lokale Desktop-Routine

Läuft nur bei offener Desktop-App und wachem PC, braucht `.env` mit Gmail-App-Passwort für `send_mail.py` und Freigaben per „Immer erlauben" beim ersten Lauf (Bash, WebSearch, WebFetch). Ablauf in `CLAUDE.md`, Abschnitt 11. Vorteil: Repo darf privat bleiben (Bilder gehen als Inline-Anhang).

## Spätere Ausbaustufen

- Verteiler (Makler, Interessenten) über n8n statt Gmail: `newsletter.html` per Webhook an `n8n.tinkellect.de` übergeben – dafür in der Routine-Umgebung die Domain freischalten. Achtung §7 UWG: auch im B2B nur mit vorheriger Einwilligung.
- Web-Version: GitHub Pages für `archive/` aktivieren und `web_base_url` in `config.json` setzen – die Mail bekommt dann automatisch einen „Web-Version"-Link.
