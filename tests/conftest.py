"""Shared fixtures for Universal Notifier tests.

Uses MagicMock-based hass following the alexa_media_player pattern.
No dependency on pytest-homeassistant-custom-component for cross-platform support.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.universal_notifier.const import (
    CONF_ALT_SERVICES, CONF_ASSISTANT_NAME, CONF_BOLD_PREFIX, CONF_CHANNELS,
    CONF_DATE_FORMAT, CONF_DEFAULT_MEDIA_PLAYER, CONF_DND, CONF_GREETINGS,
    CONF_IGNORE_TITLE_VOICE, CONF_INCLUDE_TIME, CONF_IS_VOICE,
    CONF_PERSON_ENTITIES, CONF_PRIORITY_VOLUME, CONF_SERVICE, CONF_TARGET,
    CONF_TIME_SLOTS, DOMAIN)

# ---------------------------------------------------------------------------
# Default configuration matching config flow defaults
# ---------------------------------------------------------------------------

DEFAULT_DATA = {
    CONF_ASSISTANT_NAME: "Assistant",
    CONF_DATE_FORMAT: "%H:%M:%S",
    CONF_INCLUDE_TIME: True,
    CONF_BOLD_PREFIX: True,
    CONF_IGNORE_TITLE_VOICE: True,
    CONF_PRIORITY_VOLUME: 0.9,
    CONF_PERSON_ENTITIES: [],
    "weekend_days": [5, 6],
    CONF_DND: {
        "weekday": {"start": "23:00", "end": "06:00"},
        "weekend": {"start": "00:00", "end": "08:00"},
    },
    CONF_TIME_SLOTS: {
        "weekday": {
            "morning":   {"start": "07:00", "volume": 0.35},
            "afternoon": {"start": "12:00", "volume": 0.40},
            "evening":   {"start": "19:00", "volume": 0.30},
            "night":     {"start": "21:30", "volume": 0.10},
        },
        "weekend": {
            "morning":   {"start": "08:00", "volume": 0.30},
            "afternoon": {"start": "14:00", "volume": 0.40},
            "evening":   {"start": "19:00", "volume": 0.30},
            "night":     {"start": "22:30", "volume": 0.10},
        },
    },
    CONF_GREETINGS: {
        "morning":   ["Buongiorno"],
        "afternoon": ["Buon pomeriggio"],
        "evening":   ["Buonasera"],
        "night":     ["Buonanotte"],
    },
    CONF_CHANNELS: {
        "test_text": {
            CONF_SERVICE: "notify.mobile_app",
            CONF_TARGET: "mobile_app_phone",
            CONF_IS_VOICE: False,
            CONF_ALT_SERVICES: {},
            CONF_DEFAULT_MEDIA_PLAYER: "",
        },
        "test_voice": {
            CONF_SERVICE: "tts.google_say",
            CONF_TARGET: "media_player.living_room",
            CONF_IS_VOICE: True,
            CONF_ALT_SERVICES: {},
            CONF_DEFAULT_MEDIA_PLAYER: "media_player.living_room",
        },
        "test_telegram": {
            CONF_SERVICE: "telegram_bot.send_message",
            CONF_TARGET: "123456789",
            CONF_IS_VOICE: False,
            CONF_ALT_SERVICES: {},
            CONF_DEFAULT_MEDIA_PLAYER: "",
        },
    },
}


# ---------------------------------------------------------------------------
# Mock Service Registry — stores registered handlers and records calls
# ---------------------------------------------------------------------------

class MockServiceRegistry:
    """Simulates hass.services with handler registration and call dispatch."""

    def __init__(self):
        self._handlers: dict[tuple[str, str], callable] = {}
        self._calls: list[dict] = []

    def async_register(self, domain, service, handler, schema=None):
        self._handlers[(domain, service)] = handler

    def async_remove(self, domain, service):
        self._handlers.pop((domain, service), None)

    def has_service(self, domain, service=None):
        if service:
            return (domain, service) in self._handlers
        return any(d == domain for d, _ in self._handlers)

    async def async_call(self, domain, service, data=None, blocking=True, target=None):
        key = (domain, service)
        if key in self._handlers:
            call = MagicMock()
            call.data = data or {}
            await self._handlers[key](call)
        else:
            self._calls.append({
                "domain": domain,
                "service": service,
                "data": data or {},
                "target": target,
            })

    @property
    def calls(self) -> list[dict]:
        return self._calls

    def clear_calls(self):
        self._calls.clear()


# ---------------------------------------------------------------------------
# Mock States Manager
# ---------------------------------------------------------------------------

class MockStatesManager:
    """Simulates hass.states with get/set support."""

    def __init__(self):
        self._states: dict[str, MagicMock] = {}

    def get(self, entity_id):
        return self._states.get(entity_id)

    def async_set(self, entity_id, state, attributes=None):
        mock_state = MagicMock()
        mock_state.state = state
        mock_state.attributes = attributes or {}
        self._states[entity_id] = mock_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_dt_util_now():
    """Patch dt_util.now() so @freeze_time works with HA's timezone utility.

    Without this, dt_util.now() ignores freezegun and returns wall-clock time.
    """
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime.now(timezone.utc),
    ) as mock_now:
        # Update return_value on each call via side_effect
        mock_now.side_effect = lambda: datetime.now(timezone.utc)
        yield mock_now


@pytest.fixture
def hass():
    """Create a MagicMock-based hass with real service registry and states."""
    mock_hass = MagicMock()
    mock_hass.data = {}
    service_registry = MockServiceRegistry()
    states_manager = MockStatesManager()

    mock_hass.services = service_registry
    mock_hass.states = states_manager

    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    _tasks: list = []

    def _create_task(coro):
        task = asyncio.ensure_future(coro)
        _tasks.append(task)
        return task

    mock_hass.loop = MagicMock()
    mock_hass.loop.create_task = _create_task

    async def _block_till_done():
        # Cancel long-running tasks (like voice_queue_worker) before gathering
        for t in _tasks:
            if not t.done():
                t.cancel()
        if _tasks:
            await asyncio.gather(*_tasks, return_exceptions=True)
            _tasks.clear()

    mock_hass.async_block_till_done = _block_till_done

    return mock_hass


@pytest.fixture
def mock_config_entry():
    """Create a MagicMock config entry with standard configuration."""
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.data = DEFAULT_DATA.copy()
    entry.options = {}
    entry.entry_id = "test_entry_id"
    entry.unique_id = DOMAIN
    entry.title = "Universal Notifier"
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
async def setup_integration(hass, mock_config_entry):
    """Set up the Universal Notifier integration.

    Calls async_setup_entry to register the service handler and
    initialize runtime data in hass.data.
    """
    from custom_components.universal_notifier import async_setup_entry

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get_entity_id = MagicMock(return_value=None)

    with patch(
        "custom_components.universal_notifier.er.async_get",
        return_value=mock_ent_reg,
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        assert result is True

    # Store ent_reg on hass for tests that need to configure entity lookups
    hass._mock_ent_reg = mock_ent_reg

    return mock_config_entry


@pytest.fixture
def service_calls(hass):
    """Provide access to recorded service calls during a test."""
    return hass.services.calls


@pytest.fixture
def voice_calls(service_calls):
    """Filter service_calls to only voice-related domains (tts, media_player)."""
    return [c for c in service_calls if c["domain"] in ("tts", "media_player")]


@pytest.fixture
async def _call_send(hass, setup_integration):
    """Provide a helper to call the Universal Notifier send service.

    For voice channels, the handler queues items on voice_queue which are
    processed by a background worker that includes asyncio.sleep. We patch
    asyncio.sleep to be instant and wait for the queue to drain.

    Also patches er.async_get so the handler's entity registry lookups
    return our mock (returns None by default, configurable via hass._mock_ent_reg).
    """
    async def _send(**kwargs):
        # Clear previous calls so each invocation starts fresh
        hass.services.clear_calls()

        entry_id = setup_integration.entry_id
        voice_queue = hass.data[DOMAIN][entry_id].get("voice_queue")
        mock_ent_reg = hass._mock_ent_reg

        # Patch asyncio.sleep (voice worker) and er.async_get (entity registry)
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch(
                "custom_components.universal_notifier.er.async_get",
                return_value=mock_ent_reg,
            ),
        ):
            await hass.services.async_call(DOMAIN, "send", kwargs, blocking=True)
            # Drain voice queue if any items were queued
            if voice_queue and not voice_queue.empty():
                await voice_queue.join()

    return _send
