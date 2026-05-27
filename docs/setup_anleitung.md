# Setup-Anleitung – EGD Projekt

## Schritt-für-Schritt-Installation (Windows / VS Code)

### 1. Voraussetzungen

- Python 3.10 oder neuer: https://www.python.org/downloads/
- VS Code: https://code.visualstudio.com/
- VS Code Extension: **Python** + **Jupyter** (im Extensions-Menü installieren)
- Git: https://git-scm.com/

### 2. Terminal öffnen & in Projektordner navigieren

```powershell
cd C:\Visual_Studio\EGD
```

### 3. Virtuelle Umgebung anlegen

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Falls Berechtigungsfehler:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Pakete installieren

```powershell
pip install -r requirements.txt
```

> ⚠️ Hinweis: `geopandas` auf Windows benötigt ggf. zusätzliche DLLs.
> Falls Fehler: `pip install geopandas --only-binary :all:`

### 5. Notebook in VS Code öffnen

1. VS Code öffnen: `code .`
2. Datei öffnen: `notebooks/standortanalyse_fitnesscenter_zuerich.ipynb`
3. Kernel wählen: Oben rechts → `.venv (Python 3.x)`
4. **Run All** (▶▶) — oder einzelne Zellen mit Shift+Enter

### 6. Erster Durchlauf (Datenbeschaffung)

Beim ersten Ausführen werden automatisch heruntergeladen:
- Stadtgrenze Zürich (OSM) ~1 MB
- Fitnesscenter (OSM) ~50 KB
- ÖV-Haltestellen (OSM) ~500 KB
- Strassennetzwerk für Isochronen (OSM) ~30 MB — **dauert 2–5 Min.**
- Statistische Quartiere (Stadt Zürich OGD WFS)
- Bevölkerungsdaten (Stadt Zürich OGD CSV)

Alle Daten werden gecacht unter `data/processed/` — spätere Läufe dauern < 1 Min.

### 7. Outputs ansehen

- **Statische Karten**: `outputs/maps/*.png` → im Explorer öffnen
- **Interaktive Karte**: `outputs/maps/interactive_map.html` → im Browser öffnen

---

## Mögliche Probleme & Lösungen

| Problem | Lösung |
|---------|--------|
| `ModuleNotFoundError: geopandas` | `pip install geopandas --only-binary :all:` |
| `ModuleNotFoundError: libpysal` | `pip install libpysal esda` |
| `osmnx` timeout beim Netzwerk-Download | Erneut ausführen — Cache greift ab 2. Versuch |
| WFS-Fehler (Quartiere) | Automatischer Fallback auf OSM-Daten |
| Kernel nicht gefunden | VS Code → Command Palette → `Python: Select Interpreter` → `.venv` wählen |

---

## GitHub Repository vorbereiten

```powershell
cd C:\Visual_Studio\EGD
git init
git add .
git commit -m "Initial commit: Standortanalyse Fitnesscenter Zürich"
git remote add origin <deine-github-url>
git push -u origin main
```

> ⚠️ Rohdaten (`data/raw/`, `data/processed/`) sind im `.gitignore` — müssen nicht
> committed werden, da sie beim Ausführen automatisch neu generiert werden.
