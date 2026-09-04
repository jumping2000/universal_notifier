# /config/custom_components/universal_notifier/__init__.py

import asyncio
import logging
import math
import random
import re

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_ENTITY_ID, CONF_SERVICE, CONF_TYPE,
                                 STATE_PLAYING)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (  # Config keys; Service keys (Inputs); Inner Channel keys; Entity IDs (auto-created); Other
    COMPANION_COMMANDS, CONF_ALT_SERVICES, CONF_ASSISTANT_NAME,
    CONF_BOLD_PREFIX, CONF_CHANNELS, CONF_CHAT_ID, CONF_DATA, CONF_DATE_FORMAT,
    CONF_DEFAULT_MEDIA_PLAYER, CONF_DND, CONF_ENTITY_ID, CONF_GREETINGS,
    CONF_IGNORE_TITLE_VOICE, CONF_INCLUDE_TIME, CONF_IS_VOICE, CONF_MESSAGE,
    CONF_OVERRIDE_GREETINGS, CONF_PERSON_ENTITIES, CONF_PRIORITY,
    CONF_PRIORITY_VOLUME, CONF_SERVICE, CONF_SKIP_ASSISTANT_NAME,
    CONF_SKIP_GREETING, CONF_TARGET,
    CONF_TARGET_DATA, CONF_TARGETS, CONF_TIME_SLOTS, CONF_TITLE, CONF_TYPE,
    DOMAIN, ENTITY_DND_OVERRIDE, ENTITY_LAST_MESSAGE, PLATFORMS)
####
from .utils import *

_LOGGER = logging.getLogger(__name__)
# Dizionario globale per tracciare gli stati originali fuori dal worker
_ORIGINAL_STATES = {}


# ==============================================================================
# LOGICA DI RICARICA E SCARICO
# ==============================================================================
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica l'entry quando le opzioni vengono aggiornate dall'utente."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Scarica l'entry e libera le risorse."""
    # Pulizia stati snapshot eventualmente orfani
    _ORIGINAL_STATES.clear()

    # Rimuovi il servizio
    hass.services.async_remove(DOMAIN, "send")

    # Scarica le piattaforme
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

# ==============================================================================
# LOGICA DI RESUME
# ==============================================================================

async def _get_player_snapshot(hass: HomeAssistant, entity_id: str) -> dict:
    """Cattura lo stato originale SOLO se non siamo già in una sessione di notifica."""
    if entity_id in _ORIGINAL_STATES:
        _LOGGER.debug(f"UniNotifier: {entity_id} già in sessione, salto snapshot.")
        return None
    state = hass.states.get(entity_id)
    if not state: return None
    attr = state.attributes
    snap = {
        "state": state.state,
        "volume": attr.get("volume_level"),
        "app_name": attr.get("app_name"),
        "media_content_id": attr.get("media_content_id"),
        "media_content_type": attr.get("media_content_type"),
        "media_position": attr.get("media_position"),
        "entity_id": entity_id
    }
    _ORIGINAL_STATES[entity_id] = snap
    _LOGGER.debug(f"UniNotifier: Snapshot originale salvato per {entity_id}: {snap}")
    return snap

async def _apply_resume(hass: HomeAssistant, entity_id: str, target_volume: float):
    """Ripristina lo stato salvato all'inizio della sessione."""
    snap = _ORIGINAL_STATES.pop(entity_id, None)
    restore_volume = (snap["volume"] if snap and snap["volume"] is not None else target_volume)
    await hass.services.async_call("media_player", "volume_set", {
        "entity_id": entity_id, "volume_level": restore_volume
    })
    _LOGGER.debug(f"UniNotifier: Resume del volume di {entity_id} con {restore_volume}")
    # Ripristino Contenuto (solo se stava suonando prima della prima notifica)
    if snap and snap["state"] == STATE_PLAYING:
        app = (snap.get("app_name") or "").lower()
        c_id = snap.get("media_content_id")
        try:
            if "spotify" in app or (c_id and "spotify" in c_id):
                await hass.services.async_call("media_player", "play_media", {
                    "entity_id": entity_id, "media_content_id": c_id, "media_content_type": "music"
                })
            else:
                await hass.services.async_call("media_player", "play_media", {
                    "entity_id": entity_id, "media_content_id": c_id,
                    "media_content_type": snap.get("media_content_type", "audio/mpeg")
                })
            _LOGGER.debug(f"UniNotifier: Tentativo di resume eseguito per {entity_id}")
        except Exception as e:
            _LOGGER.error(f"UniNotifier: Errore nel resume di {entity_id}: {e}")

