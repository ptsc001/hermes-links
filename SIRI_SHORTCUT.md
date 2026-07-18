# Siri Shortcut – Brain Dump in < 5 Sekunden

## Was du brauchst
- iOS 16+ (Shortcuts App)
- Die URL und den API-Key aus dem Dashboard

## Schritt-für-Schritt

### 1. Shortcuts App öffnen
Auf deinem iPhone: **Shortcuts** → **+** (neuer Shortcut)

### 2. Auslöser setzen
- Tippe auf **"App oder Aktion suchen"** → suche **"Siri"** → wähle **"In Siri fragen"**
- Gib einen Satz ein wie: **"Brain Dump"** oder **"Merken"**
- (Alternativ: **"App oder Aktion suchen"** → suche **"Apple Watch"** → wähle **"Auf der Apple Watch zeigen"** – dann via Watch auslösbar)

### 3. Text erfassen
- Tippe auf **+** unter dem Trigger → suche **"Text anfragen"** → wähle **"Eingabe anfordern"**
- Frage: **"Was soll ich mir merken?"**
- Standard-Text: *(leer lassen)*

### 4. API-Aufruf
- Tippe auf **+** → suche **"Inhalt der URL"** → wähle **"URL-Inhalt abrufen"**
  - **Methode:** POST
  - **URL:** `https://highlighted-vancouver-shakespeare-admission.trycloudflare.com/brain/api/dump`
  - **Headers:**
    - Key: `X-API-Key` → Text: `bk_svrz-X9hrybfdLdGluleOA3NuL2RLrAX`
    - Key: `Content-Type` → Text: `application/json`
  - **Request-Body:** JSON → `{"text": "`**Eingabe (Magische Variable aus Schritt 3 einfügen)**`", "source": "siri"}`

  **Wichtig:** Um die Eingabe einzufügen: tippe lange auf den Body → **"Magische Variable auswählen"** → wähle **"Text anfragen"**

### 5. Bestätigung (optional)
- Tippe auf **+** → suche **"Text"** → wähle **"Text"**
  - Gib ein: **"✅ Gespeichert: **"** und hänge die **Eingabe** dahinter
- Tippe auf **+** → suche **"Sprechen"** → wähle **"Text vorlesen"**

### 6. Shortcut benennen
- Tippe oben auf den Namen → **"Brain Dump"**

## Nutzung

### Per Siri:
**"Hey Siri, Brain Dump"** – Siri fragt "Was soll ich mir merken?" – du sprichst deinen Text – fertig.

### Per Apple Watch:
Wenn du Schritt 2b gemacht hast: Shortcut erscheint auf der Watch → antippen → dikrieren → speichern.

### Per Control Center (optional):
Shortcuts App → Shortcut → **"Zu Home-Bildschirm"** → als App-Icon ablegen.

---

## Test
Nach dem Einrichten: Einfach **"Hey Siri, Brain Dump – Meeting mit Müller um 15 Uhr"** – der Eintrag landet in der Datenbank und ich sehe ihn sofort.

## Was passiert danach?
- Der Cron-Job (7:30 Uhr) verarbeitet alle unprocessed Items
- Termine → Kalender, Todos → Erinnerungen
- Wenn du was dringendes hast: schreib mir einfach hier – ich seh die neuen Einträge in der DB live
