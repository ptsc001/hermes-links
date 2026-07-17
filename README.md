# Hermes Links

Glassmorphism Link Dashboard – Speichere und verwalte Links mit Notizen, Tags und Kategorien.

## Features

- Dashboard mit Glas-Effekt Design & Aurora-Hintergrund
- Links speichern mit Titel, Notiz, Tags & Kategorien
- Gelesen/Favorit markieren
- Volltext-Suche & Filter
- iPhone-kompatibel (wird von iOS Shortcuts angesteuert)
- REST API für externe Integration

## Schnellstart (Lokal)

```bash
pip install -r requirements.txt
python main.py
```

App unter http://127.0.0.1:8877/links — API Key steht im Terminal beim Start.

## API

Alle Endpunkte unter `/links/api/` — API Key via `X-API-Key` Header.

- `POST /links/api/links` — Neuen Link anlegen
- `GET /links/api/links` — Links auflisten (mit Filter/Suche/Sortierung)
- `GET /links/api/links/{id}` — Einzelnen Link abrufen
- `PATCH /links/api/links/{id}` — Link aktualisieren
- `DELETE /links/api/links/{id}` — Link löschen
- `GET /links/api/stats` — Statistiken

## Deploy

### Render (empfohlen)

1. Forke dieses Repo
2. Auf [Render.com](https://render.com) → **New Web Service** → Repo verbinden
3. Render erkennt `render.yaml` automatisch
4. Fertig – HTTPS + eigenes Domain möglich
