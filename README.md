# 📢 Universal Notifier (Advanced)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/jumping2000/universal_notifier)](https://github.com/jumping2000/universal_notifier/releases)

**Universal Notifier** è un componente custom per Home Assistant che centralizza e potenzia la gestione delle notifiche.

Trasforma semplici automazioni in un sistema di comunicazione "Smart Home" che conosce l'ora del giorno, rispetta il tuo sonno (DND), saluta in modo naturale e gestisce automaticamente il volume degli assistenti vocali.

## ✨ Caratteristiche Principali

* **Piattaforma Unificata:** Un solo servizio (`universal_notifier.send`) per Telegram, App Mobile, Alexa, Google Home, ecc.
* **Voce vs Testo:** Distingue automaticamente tra messaggi da leggere (con prefissi `[Jarvis - 12:30]`) e messaggi da pronunciare (solo testo pulito).
* **Time Slots & Volume Smart:** Imposta volumi diversi per Mattina, Pomeriggio, Sera e Notte. Il componente regola il volume *prima* di parlare.
* **Do Not Disturb (DND):** Definisci un orario di silenzio per gli assistenti vocali. Le notifiche critiche (`priority: true`) passano comunque.
* **Saluti Casuali:** "Buongiorno", "Buon pomeriggio", ecc., scelti casualmente da liste personalizzabili.
* **Gestione Comandi:** Supporto nativo per comandi Companion App (es. `TTS`, `command_volume_level`) inviati in modalità "RAW".

## 🚀 Installazione

### Tramite HACS (Consigliato)
1.  Aggiungi questo repository come **Custom Repository** in HACS (Tipo: *Integration*).
2.  Cerca "Universal Notifier" e installa.
3.  Riavvia Home Assistant.

### Manuale
1.  Copia la cartella `universal_notifier` dentro `/config/custom_components/`.
2.  Riavvia Home Assistant.

## ⚙️ Configurazione (`configuration.yaml`)

```yaml
universal_notifier:
  assistant_name: "Jarvis"       # Nome visualizzato nei messaggi di testo
  date_format: "%H:%M"           # Formato orario
  include_time: true             # Includere l'orario nei messaggi di testo?

  # --- FASCE ORARIE E VOLUMI ---
  # Definisci quando inizia una fascia e il volume per gli assistenti vocali (0.0 - 1.0)
  time_slots:
    morning:
      start: "06:30"
      volume: 0.35
    afternoon:
      start: "12:00"
      volume: 0.60
    evening:
      start: "19:00"
      volume: 0.45
    night:
      start: "23:30"
      volume: 0.15

  # --- DO NOT DISTURB (DND) ---
  # In questo orario, i canali 'is_voice: true' vengono ignorati (salvo priority: true)
  dnd:
    start: "00:00"
    end: "06:30"

  # --- SALUTI PERSONALIZZATI (Opzionale) ---
  greetings:
    morning:
      - "Buongiorno signore"
      - "Ben svegliato"
    night:
      - "Buonanotte"
      - "Shh, è tardi"

  # --- CANALI (Alias) ---
  channels:
    # Esempio TELEGRAM (Testo)
    telegram_admin:
      service: telegram_bot.send_message
      target: 123456789
      is_voice: false

    # Esempio ALEXA (Voce)
    alexa_sala:
      service: notify.alexa_media_echo_sala
      service_data:
        type: tts
      # Necessario per regolare il volume automaticamente
      entity_id: media_player.echo_sala
      is_voice: true

    # Esempio GOOGLE (Voce)
    google_cucina:
      service: tts.google_translate_say
      entity_id: media_player.nest_hub_cucina
      is_voice: true
      
    # Esempio MOBILE APP
    my_phone:
      service: notify.mobile_app_iphone_di_marco