# ==============================================================================
# SERVICE SCHEMA
# ==============================================================================

SEND_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MESSAGE): cv.string,
    vol.Required(CONF_TARGETS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TITLE): cv.string,
    vol.Optional(CONF_DATA): dict,
    vol.Optional(CONF_TARGET_DATA): dict,
    vol.Optional(CONF_PRIORITY): cv.boolean,
    vol.Optional(CONF_SKIP_GREETING): cv.boolean,
    vol.Optional(CONF_SKIP_ASSISTANT_NAME): cv.boolean,
    vol.Optional(CONF_INCLUDE_TIME): cv.boolean,
    vol.Optional(CONF_PRIORITY_VOLUME): cv.string,
    vol.Optional(CONF_ASSISTANT_NAME): cv.string,
    vol.Optional(CONF_BOLD_PREFIX): cv.boolean,
    vol.Optional(CONF_IGNORE_TITLE_VOICE): cv.boolean,
    vol.Optional(CONF_OVERRIDE_GREETINGS): dict,
}, extra=vol.ALLOW_EXTRA)

# ==============================================================================
# CONFIG ENTRY SETUP
# ==============================================================================

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup del componente Universal Notifier da config entry (UI)."""

    # Config effettiva: options sovrascrivono data (merge shallow)
    conf = {**entry.data, **entry.options}

    # --- Estrazione variabili di configurazione ---
    channels_config     = conf.get(CONF_CHANNELS, {})
    global_name         = conf.get(CONF_ASSISTANT_NAME, "")
    global_date_fmt     = conf.get(CONF_DATE_FORMAT, "%H:%M:%S")
    global_include_time = conf.get(CONF_INCLUDE_TIME, True)
    global_priority_vol = conf.get(CONF_PRIORITY_VOLUME, 0.9)
    time_slots_conf     = conf.get(CONF_TIME_SLOTS, {})
    dnd_conf            = conf.get(CONF_DND, {"start": "23:00", "end": "06:00"})
    # Retrocompat: migrate old flat DND to nested weekday/weekend
    if isinstance(dnd_conf, dict) and "weekday" not in dnd_conf and "start" in dnd_conf:
        dnd_conf = {"weekday": dnd_conf, "weekend": dnd_conf}
    base_greetings      = conf.get(CONF_GREETINGS, {})
    global_bold_setting          = conf.get(CONF_BOLD_PREFIX, True)
    global_ignore_title_voice   = conf.get(CONF_IGNORE_TITLE_VOICE, True)
    weekend_days         = [int(d) if isinstance(d, str) else d for d in conf.get("weekend_days", ["5", "6"])]

    # --- Inizializzazione coda TTS ---
    voice_queue = asyncio.Queue()

    person_entities_conf = conf.get(CONF_PERSON_ENTITIES, [])

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "conf":               conf,
        "voice_queue":        voice_queue,
        "runtime_priority_vol": None,   # override runtime da select entity
        "tts_buffer":         2.5,      # sovrascrivibile da number entity
        "text_format":        "html",   # sovrascrivibile da select entity
        "notification_mode":  "Normal", # sovrascrivibile da select entity
    }

    ############################################################################
    async def voice_queue_worker():
        """Worker in background che consuma la coda vocale."""
        _LOGGER.debug("UniNotifier: Voice Queue Worker avviato.")
        while True:
            task = await voice_queue.get()
            try:
                players = task['physical_players']
                target_vol = task['target_volume']
                # 1. SNAPSHOT (Solo all'inizio della catena)
                for eid in players:
                    await _get_player_snapshot(hass, eid)
                # 2. IMPOSTA VOLUME TARGET
                if players and target_vol is not None:
                    await hass.services.async_call("media_player", "volume_set", {
                        "entity_id": players, "volume_level": target_vol
                    })
                # 3. ESECUZIONE NOTIFICA
                _LOGGER.debug(f"UniNotifier: Elaborazione messaggio vocale: {task['text_content'][:35]}...")
                _LOGGER.debug(f"UniNotifier: {task['physical_players']} {task['target_volume']} {task['service']} {task['payload']} ")
                await hass.services.async_call(task['domain'], task['service'], task['payload'])
                # 4. ATTESA FINE MESSAGGIO
                tts_buffer = hass.data[DOMAIN][entry.entry_id].get("tts_buffer", 2.5)
                wait_time = estimate_tts_duration(task['text_content'], buffer=tts_buffer)
                _LOGGER.debug(f"UniNotifier: Attesa di {wait_time:.2f}s per fine messaggio.")
                await asyncio.sleep(wait_time)
                # 5. CONTROLLO CODA PER RESUME
                if voice_queue.empty():
                    _LOGGER.debug("UniNotifier: Coda vuota, chiusura sessione e ripristino media.")
                    for eid in list(_ORIGINAL_STATES.keys()):
                        await _apply_resume(hass, eid, target_vol)
                else:
                    _LOGGER.debug(f"UniNotifier: Coda non vuota ({voice_queue.qsize()} messaggi), posticipo resume.")
            except Exception as e:
                _ORIGINAL_STATES.clear()
                _LOGGER.error(f"UniNotifier: Errore nel worker vocale: {e}")
            finally:
                voice_queue.task_done()

    worker_task = hass.loop.create_task(voice_queue_worker())

    # Cancella il worker quando l'entry viene scaricata (reload/rimozione)
    def _cancel_worker() -> None:
        worker_task.cancel()

    entry.async_on_unload(_cancel_worker)

    ############################################################################
    async def async_send_notification(call: ServiceCall):
        """Handler principale del servizio 'send'."""
        # 1. Parsing Input
        global_raw_message = call.data.get(CONF_MESSAGE, "")
        global_title = call.data.get(CONF_TITLE)
        runtime_data = call.data.get(CONF_DATA, {})
        target_specific_data = call.data.get(CONF_TARGET_DATA, {})
        targets = call.data.get(CONF_TARGETS, [])
        override_name = call.data.get(CONF_ASSISTANT_NAME, global_name)
        skip_greeting = call.data.get(CONF_SKIP_GREETING, False)
        skip_assistant_name = call.data.get(CONF_SKIP_ASSISTANT_NAME, False)
        include_time = call.data.get(CONF_INCLUDE_TIME, global_include_time)
        # priority_volume: prima controlla override runtime (select entity), poi call data, poi config
        runtime_pv = hass.data[DOMAIN][entry.entry_id].get("runtime_priority_vol")
        priority_volume = call.data.get(
            CONF_PRIORITY_VOLUME,
            runtime_pv if runtime_pv is not None else float(global_priority_vol)
        )
        is_priority = call.data.get(CONF_PRIORITY, False)
        use_bold_prefix = call.data.get(CONF_BOLD_PREFIX, global_bold_setting)
        ignore_title_voice = call.data.get(CONF_IGNORE_TITLE_VOICE, global_ignore_title_voice)
        # 2. Analisi Contesto
        now = dt_util.now()
        now_time = now.time()
        now_weekday = now.weekday()  # 0=Mon, 6=Sun
        slot_key, slot_volume = get_current_slot_info(
            time_slots_conf, now_time, now_weekday, weekend_days
        )
        if now_weekday in weekend_days:
            active_dnd = dnd_conf.get("weekend", dnd_conf.get("weekday", {"start": "23:00", "end": "06:00"}))
        else:
            active_dnd = dnd_conf.get("weekday", {"start": "23:00", "end": "06:00"})
        is_dnd_active = is_time_in_range(active_dnd["start"], active_dnd["end"], now_time)

        # DND Override: switch entity forces DND on regardless of time
        ent_reg = er.async_get(hass)
        dnd_override_uid = f"{DOMAIN}_{entry.entry_id}_{ENTITY_DND_OVERRIDE}"
        dnd_override_entry = ent_reg.async_get_entity_id("switch", DOMAIN, dnd_override_uid)
        dnd_override_state = hass.states.get(dnd_override_entry) if dnd_override_entry else None
        if dnd_override_state and dnd_override_state.state == "on":
            is_dnd_active = True

        # 3. Gestione Saluti
        override_greetings_data = call.data.get(CONF_OVERRIDE_GREETINGS)
        effective_greetings = base_greetings
        if override_greetings_data:
            effective_greetings = base_greetings.copy()
            for key, value in override_greetings_data.items():
                if key in effective_greetings:
                    if not isinstance(value, list): value = [value]
                    effective_greetings[key] = value

        options = effective_greetings.get(slot_key, [])
        current_greeting = random.choice(options) if options and not skip_greeting else ""
        raw_name = override_name
        raw_time_str = now.strftime(global_date_fmt) if include_time else ""
        if isinstance(targets, str): targets = [targets]

        tasks = []

        # ======================================================================
        # 4. CICLO SUI CANALI
        # ======================================================================
        for target_alias in targets:
            if target_alias not in channels_config:
                _LOGGER.debug(f"UniNotifier: Target '{target_alias}' sconosciuto.")
                continue
            channel_conf = channels_config[target_alias]
            _LOGGER.debug(f"UniNotifier: START, Channel Configuration {channel_conf}")

            ####################################################################
            # A. Preparazione Dati Specifici
            specific_data = {}
            if target_alias in target_specific_data:
                specific_data = target_specific_data[target_alias].copy()
            _LOGGER.debug(f"UniNotifier: Sezione A, Specific Data {specific_data}")
            target_raw_message = specific_data.pop(CONF_MESSAGE, global_raw_message)

            dynamic_entities = specific_data.pop(CONF_ENTITY_ID, channel_conf.get(CONF_TARGET))
            if isinstance(dynamic_entities, str):
                dynamic_entities = [e.strip() for e in dynamic_entities.split(",") if e.strip()]
            elif dynamic_entities is None:
                dynamic_entities = []
            _LOGGER.debug(f"UniNotifier: Sezione A, Dynamic Entities {dynamic_entities}")

            ####################################################################
            # B. Selezione Servizio
            service_type = specific_data.pop(CONF_TYPE, runtime_data.get(CONF_TYPE, None))
            alt_services_conf = channel_conf.get(CONF_ALT_SERVICES, {})
            _LOGGER.debug(f"UniNotifier: Sezione B, Service type {service_type}")
            _LOGGER.debug(f"UniNotifier: Sezione B, Service alt {alt_services_conf}")

            if service_type and service_type in alt_services_conf:
                target_service_conf = alt_services_conf[service_type]
                full_service_name = target_service_conf[CONF_SERVICE]
                is_voice_channel = False
            else:
                full_service_name = channel_conf[CONF_SERVICE]
                is_voice_channel = channel_conf.get(CONF_IS_VOICE, False)
            _LOGGER.debug(f"UniNotifier: Sezione B, Full Service Name {full_service_name}")

            try:
                srv_domain, srv_name = full_service_name.split(".", 1)
            except ValueError:
                _LOGGER.error(f"UniNotifier: Sezione B, Servizio non valido {full_service_name}")
                continue

            ####################################################################
            # C. Check Comandi MOBILE APP
            is_command_message = False
            if target_raw_message in COMPANION_COMMANDS or str(target_raw_message).startswith("command_"):
                is_command_message = True
            _LOGGER.debug(f"UniNotifier: Sezione C, Is Command Message {is_command_message}")

            ####################################################################
            # D. COSTRUZIONE MESSAGGIO E TITOLO
            parse_mode = specific_data.get("parse_mode", runtime_data.get("parse_mode"))
            if not parse_mode and not is_voice_channel:
                parse_mode = hass.data[DOMAIN][entry.entry_id].get("text_format", "html")
            parse_mode = normalize_parse_mode(parse_mode, srv_domain)
            final_msg = ""
            final_title = global_title
            text_content_for_duration = ""
            if is_command_message:
                final_msg = target_raw_message
            else:
                if is_voice_channel:
                    clean_msg = clean_text_for_tts(str(target_raw_message))
                    clean_greet = clean_text_for_tts(current_greeting)
                    full_spoken_text = ""
                    if final_title and not ignore_title_voice:
                        clean_title = clean_text_for_tts(final_title)
                        if clean_title:
                            full_spoken_text += f"{clean_title}. "
                    if clean_greet:
                        full_spoken_text += f"{clean_greet}. "
                    full_spoken_text += clean_msg
                    final_msg = full_spoken_text
                    final_title = None
                    text_content_for_duration = final_msg
                elif srv_domain == "notify" and srv_name == "send_message":
                    device_type = "apple" if is_apple_device(hass, dynamic_entities) else "android"
                    final_msg, final_title = apply_mobile_notify_text_formatting(
                        message=target_raw_message,
                        title=final_title,
                        device_type=device_type,
                        name=raw_name,
                        time_str=raw_time_str,
                        greeting=current_greeting,
                        parse_mode=parse_mode,
                        use_bold_prefix=use_bold_prefix,
                        skip_assistant_name=skip_assistant_name,
                    )
                else:
                    clean_name = sanitize_text_visual(raw_name, parse_mode)
                    clean_time = sanitize_text_visual(raw_time_str, parse_mode)
                    clean_msg = sanitize_text_visual(str(target_raw_message), parse_mode)
                    clean_greet = sanitize_text_visual(current_greeting, parse_mode)
                    clean_orig_title = sanitize_text_visual(final_title, parse_mode) if final_title else None
                    if use_bold_prefix:
                        clean_name = apply_formatting(clean_name, parse_mode, "bold")
                        clean_time = apply_formatting(clean_time, parse_mode, "bold")
                        clean_orig_title = apply_formatting(clean_orig_title, parse_mode, "bold")
                    prefix_parts = []
                    if clean_name and not skip_assistant_name:
                        prefix_parts.append(clean_name)
                    if clean_time:
                        prefix_parts.append(clean_time)
                    clean_prefix = f"[{' - '.join(prefix_parts)}]" if prefix_parts else ""
                    greeting_part = f"{clean_greet}. " if clean_greet else ""
                    if clean_orig_title:
                        final_title = f"{clean_prefix} {clean_orig_title}" if clean_prefix else clean_orig_title
                        final_msg = f"{greeting_part}{clean_msg}"
                    else:
                        final_msg = f"{clean_prefix} {greeting_part}{clean_msg}" if clean_prefix else f"{greeting_part}{clean_msg}"

            # Escape MarkdownV2 special chars for Telegram
            if not is_voice_channel and parse_mode == "markdownv2":
                final_msg = escape_markdownv2(final_msg)
                if final_title:
                    final_title = escape_markdownv2(final_title)
            _LOGGER.debug(f"UniNotifier: Sezione D, Final message '{final_msg}'")

            ####################################################################
            # E. Determinazione del Volume attuale
            override_volume = specific_data.get("volume", runtime_data.get("volume"))
            if override_volume is not None:
                try: target_volume = float(override_volume)
                except ValueError: target_volume = slot_volume
            elif is_priority:
                target_volume = priority_volume
            else:
                target_volume = slot_volume

            ####################################################################
            # F. Applicazione Volume e Check DND (Solo Canali Voce)
            if is_voice_channel:
                if is_dnd_active and not is_priority and override_volume is None:
                    _LOGGER.debug(f"UniNotifier: Sezione F, Skipped '{target_alias}' (DND attivo)")
                    continue

            ####################################################################
            # F2. Filtro routing in base a notification_mode
            # Attivo SOLO se ci sono person entities configurate
            notification_mode = hass.data[DOMAIN][entry.entry_id].get("notification_mode", "Normal")
            if person_entities_conf and notification_mode != "Normal":
                if notification_mode == "Voice home":
                    family_state = hass.states.get(f"sensor.{DOMAIN}_family")
                    family_home = family_state is not None and family_state.state == "home"
                    if family_home and not is_voice_channel:
                        _LOGGER.debug(f"UniNotifier: Sezione F2, Skipped '{target_alias}' (Voice home, family a casa → solo voce)")
                        continue
                    elif not family_home and is_voice_channel:
                        _LOGGER.debug(f"UniNotifier: Sezione F2, Skipped '{target_alias}' (Voice home, family non a casa → solo testo)")
                        continue
                elif notification_mode == "Text home":
                    if is_voice_channel:
                        _LOGGER.debug(f"UniNotifier: Sezione F2, Skipped '{target_alias}' (Text home mode)")
                        continue

            ####################################################################
            # G. Costruzione Payload Finale
            service_payload = {}
            _LOGGER.debug(f"UniNotifier: Sezione G, final_title '{final_title}' ")
            if srv_domain == "telegram_bot":
                if "parse_mode" not in service_payload and parse_mode:
                    service_payload["parse_mode"] = parse_mode
                if service_type in ["photo", "video", "animation", "voice", "document"]:
                    service_payload["caption"] = final_msg
                else:
                    service_payload["message"] = final_msg
            else:
                service_payload["message"] = final_msg
            if final_title:
                service_payload["title"] = final_title
                if service_type in ["photo", "video", "animation", "voice", "document"]:
                    service_payload["caption"] = final_title + " " + final_msg
                    service_payload.pop("title", None)
            _LOGGER.debug(f"UniNotifier: Sezione G, service_payload '{service_payload}' ")

            ####################################################################
            # H. Routing dei Target nel Payload
            conf_target_value = channel_conf.get(CONF_TARGET)
            if conf_target_value is not None:
                # Normalize: always produce list[str] regardless of input type
                if not isinstance(conf_target_value, list):
                    if isinstance(conf_target_value, str) and "," in conf_target_value:
                        conf_target_value = [s.strip() for s in conf_target_value.split(",") if s.strip()]
                    else:
                        conf_target_value = [conf_target_value]
                conf_target_value = [str(x) for x in conf_target_value]
            if conf_target_value:
                if srv_domain == "tts":
                    service_payload[ATTR_ENTITY_ID] = conf_target_value
                elif srv_domain != "telegram_bot":
                    # Telegram gestito da Sezione J (iterazione per chat_id)
                    service_payload[CONF_TARGET] = conf_target_value
            _LOGGER.debug(f"UniNotifier: Sezione H, service_payload '{service_payload}' ")

            ####################################################################
            # I. Merge Dati Accessori (alexa type, telegram images, etc.)
            all_additional_data = {}
            if runtime_data: all_additional_data.update(runtime_data)
            if specific_data: all_additional_data.update(specific_data)
            for k in ["volume", CONF_TYPE, "parse_mode"]: all_additional_data.pop(k, None)

            if all_additional_data:
                if srv_domain == "notify":
                    if "data" not in service_payload: service_payload["data"] = {}
                    service_payload["data"].update(all_additional_data)
                else:
                    service_payload.update(all_additional_data)
            _LOGGER.debug(f"UniNotifier: Sezione I, service_payload '{service_payload}' ")
            if not is_voice_channel and not is_command_message and srv_domain == "notify" and parse_mode:
                if "data" not in service_payload:
                    service_payload["data"] = {}
                service_payload["data"].setdefault("parse_mode", parse_mode)

            ####################################################################
            physical_players = []
            # J. DISPATCH LOGIC: CODA PER VOCE vs IMMEDIATO
            if srv_domain == "telegram_bot":
                if conf_target_value:
                    for chat_id in conf_target_value:
                        p = service_payload.copy()
                        p[CONF_CHAT_ID] = int(chat_id)
                        _LOGGER.debug(f"UniNotifier: Sezione J, Telegram to chat_id={chat_id} payload {p}")
                        tasks.append(hass.services.async_call(srv_domain, srv_name, p))
            elif is_voice_channel:
                default_mp = channel_conf.get(CONF_DEFAULT_MEDIA_PLAYER, "")
                if srv_domain == "tts":
                    # Per TTS: dynamic_entities contiene il target TTS (tts.xxx),
                    # media_player_entity_id indica dove riprodurre l'audio
                    tts_media_players = specific_data.pop("media_player_entity_id", None)
                    if not tts_media_players and dynamic_entities:
                        # entity_id in target_data può contenere media_player da usare
                        tts_media_players = [e for e in dynamic_entities if isinstance(e, str) and e.startswith("media_player.")]
                    if not tts_media_players and default_mp:
                        tts_media_players = [default_mp]
                    if tts_media_players:
                        if isinstance(tts_media_players, str):
                            tts_media_players = [tts_media_players]
                        service_payload["media_player_entity_id"] = tts_media_players
                        physical_players.extend(tts_media_players)
                elif srv_domain == "notify":
                    if dynamic_entities:
                        notify_targets = dynamic_entities
                    elif default_mp:
                        notify_targets = [default_mp]
                    else:
                        notify_targets = conf_target_value or []
                    physical_players.extend(notify_targets)
                    service_payload[CONF_TARGET] = notify_targets
                physical_players = [p for p in physical_players if isinstance(p, str) and p.startswith("media_player.")]
                _LOGGER.debug(f"UniNotifier: Sezione J, Media players coinvolti {physical_players}.")
                queue_item = {
                    'domain': srv_domain,
                    'service': srv_name,
                    'payload': service_payload,
                    'text_content': text_content_for_duration,
                    'physical_players': physical_players,
                    'target_volume': target_volume
                }
                voice_queue.put_nowait(queue_item)
                _LOGGER.debug(f"UniNotifier: Sezione J, Messaggio per {target_alias} accodato.")
            else:
                _LOGGER.debug(f"UniNotifier: Sezione J, Final payload {service_payload} - Service data {srv_domain}/{srv_name}")
                if srv_domain == "notify" and srv_name == "send_message":
                    # notify.send_message requires target as a separate async_call
                    # parameter and does not accept 'target' or 'data' in service_data
                    target_entities = service_payload.pop(CONF_TARGET, None)
                    service_payload.pop("data", None)
                    call_target = {"entity_id": target_entities} if target_entities else None
                    tasks.append(hass.services.async_call(srv_domain, srv_name, service_payload, target=call_target))
                else:
                    tasks.append(hass.services.async_call(srv_domain, srv_name, service_payload))

        if tasks:
            await asyncio.gather(*tasks)

        # K. Last Message Sent — write raw message to text entity
        last_msg_uid = f"{DOMAIN}_{entry.entry_id}_{ENTITY_LAST_MESSAGE}"
        last_msg_entry = ent_reg.async_get_entity_id("text", DOMAIN, last_msg_uid)
        last_msg_eid = last_msg_entry
        try:
            if not last_msg_eid:
                raise ValueError(f"Entity with unique_id {last_msg_uid} not found in registry")
            await hass.services.async_call(
                "text", "set_value",
                {"entity_id": last_msg_eid, "value": global_raw_message[:255]},
                blocking=True,
            )
        except Exception as e:
            _LOGGER.warning(f"UniNotifier: Impossibile aggiornare {last_msg_eid}: {e}")

    ############################################################################
    # Registrazione servizio e caricamento piattaforme
    hass.services.async_register(DOMAIN, "send", async_send_notification, schema=SEND_SERVICE_SCHEMA)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Ricarica l'entry quando l'utente salva le opzioni
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True