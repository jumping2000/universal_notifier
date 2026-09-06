# 📢 Universal Notifier
a new release from an appdaemon app by @caiosweet and @jumping2000

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jumping2000/universal_notifier?style=for-the-badge)
![GitHub Release Date](https://img.shields.io/github/release-date/jumping2000/universal_notifier?style=for-the-badge)
![GitHub stars](https://img.shields.io/github/stars/jumping2000/universal_notifier?style=for-the-badge)
![GitHub issues](https://img.shields.io/github/issues/jumping2000/universal_notifier?style=for-the-badge)
![License](https://img.shields.io/github/license/jumping2000/universal_notifier?style=for-the-badge)
![HA integration](https://img.shields.io/badge/Home%20Assistant-Integration-blue?style=for-the-badge)

> **🆕 Latest (v0.9.0):** notify.send_message support and some fixes. See the [Changelog](CHANGELOG.md) for details.
>
> [User configuration Guide](USER_GUIDE.md)

### 🌍 Translations

| Language | README | User Guide |
|:---|:---|:---|
| en English | [README.md](README.md) | [USER_GUIDE.md](USER_GUIDE.md) |
| it Italiano | [README_IT.md](README_IT.md) | [USER_GUIDE_IT.md](USER_GUIDE_IT.md) |
| ca Català | [README_CA.md](README_CA.md) | [USER_GUIDE_CA.md](USER_GUIDE_CA.md) |
| es Español | [README_ES.md](README_ES.md) | [USER_GUIDE_ES.md](USER_GUIDE_ES.md) |
<!---
[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://https://github.com/jumping2000/universal_notifier/graphs/commit-activity?style=for-the-badge)
[![GitHub issues](https://img.shields.io/github/issues/jumping2000/universal_notifier)](https://github.com/jumping2000/universal_notifier/issues?style=for-the-badge)<br>
--->
### Buy me a coffee and give me a star ✨!
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/jumping)

[![Star History Chart](https://api.star-history.com/svg?repos=jumping2000/universal_notifier&type=Date)](https://star-history.com/#bytebase/star-history&Date)

___

**Universal Notifier** is a custom Home Assistant component that centralizes and enhances notification management.

It transforms simple automations into a "Smart Home" communication system that knows the time of day, respects your sleep (Do Not Disturb - DND), greets naturally, and automatically manages the volume of voice assistants.

## 🚀 Key Features

* **Unified Platform:** A single service (`universal_notifier.send`) for Telegram, Mobile App, Alexa, Google Home, etc.
* **Personalized notifications** to several targets (i.e. alarm notification to both Telegram and Alexa)
* **Voice vs. Text:** Automatically differentiates between messages to be read (with prefixes like `[Jarvis - 12:30]`) and messages to be spoken (clean text only).
* **Smart Time Slots & Volume:** Set different volumes for Morning, Afternoon, Evening, and Night. The component adjusts the volume *before* speaking.
* **Do Not Disturb (DND):** Define quiet hours for voice assistants. Critical notifications (`priority: true`) will still go through.
* **Random Greetings:** "Good morning," "Good afternoon," etc., chosen randomly from customizable lists.
* **Command Handling:** Native support for Companion App commands (e.g., `TTS`, `command_volume_level`) sent in "RAW" mode.
* **Intelligent Queueing (FIFO):** Voice notifications are handled by a background worker using asyncio.Queue. This prevents audio overlapping by playing messages sequentially.
* **Snapshot & Resume:** The system saves the state (volume, track, and app) of media players before a notification and tries to restore it after the entire queue is empty.

### 📊 Monitoring & Diagnostics - Entities

| Entity | Type | Description |
|:---|:---|:---|
| **Volume** | Sensor | Real-time sensor showing the exact volume percentage for the next notification, automatically calculated based on the current active time slot. Dynamic icon based on level. Extra attributes: `current_slot`, `raw_volume`. |
| **Family** | Sensor | Tracks family presence status (`home` / `not_home`) based on configured `person` entities. |
| **DND** | Binary Sensor | Indicates whether Do Not Disturb mode is currently active or inactive. |
| **Voice Buffer** | Number | Adjustable buffer time (0.5–10.0 s, step 0.5) for TTS playback to ensure complete message delivery. Default: 1.5 s. |
| **Priority Volume** | Select | Sets the volume level for priority notifications. Options: 0.1 to 1.0. |
| **Text Format** | Select | Selects the text formatting mode for notifications: `html` or `markdown`. |
| **Notification Mode** | Select | Controls notification routing based on presence: `Normal` (all go through), `Voice home` (voice only when home), `Text home` (text only, no voice). |
| **Default Media Players** | Sensor | Shows the default media players configured for voice channels. State: number of channels with a default. Attributes: map `{channel_alias: media_player.xxx}`. |
| **DND Override** | Switch | Forces Do Not Disturb on regardless of the time-based schedule. Useful for manually enabling quiet mode at any time. |
| **Last Message Sent** | Text | Stores the raw text of the last notification sent (max 255 characters). Updated automatically after each `universal_notifier.send` call. |

___

## 🛠️ Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jumping2000&repository=universal_notifier&category=Integration)

<details>
<summary>Click to show installation instructions</summary>
<ol>
<li>Install files:</li>
<ul>
<li><u>Using HACS:</u><br>
In the HACS panel, search for 'Universal Notifier', open the repository and click 'Download'.</li>
<li><u>Manually:</u><br>
Download the <a href="https://github.com/jumping2000/universal_notifier/releases">latest release</a> as a zip file and extract it into the `custom_components` folder in your HA installation.</li>
</ul>
<li>Restart HA to load the integration into HA.</li>
<li>Go to Settings -> Devices & services and click 'ADD INTEGRATION' button. Look for Universal Notifier and click to add it.</li>
<li>The Universal Notifier integration is ready for YAML configuration.</li>
</ol>
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

## ⚙️ Configuration (UI)

Universal Notifier is fully configurable from the Home Assistant UI. No YAML configuration is needed.

<details>
  <summary>Click me</summary>

### Initial Setup

After installing the integration, go to **Settings > Devices & Services > Add Integration** and search for **Universal Notifier**. The setup wizard will guide you through the following steps:

#### Step 1 — Global Settings & Do Not Disturb
| Setting | Description | Default |
|:---|:---|:---|
| Assistant Name | Name displayed in text message prefixes (e.g. `[Jarvis - 12:30]`) | `Jarvis` |
| Time Format | strftime format for the time prefix | `%H:%M` |
| Include Time in Message Prefix | Whether to show the time in text notifications | `true` |
| Bold Message Prefix | Whether to bold the assistant name and time | `true` |
| Priority Volume | Volume used when `priority: true` (0.0 – 1.0) | `0.9` |
| Person Entities | Optional person entities for presence detection | — |
| DND Start | Do Not Disturb start time (HH:MM) | `23:00` |
| DND End | Do Not Disturb end time (HH:MM) | `06:00` |

#### Step 2 — Time Slots
Set the start time and default TTS volume for each time period.

| Time Slot | Default Start | Default Volume |
|:---|:---|:---|
| Morning | 07:00 | 0.35 |
| Afternoon | 12:00 | 0.4 |
| Evening | 19:00 | 0.3 |
| Night | 22:00 | 0.1 |

#### Step 3 — Greetings
Enter one greeting per line for each time slot. A random greeting will be chosen each time a notification is sent.

#### Step 4 — First Channel (required)
You must add at least one notification channel to complete the setup. Each channel requires:

| Field | Description |
|:---|:---|
| Alias | A unique name for the channel (e.g. `alexa_living_room`) |
| Service | The HA service to call in `domain.service` format (e.g. `notify.mobile_app_pixel`) |
| Target | Target entity_id (optional, comma-separated for multiple targets) |
| Voice Channel | Enable for TTS devices (applies volume, DND, and greeting logic) |
| Alt Services | Optional JSON dict for alternative services (e.g. Telegram photo/video) |

### Editing Configuration

After initial setup, go to **Settings > Devices & Services > Universal Notifier > Configure** to access the options menu:

- **Global Settings** — Edit assistant name, time format, prefix options, and priority volume
- **Do Not Disturb** — Change DND start/end times
- **Time Slots** — Adjust start times and volumes for each period
- **Greetings** — Customize greetings for each time slot
- **Channels** — Add or remove notification channels

### Little tips
- if you forget configured channels, go to `Integrations` - `Universal Notifier` - `Configure` - `Channels` - `Remove channel` 
- for Telegram photo and video add in channel configuration: 
```
{
  "photo": {"service": "telegram_bot.send_photo"},
  "video": {"service": "telegram_bot.send_video"}
}
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
|skip_assistant_name|bool|No|If true, omits the assistant name from the visual prefix.|
|include_time|bool|No|Overrides the configuration to include/exclude the time in the visual prefix.|
|ignore_title_voice|bool|No|If true, ignores the title for voice notifications (TTS/notify voice channels).|
|bold_prefix|bool|No|Overrides the configuration to have assistant name and time in bold|
|assistant_name|string|No|Overrides the global assistant name.|
|override_greetings|dict|No|Overrides the default greetings.| 

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
    - telegram_bob
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
  message: The washing machine has finished its cycle.
  title: Laundry Alert
  priority: true
  targets:
    - google_home
    - telegram_bob
    - mobile_bob
  target_data:
    google_home:
      entity_id: media_player.kitchen
      volume: 0.3
    mobile_bob:
      image: "https://www.home-assistant.io/images/default-social.png"
      color: red
      channel: "washing-alert"
    telegram_bob:
      type: photo
      url: "https://www.home-assistant.io/images/default-social.png"
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
