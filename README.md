# 📢 Universal Notifier

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jumping2000/universal_notifier?style=for-the-badge) 
![GitHub Release Date](https://img.shields.io/github/release-date/jumping2000/universal_notifier?style=for-the-badge)
<!---
[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://https://github.com/jumping2000/universal_notifier/graphs/commit-activity?style=for-the-badge)
[![GitHub issues](https://img.shields.io/github/issues/jumping2000/universal_notifier)](https://github.com/jumping2000/universal_notifier/issues?style=for-the-badge)<br>
--->
[![Buy me a coffee](https://cdn.buymeacoffee.com/buttons/bmc-new-btn-logo.svg)](https://www.buymeacoffee.com/jumping)<span style="margin-left:15px;font-size:38px !important;"><b>Buy me a coffee and give me a star ✨!</b></span></a>
<a href="https://www.buymeacoffee.com/jumping"><img src="https://cdn.buymeacoffee.com/buttons/default-yellow.png" height="20">

___

**Universal Notifier** è un componente custom per Home Assistant che centralizza e potenzia la gestione delle notifiche.

Trasforma semplici automazioni in un sistema di comunicazione "Smart Home" che conosce l'ora del giorno, rispetta il tuo sonno (DND), saluta in modo naturale e gestisce automaticamente il volume degli assistenti vocali.

## ✨ Caratteristiche Principali

* **Piattaforma Unificata:** Un solo servizio (`universal_notifier.send`) per Telegram, App Mobile, Alexa, Google Home, ecc.
* **Voce vs Testo:** Distingue automaticamente tra messaggi da leggere (con prefissi `[Jarvis - 12:30]`) e messaggi da pronunciare (solo testo pulito).
* **Time Slots & Volume Smart:** Imposta volumi diversi per Mattina, Pomeriggio, Sera e Notte. Il componente regola il volume *prima* di parlare.
* **Do Not Disturb (DND):** Definisci un orario di silenzio per gli assistenti vocali. Le notifiche critiche (`priority: true`) passano comunque.
* **Saluti Casuali:** "Buongiorno", "Buon pomeriggio", ecc., scelti casualmente da liste personalizzabili.
* **Gestione Comandi:** Supporto nativo per comandi Companion App (es. `TTS`, `command_volume_level`) inviati in modalità "RAW".

___

**Universal Notifier** is a custom Home Assistant component that centralizes and enhances notification management.

It transforms simple automations into a "Smart Home" communication system that knows the time of day, respects your sleep (Do Not Disturb - DND), greets naturally, and automatically manages the volume of voice assistants.

## ✨ Key Features

* **Unified Platform:** A single service (`universal_notifier.send`) for Telegram, Mobile App, Alexa, Google Home, etc.
* **Voice vs. Text:** Automatically differentiates between messages to be read (with prefixes like `[Jarvis - 12:30]`) and messages to be spoken (clean text only).
* **Smart Time Slots & Volume:** Set different volumes for Morning, Afternoon, Evening, and Night. The component adjusts the volume *before* speaking.
* **Do Not Disturb (DND):** Define quiet hours for voice assistants. Critical notifications (`priority: true`) will still go through.
* **Random Greetings:** "Good morning," "Good afternoon," etc., chosen randomly from customizable lists.
* **Command Handling:** Native support for Companion App commands (e.g., `TTS`, `command_volume_level`) sent in "RAW" mode.

## 🚀 Installation
<details>
  <summary>Click me</summary>

### Via HACS (Recommended)
1.  Add this repository as a **Custom Repository** in HACS (Category: *Integration*).
2.  Search for "Universal Notifier" and install it.
3.  Restart Home Assistant.

### Manual Installation
1.  Copy the `universal_notifier` folder into your `/config/custom_components/` directory.
2.  Restart Home Assistant.

</details>

## 🔗 Prerequisites
<details>
  <summary>Click me</summary>

Before configuring Universal Notifier, ensure you have installed and set up the underlying notification integrations you plan to use:
* **Google Home / TTS**: Install the Google Translate [Text-to-Speech (TTS)](https://www.home-assistant.io/integrations/tts) integration to enable voice announcements on Google Assistant devices.
* **Alexa / Echo Devices**: Install the [Alexa Media Player Custom Component](https://github.com/alandtse/alexa_media_player) (via HACS) to allow Home Assistant to send announcements and set volume on Echo devices.
* **Telegram**: Configure and install the [Telegram Bot](https://www.home-assistant.io/integrations/telegram_bot/) integration to send visual messages.
* **Mobile App**: Ensure the [Mobile App integration](https://companion.home-assistant.io/) is active and configured for your devices (this is usually set up automatically when you log in via the app).

This component acts as a "router"; it must have the target services available to function correctly.
</details>

## ⚙️ Configuration (`configuration.yaml`)
<details>
  <summary>Click me</summary>

Time slots default value:
|Time Slot|Start|Volume|
|:---|:---|:---|
|morning|07:00|0.35|
|afternoon|12:00|0.4|
|evening|19:00|0.3|
|night|022:00|0.1|

Do Not Disturb default value:
|Service|Start|End|
|:---|:---|:---|
|DND|23:00|06.00|

#### Base Configuration (it uses default values for time slots and DND)

```yaml
universal_notifier:
  # --- CHANNELS (Aliases) ---
  channels:
    # Example ALEXA (Voice - Requires entity_id for volume control)
    alexa_living_room:
      service: notify.alexa_media_echo_dot
      target: media_player.echo_dot
      is_voice: true

    # Example GH (Voice - Requires entity_id for volume control)
    gh_kitchen:
      service: tts.speak
      target: tts.google_translate_it_it
      service_data:
        media_player_entity_id: media_player.kitchen
      is_voice: true

    # Example TELEGRAM
    telegram_admin:
      service: telegram_bot.send_message
      target: 123456789
      alt_services:
        photo:
          service: telegram_bot.send_photo
        video:
          service: telegram_bot.send_video
      
    # Example MOBILE APP
    my_android:
      service: notify.mobile_app_samsungs21

    # Example PERSISTENT NOTIFICATION
    ha_notification:
      service: persistent_notification.create

```

#### Complete Configuration and Time Slots

This is where you define the time slots, the default volume for voice devices within each slot, and DND hours.

```yaml
universal_notifier:
  assistant_name: "Jarvis"       # Name displayed in text messages
  date_format: "%H:%M"           # Time format
  include_time: true             # Include the time in text message prefixes?

  # --- TIME SLOTS AND VOLUMES ---
  # Defines when a slot starts and the default volume for voice assistants (0.0 - 1.0)
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
  # Voice channels ('is_voice: true') are skipped during this time (unless priority: true)
  dnd:
    start: "00:00"
    end: "06:30"
    
  # --- CUSTOM GREETINGS (Optional) ---
  greetings:
    morning:
      - "Good morning sir"
      - "Welcome back"
    night:
      - "Good night"
      - "Shh, it's late"

  # --- CHANNELS (Aliases) ---
  channels:
    # Example ALEXA (Voice - Requires entity_id for volume control)
    alexa_living_room:
      service: notify.alexa_media_echo_dot
      target: media_player.echo_dot
      is_voice: true

    # Example TELEGRAM (Text)
    telegram_admin:
      service: telegram_bot.send_message
      target: 123456789
      is_voice: false
      
    # Example MOBILE APP
    my_android:
      service: notify.mobile_app_samsungs21
```

</details>

## 🎯 Service Field Reference
<details>
  <summary>Click me</summary>

|Field|Type | Required |Description |
|:---|:---|:---|:---|
|message|string|Yes|The main text of the notification.|
|targets|list|Yes|List of channel aliases defined in configuration.yaml.|
|title|string|No|Notification| title (supported by Notify and Mobile App).|
|data|dict|No|Generic extra data applied to ALL underlying services.|
|target_data|dict|No|Dictionary {target_alias: {specific_data}} for targeted overrides.|
|priority|bool|No|If true, bypasses DND and sets high volume (default 0.9).|
|skip_greeting|bool|No|If true, does not add the time-based greeting (e.g., Good Morning).|
|include_time|bool|No|Overrides the configuration to include/exclude the time in the visual prefix.|
|assistant_name|string|No|Overrides the global assistant name.|
|override_greetings|dict|No|Overrides the default greetings for this single call.|

</details>

## 📝 Usage Examples
<details>
  <summary>Click me</summary>

#### 1. Standard Notification (Automatic Volume)
If sent at 3:00 PM, it will use the afternoon volume (0.60). If sent at 2:00 AM (DND is active), Alexa will be skipped, but Telegram will receive the message.

```yaml
action: universal_notifier.send
data:
  message: "The laundry is finished."
  targets:
    - alexa_living_room
    - telegram_admin
```

#### 2. Priority Notification (Bypasses DND and sets Volume to 90%)
Use the priority flag for critical alerts.

```yaml
action: universal_notifier.send
data:
  title: "CRITICAL ALERT"
  message: "Water leak detected, valve closed!"
  priority: true        # <--- FORCES SENDING AND MAX VOLUME (0.9)
  skip_greeting: true   # <--- Avoids greetings like "Good night" during an alarm
  targets:
    - alexa_living_room
    - telegram_bot_media
    - gh_kitchen
```

#### 3. Companion App Commands (Raw Messages)
If the message is a recognized command (like "TTS") or starts with *command_*, greetings and prefixes are automatically stripped.

```yaml
action: universal_notifier.send
data:
  message: "TTS" # The component sends "TTS" RAW, without prefixes.
  targets:
    - my_android
  target_data:
    my_android:
      tts_text: "The postman is at the door."
      media_stream: alarm_stream_max
      clickAction: /lovelace/main
```

#### 4. Multi target
How to send to multiple targets.

```yaml
action: universal_notifier.send
data:
  priority: true
  message: "Something happened at home!"
  targets: 
    - my_phone
    - telegram_first
    - alexa_living_room
    - gh_kitchen
  target_data:
    my_phone:
      image: "https://www.home-assistant.io/images/default-social.png"
      color: red
      channel: "Motion"
    telegram_first:
      type: photo
      url: "https://www.home-assistant.io/images/default-social.png"
    alexa_living_room:
      type: announce
      volume: 0.8
    gh_kitchen:
      volume: 0.5
```

</details>

## 🪲 Troubleshooting
<details>
  <summary>Click me</summary>
  
For debug, add in *configuration.yaml*:

```yaml
logger:
  default: info
  logs:
    custom_components.universal_notifier: debug
```

</details>
