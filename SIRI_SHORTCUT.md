# Siri Shortcut – Hermes Brain Dump

## Überblick

Mit einem iOS Kurzbefehl (Shortcut) kannst du per Siri-Sprachbefehl Notizen, Aufgaben und Ideen direkt in Hermes Brain speichern – ohne die App zu öffnen.

## 1. Kurzbefehl installieren

Öffne diesen Link auf dem iPhone:

> **[Kurzbefehl installieren](https://www.icloud.com/shortcuts/...)**

(Da der Link dynamisch ist, folge stattdessen der Anleitung unter 2.)

## 2. Manuelle Einrichtung (5 Minuten)

### Schritt 1: Kurzbefehl öffnen

1. Öffne die **Kurzbefehle**-App auf dem iPhone
2. Tippe auf **+** (neuer Kurzbefehl)
3. Tippe auf **Kurzbefehl umbenennen** → nenne ihn **"Brain Dump"**
4. Tippe auf **App-Symbol auswählen** → wähle 🧠

### Schritt 2: Eingabe definieren

5. Tippe auf **+ Aktion hinzufügen**
6. Suche nach **"Texteingabe"** → wähle **"Texteingabe anfordern"**
7. Ändere die Frage zu: **"Was geht dir durch den Kopf?"**

### Schritt 3: Aktion hinzufügen

8. Tippe erneut auf **+**
9. Suche nach **"Inhalte abrufen"** → wähle **"Inhalte abrufen"**
10. Fülle die Felder aus:
    - **URL:** `https://representing-remedy-shape-obligations.trycloudflare.com/brain/api/dump`
    - **Methode:** `POST`
    - **Header hinzufügen:**
      - Key: `Content-Type` → Value: `application/json`
      - Key: `X-API-Key` → Value: `bk_cu4sg99-XafK_PncBqLeC_Vxtgd_QmVWZHh5b2IKUnQ`
    - **Anfragetext:** `{"text": "{{Eingabe}}", "source": "siri"}`

### Schritt 4: Ergebnis anzeigen

11. Tippe auf **+**
12. Suche nach **"QuickLook"** oder **"Ergebnis anzeigen"**
13. Wähle **"Schnellanzeige"** – so siehst du die Bestätigung

### Schritt 5: Zu Siri hinzufügen

14. Tippe oben rechts auf das **Info-Symbol (i)**
15. Aktiviere **"Zu Siri hinzufügen"**
16. Nimm den Satz auf: **"Brain dump [Text]"** oder **"Merken: [Text]"**

## 3. Nutzung

**Per Siri:**
- *"Hey Siri, Brain dump Meeting morgen um 10 Uhr"*
- *"Hey Siri, Merken: GitHub Token erneuern"*
- *"Hey Siri, Brain Dump"* → Siri fragt nach Text

**Per Kurzbefehl:**
- Vom Home-Bildschirm: Kurzbefehl-Widget tippen
- Aus der Kurzbefehle-App: "Brain Dump" antippen

## 4. Homescreen Shortcut (Web-App)

1. Safari öffnen → `https://representing-remedy-shape-obligations.trycloudflare.com/brain/` aufrufen
2. Login mit Passwort: `!!pS!!220252-`
3. Tippe auf **Teilen-Button** (unten Mitte)
4. Scrolle runter → **"Zum Home-Bildschirm"**
5. Name: **"Brain"** → **"Hinzufügen"**

Ab jetzt öffnest du die App wie eine native App vom Home-Bildschirm.

## Technischer Hintergrund

- **API-Endpoint:** `POST https://.../brain/api/dump`
- **Authentifizierung:** `X-API-Key` Header (oben)
- **Payload:** `{"text": "...", "source": "siri"}`
- **Antwort:** `{"status": "ok", "item": {...}}`
- **Auto-Klassifikation:** Termine, ToDos, Ideen, Privates, Business werden automatisch erkannt

## Trouble

- **"Nicht autorisiert"** → API-Key ist falsch. Schick mir eine Nachricht.
- **Tunnel tot** → Cloudflare-URL kann sich nach Neustart ändern. Schreib mir, ich geb dir die neue URL.
- **Alles rot/Error** → Schreib mir den Wortlaut der Fehlermeldung.
