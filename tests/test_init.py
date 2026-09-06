"""Tests for __init__.py — service handler, DND, routing, voice queue."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from custom_components.universal_notifier.const import (
    CONF_BOLD_PREFIX, CONF_CHANNELS, CONF_CHAT_ID, CONF_DATA,
    CONF_DEFAULT_MEDIA_PLAYER, CONF_DND, CONF_GREETINGS,
    CONF_IGNORE_TITLE_VOICE, CONF_INCLUDE_TIME, CONF_IS_VOICE, CONF_MESSAGE,
    CONF_OVERRIDE_GREETINGS, CONF_PERSON_ENTITIES, CONF_PRIORITY,
    CONF_PRIORITY_VOLUME, CONF_SERVICE, CONF_SKIP_GREETING, CONF_TARGET,
    CONF_TARGET_DATA, CONF_TARGETS, CONF_TIME_SLOTS, CONF_TITLE, CONF_TYPE,
    DOMAIN, ENTITY_DND_OVERRIDE, ENTITY_LAST_MESSAGE)
from tests.conftest import DEFAULT_DATA

# ============================================================================
# Service registration
# ============================================================================

class TestServiceRegistration:
    async def test_send_service_registered(self, hass, setup_integration):
        """The 'send' service should be registered after setup."""
        assert hass.services.has_service(DOMAIN, "send")


# ============================================================================
# Channel routing
# ============================================================================

class TestChannelRouting:
    async def test_text_channel_calls_notify(
        self, hass, _call_send, service_calls
    ):
        """Text channel should call the configured notify service."""
        await _call_send(
            message="Test message",
            targets=["test_text"],
        )
        notify_calls = [c for c in service_calls if c["domain"] == "notify"]
        assert len(notify_calls) >= 1
        assert notify_calls[0]["service"] == "mobile_app"
        assert "Test message" in notify_calls[0]["data"].get("message", "")

    async def test_unknown_target_is_skipped(
        self, hass, _call_send, service_calls
    ):
        """Unknown target alias should be silently skipped."""
        await _call_send(
            message="Test",
            targets=["nonexistent"],
        )
        assert len(service_calls) == 0

    async def test_multiple_targets(
        self, hass, _call_send, service_calls
    ):
        """Multiple targets should produce multiple service calls."""
        await _call_send(
            message="Broadcast",
            targets=["test_text", "test_telegram"],
        )
        domains = [c["domain"] for c in service_calls]
        assert "notify" in domains


# ============================================================================
# Empty target / notify.send_message
# ============================================================================

class TestEmptyTarget:
    @freeze_time("2026-06-17 10:00:00")
    async def test_empty_target_not_forwarded(
        self, hass, _call_send, service_calls, setup_integration
    ):
        """An empty target must not be forwarded as ['']."""
        entry = setup_integration
        conf = hass.data[DOMAIN][entry.entry_id]["conf"]
        original = conf[CONF_CHANNELS]["test_text"][CONF_TARGET]
        conf[CONF_CHANNELS]["test_text"][CONF_TARGET] = ""
        try:
            await _call_send(message="Test", targets=["test_text"])
            notify_calls = [c for c in service_calls if c["domain"] == "notify"]
            assert len(notify_calls) >= 1
            assert "target" not in notify_calls[0]["data"]
        finally:
            conf[CONF_CHANNELS]["test_text"][CONF_TARGET] = original


class TestNotifySendMessage:
    @freeze_time("2026-06-17 10:00:00")
    async def test_notify_send_message_target_kwarg(
        self, hass, _call_send, service_calls, setup_integration
    ):
        """notify.send_message must get target as kwarg, not inside data."""
        entry = setup_integration
        conf = hass.data[DOMAIN][entry.entry_id]["conf"]
        conf[CONF_CHANNELS]["mail_gianpi"] = {
            CONF_SERVICE: "notify.send_message",
            CONF_TARGET: "notify.gianpi_homeassistant",
            CONF_IS_VOICE: False,
            CONF_DEFAULT_MEDIA_PLAYER: "",
        }
        try:
            await _call_send(
                message="Prova", title="Casa Smart", targets=["mail_gianpi"]
            )
            calls = [
                c for c in service_calls
                if c["domain"] == "notify" and c["service"] == "send_message"
            ]
            assert len(calls) == 1
            assert "target" not in calls[0]["data"]
            assert "data" not in calls[0]["data"]
            assert calls[0]["data"].get("message")
            assert calls[0]["target"] == {"entity_id": ["notify.gianpi_homeassistant"]}
        finally:
            conf[CONF_CHANNELS].pop("mail_gianpi", None)


# ============================================================================
# DND logic
# ============================================================================

class TestDNDLogic:
    @freeze_time("2026-06-17 02:00:00")  # Wednesday, inside DND
    async def test_voice_skipped_during_dnd(
        self, hass, _call_send, service_calls
    ):
        """Voice channels should be skipped during DND hours."""
        await _call_send(
            message="Night alert",
            targets=["test_voice"],
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) == 0

    @freeze_time("2026-06-17 02:00:00")  # Wednesday, inside DND
    async def test_text_not_skipped_during_dnd(
        self, hass, _call_send, service_calls
    ):
        """Text channels should NOT be skipped during DND hours."""
        await _call_send(
            message="Text alert",
            targets=["test_text"],
        )
        notify_calls = [c for c in service_calls if c["domain"] == "notify"]
        assert len(notify_calls) >= 1

    @freeze_time("2026-06-17 02:00:00")
    async def test_priority_bypasses_dnd(
        self, hass, _call_send, service_calls
    ):
        """Priority messages should bypass DND on voice channels."""
        await _call_send(
            message="Emergency!",
            targets=["test_voice"],
            priority=True,
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) >= 1

    @freeze_time("2026-06-17 10:00:00")  # Wednesday, outside DND
    async def test_voice_works_outside_dnd(
        self, hass, _call_send, service_calls
    ):
        """Voice channels should work outside DND hours."""
        await _call_send(
            message="Daytime alert",
            targets=["test_voice"],
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) >= 1

    @freeze_time("2026-06-20 02:00:00")  # Saturday, inside weekend DND (00:00-08:00)
    async def test_weekend_dnd_uses_weekend_schedule(
        self, hass, _call_send, service_calls
    ):
        """Weekend DND should use the weekend schedule."""
        await _call_send(
            message="Weekend night",
            targets=["test_voice"],
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) == 0

    @freeze_time("2026-06-17 01:00:00")  # Wednesday 01:00 — inside weekday DND (23:00-06:00)
    async def test_weekday_dnd_uses_weekday_schedule(
        self, hass, _call_send, service_calls
    ):
        """Weekday DND at 01:00 should be active (23:00-06:00 range)."""
        await _call_send(
            message="Weekday night",
            targets=["test_voice"],
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) == 0


# ============================================================================
# DND Override switch
# ============================================================================

class TestDNDOverride:
    @freeze_time("2026-06-17 12:00:00")  # Outside normal DND
    async def test_dnd_override_forces_dnd(
        self, hass, _call_send, service_calls, setup_integration
    ):
        """DND override switch should force DND even outside normal hours."""
        # Configure entity registry to return an entity_id for the DND override switch
        dnd_entity_id = "switch.universal_notifier_dnd_override"
        hass._mock_ent_reg.async_get_entity_id = MagicMock(
            side_effect=lambda domain, platform, uid: (
                dnd_entity_id if uid == f"{DOMAIN}_test_entry_id_{ENTITY_DND_OVERRIDE}"
                else None
            )
        )

        # Set DND override switch to "on"
        hass.states.async_set(dnd_entity_id, "on")

        await _call_send(
            message="Should be blocked",
            targets=["test_voice"],
        )
        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        assert len(tts_calls) == 0


# ============================================================================
# Greetings
# ============================================================================

class TestGreetings:
    @freeze_time("2026-06-17 09:00:00")  # Morning
    async def test_greeting_included_in_message(
        self, hass, _call_send, service_calls
    ):
        """Morning greeting should be included in the message."""
        await _call_send(
            message="Test",
            targets=["test_text"],
        )
        assert len(service_calls) >= 1
        msg = service_calls[0]["data"].get("message", "")
        assert "Buongiorno" in msg

    @freeze_time("2026-06-17 09:00:00")
    async def test_skip_greeting(
        self, hass, _call_send, service_calls
    ):
        """skip_greeting=True should omit the greeting."""
        await _call_send(
            message="Test",
            targets=["test_text"],
            skip_greeting=True,
        )
        msg = service_calls[0]["data"].get("message", "")
        assert "Buongiorno" not in msg

    @freeze_time("2026-06-17 09:00:00")
    async def test_override_greetings(
        self, hass, _call_send, service_calls
    ):
        """override_greetings should replace default greetings."""
        await _call_send(
            message="Test",
            targets=["test_text"],
            override_greetings={"morning": ["Ciao custom"]},
        )
        msg = service_calls[0]["data"].get("message", "")
        assert "Ciao custom" in msg


# ============================================================================
# Title and bold prefix
# ============================================================================

class TestTitleAndPrefix:
    @freeze_time("2026-06-17 10:00:00")
    async def test_title_included(
        self, hass, _call_send, service_calls
    ):
        """Title should be included in the payload."""
        await _call_send(
            message="Body text",
            title="My Title",
            targets=["test_text"],
        )
        assert len(service_calls) >= 1
        data = service_calls[0]["data"]
        title = data.get("title", "")
        assert "My Title" in title

    @freeze_time("2026-06-17 10:00:00")
    async def test_bold_prefix_in_message(
        self, hass, _call_send, service_calls
    ):
        """Bold prefix [Name - Time] should be in the message."""
        await _call_send(
            message="Body",
            targets=["test_text"],
        )
        msg = service_calls[0]["data"].get("message", "")
        assert "Assistant" in msg  # configured name

    @freeze_time("2026-06-17 10:00:00")
    async def test_include_time_false(
        self, hass, _call_send, service_calls
    ):
        """include_time=False should omit time from prefix."""
        await _call_send(
            message="Body",
            targets=["test_text"],
            include_time=False,
        )
        msg = service_calls[0]["data"].get("message", "")
        # Time format is %H:%M:%S — if no time, prefix bracket should not have colon
        if "]" in msg:
            prefix_part = msg.split("]")[0]
            assert ":" not in prefix_part

    @freeze_time("2026-06-17 10:00:00")
    async def test_skip_assistant_name(
        self, hass, _call_send, service_calls
    ):
        """skip_assistant_name=True should omit the name but keep the time prefix."""
        await _call_send(
            message="Body",
            targets=["test_text"],
            skip_assistant_name=True,
        )
        msg = service_calls[0]["data"].get("message", "")
        assert "Assistant" not in msg  # configured name
        assert msg.startswith("[")  # time-only prefix remains
        assert ":" in msg.split("]")[0]

    @freeze_time("2026-06-17 10:00:00")
    async def test_skip_assistant_name_no_time_no_greeting(
        self, hass, _call_send, service_calls
    ):
        """With name, time and greeting all skipped, message is just the raw body."""
        await _call_send(
            message="Body",
            targets=["test_text"],
            skip_assistant_name=True,
            include_time=False,
            skip_greeting=True,
        )
        msg = service_calls[0]["data"].get("message", "")
        assert msg == "Body"

    @freeze_time("2026-06-17 10:00:00")
    async def test_skip_assistant_name_with_title(
        self, hass, _call_send, service_calls
    ):
        """skip_assistant_name=True should omit the name from the title prefix too."""
        await _call_send(
            message="Body",
            title="My Title",
            targets=["test_text"],
            skip_assistant_name=True,
        )
        data = service_calls[0]["data"]
        title = data.get("title", "")
        assert "Assistant" not in title
        assert "My Title" in title


# ============================================================================
# Telegram routing
# ============================================================================

class TestTelegramRouting:
    @freeze_time("2026-06-17 10:00:00")
    async def test_telegram_chat_id_as_int(
        self, hass, _call_send, service_calls
    ):
        """Telegram chat_id should be sent as int in the payload."""
        await _call_send(
            message="Telegram test",
            targets=["test_telegram"],
        )
        telegram_calls = [c for c in service_calls if c["domain"] == "telegram_bot"]
        assert len(telegram_calls) >= 1
        assert telegram_calls[0]["data"][CONF_CHAT_ID] == 123456789

    @freeze_time("2026-06-17 10:00:00")
    async def test_comma_separated_targets(
        self, hass, _call_send, service_calls, setup_integration
    ):
        """Comma-separated target in config should produce multiple calls."""
        entry = setup_integration
        conf = hass.data[DOMAIN][entry.entry_id]["conf"]
        original_target = conf[CONF_CHANNELS]["test_telegram"][CONF_TARGET]
        conf[CONF_CHANNELS]["test_telegram"][CONF_TARGET] = "111,222"
        try:
            await _call_send(
                message="Multi telegram",
                targets=["test_telegram"],
            )
            telegram_calls = [c for c in service_calls if c["domain"] == "telegram_bot"]
            assert len(telegram_calls) == 2
            chat_ids = {c["data"][CONF_CHAT_ID] for c in telegram_calls}
            assert chat_ids == {111, 222}
        finally:
            conf[CONF_CHANNELS]["test_telegram"][CONF_TARGET] = original_target


# ============================================================================
# Last message entity
# ============================================================================

class TestLastMessage:
    @freeze_time("2026-06-17 10:00:00")
    async def test_last_message_entity_updated(
        self, hass, _call_send, service_calls, setup_integration
    ):
        """Last message text entity should be updated after send."""
        # Configure entity registry to return entity_id for last message
        last_msg_entity_id = "text.universal_notifier_last_message_sent"
        hass._mock_ent_reg.async_get_entity_id = MagicMock(
            side_effect=lambda domain, platform, uid: (
                last_msg_entity_id
                if uid == f"{DOMAIN}_test_entry_id_{ENTITY_LAST_MESSAGE}"
                else None
            )
        )

        hass.states.async_set(last_msg_entity_id, "")

        await _call_send(
            message="Hello world",
            targets=["test_text"],
        )
        # The handler calls text.set_value — check it was called
        text_calls = [c for c in service_calls if c["domain"] == "text"]
        assert len(text_calls) >= 1
        assert text_calls[0]["data"]["value"] == "Hello world"


# ============================================================================
# Time slots / volume
# ============================================================================

class TestTimeSlots:
    @freeze_time("2026-06-17 09:00:00")  # Morning, weekday
    async def test_morning_slot_volume(
        self, hass, _call_send, service_calls
    ):
        """Morning slot should use morning volume (0.35)."""
        await _call_send(
            message="Volume test",
            targets=["test_voice"],
        )
        volume_calls = [
            c for c in service_calls
            if c["domain"] == "media_player" and c["service"] == "volume_set"
        ]
        assert len(volume_calls) >= 1
        assert volume_calls[0]["data"]["volume_level"] == 0.35


# ============================================================================
# notification_mode
# ============================================================================

class TestNotificationMode:
    @freeze_time("2026-06-17 10:00:00")
    async def test_text_home_mode_skips_voice(self, hass, service_calls, mock_config_entry):
        """Text home mode should skip voice channels when person_entities configured."""
        from custom_components.universal_notifier import async_setup_entry

        # Set person_entities BEFORE setup (captured by closure)
        entry_data = DEFAULT_DATA.copy()
        entry_data[CONF_PERSON_ENTITIES] = ["person.test"]
        mock_config_entry.data = entry_data

        mock_ent_reg = MagicMock()
        mock_ent_reg.async_get_entity_id = MagicMock(return_value=None)
        hass._mock_ent_reg = mock_ent_reg

        with (
            patch("custom_components.universal_notifier.er.async_get", return_value=mock_ent_reg),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await async_setup_entry(hass, mock_config_entry)

        hass.data[DOMAIN][mock_config_entry.entry_id]["notification_mode"] = "Text home"

        hass.services.clear_calls()
        with patch("custom_components.universal_notifier.er.async_get", return_value=mock_ent_reg):
            await hass.services.async_call(DOMAIN, "send", {
                "message": "Test",
                "targets": ["test_voice", "test_text"],
            }, blocking=True)

        tts_calls = [c for c in service_calls if c["domain"] == "tts"]
        notify_calls = [c for c in service_calls if c["domain"] == "notify"]
        assert len(tts_calls) == 0
        assert len(notify_calls) >= 1
