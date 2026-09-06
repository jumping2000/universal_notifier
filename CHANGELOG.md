# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.9.0] - 2026-09-06 - PRODUCTION

### Added
- **`notify.send_message` support**: Channels using the Home Assistant notify entity architecture (`service: notify.send_message` + `target: notify.<name>`) are now dispatched correctly. The target is passed as the `target` kwarg of the service call and the `data` key is no longer injected, both of which `notify.send_message` rejects.

### Fixed
- **Empty target no longer forwarded as `['']`**: A channel with a blank `target` field no longer overrides the default recipient of `notify.*` services (e.g. SMTP) with an empty list. Empty and whitespace-only entries are now filtered out during target normalization.

## [0.8.4] - 2026-07-26 - PRODUCTION

### Added
- **Skip Assistant Name flag**: New optional `skip_assistant_name` boolean in the `universal_notifier.send` service. When true, the assistant name is omitted from the visual prefix (`[Home Assistant - 10:00]` becomes `[10:00]`). Combined with `include_time: false` and `skip_greeting: true`, notifications are delivered as the raw message with no prefix at all. Also fixes the stray `[ - 10:00]` prefix shown when the configured assistant name was empty.

## [0.8.3] - 2026-06-17 - PRODUCTION
New version, see preproduction releases for new features

## [0.8.2] - 2026-06-17 - PREPROD

### Fixed
- **Volume sensor weekday/weekend slots**: The Volume sensor now correctly works. Previously the sensor always used the default path regardless of the day of the week.
- **Telegram target normalization**: `CONF_TARGET` (chat_id) is now normalized once to `list[str]` regardless of input type (single value, list, comma-separated string, numeric). Eliminated redundant re-reads and inconsistent `int`/`str` conversions

## [0.8.1] - 2026-06-14 - PREPROD

### Fixed
- **Telegram parse modes**: MarkdownV2 bold: `**bold**` correctly converted to `*bold*` per Telegram spec. `plain_text` strips `**bold**`/`*italic*` markers instead of showing them literally. `parse_mode` removed from notify service `data` (unsupported by `mobile_app`).
- **Volume resume when media player is idle**: When a media player is idle/off at notification time, the snapshot captures `volume_level=None`. Previously, the resume phase would try to restore `None`, producing a no-op. Now it falls back to the target volume used during the notification.
- **Select entities persist across restarts**: `PriorityVolumeSelect`, `TextFormatSelect`, and `NotificationModeSelect` now use `RestoreEntity` to survive HA reboots.

## [0.8.0] - 2026-06-13 - PREPROD

### Added
- **Weekday/Weekend DND**: Do Not Disturb now supports separate schedules for weekdays and weekends, configurable independently in the UI.
- **Weekday/Weekend time slots**: Time slots (with volumes) now support also weekdays and weekends, configurable independently in the UI.
- **Comma-separated targets**: The `target` field in channel configuration now accepts comma-separated values (e.g. `"-100123,-100456"`). Notifications are sent to all specified targets automatically.
- **Weekend days selector**: Configurable weekend days (default: Saturday and Sunday) used by the DND split logic.
- **DND Override switch**: New switch entity (`switch.*_dnd_override`) that forces DND on regardless of the time-based schedule. Useful for manually enabling quiet mode at any time.
- **Last Message Sent entity**: New text entity (`text.*_last_message_sent`) that stores the raw text of the last notification sent (max 255 characters). Updated automatically after each `universal_notifier.send` call.

### Changed
- DND and Time slots configuration migrated from a single start/end range to a nested `{"weekday": {...}, "weekend": {...}}` structure with automatic backward compatibility for existing flat configurations.

### Fixed
- **HTML formatting for Telegram and Companion**: User-provided HTML (`<b>`, `<i>`, `<a>`) is now preserved and correctly rendered in Telegram and HA Companion instead of being escaped as `&lt;`.
- **Markdown formatting for Telegram**: `parse_mode` is now correctly normalized to `"MarkdownV2"` for Telegram (was `"markdown"` which Telegram ignores). Special characters are auto-escaped while preserving `**bold**` syntax.
- **Voice channels no longer read HTML tags**: `clean_text_for_tts()` now strips HTML tags (`<b>`, `<i>`, `<a>`, etc.) before sending to TTS engines like Google Home.
- **Voice channels no longer read emoji/icons**: `clean_text_for_tts()` now strips emoji and Unicode icons (🏠, 🌡️, 💧, 🔔, ⚡, ✅, etc.) while preserving accented characters (è, à, ò, ù).
- **Voice buffer persistence**: The Voice Buffer slider now persists its value across HA restarts using `RestoreEntity`.
- **Last Message Sent not updating**: Added missing `async_set_value()` implementation to the text entity — `text.set_value` service call was silently failing because `TextEntity` requires this method to be implemented by subclasses.

## [0.7.1] - 2026-04-03

### Added
- Dynamic target for voice notifications

### Changed
- a lot of entities to monitor/personalize your Universal Notifier
- transition to UI configuration
