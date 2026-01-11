# /config/custom_components/universal_notifier/__init__.py

import logging
import random
import re
import voluptuous as vol
import asyncio
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util import dt as dt_util

# Importiamo TUTTE le costanti necessarie
from .const import (
    DOMAIN,
    # Config keys
    CONF_CHANNELS, CONF_ASSISTANT_NAME, CONF_DATE_FORMAT,
    CONF_GREETINGS, CONF_TIME_SLOTS, CONF_DND, CONF_BOLD_PREFIX,
    # Service keys (Inputs)
    CONF_MESSAGE, CONF_TITLE, CONF_TARGETS, CONF_DATA, CONF_TARGET_DATA,
    CONF_PRIORITY, CONF_SKIP_GREETING, CONF_INCLUDE_TIME, CONF_OVERRIDE_GREETINGS,
    # Inner Channel keys
    CONF_SERVICE, CONF_SERVICE_DATA, CONF_TARGET, CONF_ENTITY_ID,
    CONF_IS_VOICE, CONF_ALT_SERVICES, CONF_TYPE,
    # Defaults
    DEFAULT_NAME, DEFAULT_DATE_FORMAT, DEFAULT_INCLUDE_TIME,
    DEFAULT_GREETINGS, DEFAULT_TIME_SLOTS, DEFAULT_DND, 
    DEFAULT_BOLD_PREFIX, PRIORITY_VOLUME, COMPANION_COMMANDS
)

_LOGGER = logging.getLogger(__name__)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def is_time_in_range(start_str: str, end_str: str, now_time) -> bool:
    """Controlla se l'orario attuale è in un range (gestisce accavallamento notte)."""
    start = dt_util.parse_time(start_str)
    end = dt_util.parse_time(end_str)
    if start <= end:
        return start <= now_time <= end
    else:
        return start <= now_time or now_time <= end

def get_current_slot_info(slots_conf: dict, now_time) -> tuple:
    """Restituisce (nome_slot, volume) basandosi sull'ora attuale."""
    # Se la config è vuota, usiamo i default di const.py
    if not slots_conf:
        slots_conf = DEFAULT_TIME_SLOTS

    sorted_slots = []
    for name, data in slots_conf.items():
        # Parsing sicuro dell'orario
        t_str = data.get("start")
        t_obj = dt_util.parse_time(t_str) if t_str else None
        vol_val = data.get("volume", 0.2)
        if t_obj:
            sorted_slots.append((name, t_obj, vol_val))
    
    # Ordina per orario di inizio
    sorted_slots.sort(key=lambda x: x[1])
    
    if not sorted_slots:
        # Fallback estremo se nessun orario è valido
        return "default", 0.2

    # Logica: Inizializziamo con l'ultimo slot della lista.
    # Questo copre il caso "notte" (es. dalle 23:00 alle 07:00).
    # Se sono le 02:00, il loop sotto non scatterà mai, e rimarrà valido l'ultimo slot (night).
    current_slot = sorted_slots[-1][0]
    current_vol = sorted_slots[-1][2]
    
    for name, start_time, vol_val in sorted_slots:
        if now_time >= start_time:
            current_slot = name
            current_vol = vol_val
        # Non serve break, dobbiamo trovare l'ultimo slot valido (il più recente passato)
        
    return current_slot, current_vol

def clean_text_for_tts(text: str) -> str:
    """Rimuove caratteri speciali per la sintesi vocale."""
    if not text: return ""
    text = re.sub(r'[*_`\[\]]', '', text) # Via markdown
    text = re.sub(r'http\S+', '', text)    # Via URL
    return text.strip()

def sanitize_text_visual(text: str, parse_mode: str = None) -> str:
    """Pulisce o esegue l'escape del testo per visualizzazione (HTML/Markdown)."""
    if not text: return ""
    if parse_mode and "html" in parse_mode.lower():
        text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text

def apply_formatting(text: str, parse_mode: str, style: str = "bold") -> str:
    """Applica la formattazione (grassetto) in base al parse_mode."""
    if not text: return ""
    mode = parse_mode.lower() if parse_mode else ""
    
    if "html" in mode:
        if style == "bold": return f"<b>{text}</b>"
    
    elif "markdown" in mode:
        return f"*{text}*" 
        
    return text

# ==============================================================================
# SCHEMAS
# ==============================================================================

# Schema per uno slot orario
TIME_SLOT_SCHEMA = vol.Schema({
    vol.Required("start"): cv.string, # Validato poi come time
    vol.Optional("volume", default=0.5): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
})

# Schema per un canale
CHANNEL_SCHEMA = vol.Schema({
    vol.Required(CONF_SERVICE): cv.string,
    vol.Optional(CONF_TARGET): cv.string,
    vol.Optional(CONF_IS_VOICE, default=False): cv.boolean,
    vol.Optional(CONF_SERVICE_DATA): dict,
    vol.Optional(CONF_ALT_SERVICES): dict
})

# Schema Configurazione Globale
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CHANNELS): vol.Schema({cv.string: CHANNEL_SCHEMA}),
        vol.Optional(CONF_ASSISTANT_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): cv.string,
        vol.Optional(CONF_INCLUDE_TIME, default=DEFAULT_INCLUDE_TIME): cv.boolean,
        vol.Optional(CONF_BOLD_PREFIX, default=DEFAULT_BOLD_PREFIX): cv.boolean,
        # Validazione dizionario slot orari
        vol.Optional(CONF_TIME_SLOTS, default=DEFAULT_TIME_SLOTS): vol.Schema({
            cv.string: TIME_SLOT_SCHEMA
        }),
        # Validazione DND
        vol.Optional(CONF_DND, default=DEFAULT_DND): vol.Schema({
            vol.Required("start"): cv.string,
            vol.Required("end"): cv.string
        }),
        
        vol.Optional(CONF_GREETINGS, default=DEFAULT_GREETINGS): dict,
    }),
}, extra=vol.ALLOW_EXTRA)

SEND_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MESSAGE): cv.string,
    vol.Required(CONF_TARGETS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TITLE): cv.string,
    vol.Optional(CONF_DATA): dict,
    vol.Optional(CONF_TARGET_DATA): dict,
    vol.Optional(CONF_PRIORITY): cv.boolean,
    vol.Optional(CONF_SKIP_GREETING): cv.boolean,
    vol.Optional(CONF_INCLUDE_TIME): cv.boolean,
    vol.Optional(CONF_ASSISTANT_NAME): cv.string,
    vol.Optional(CONF_BOLD_PREFIX): cv.boolean,
    vol.Optional(CONF_OVERRIDE_GREETINGS): dict,
}, extra=vol.ALLOW_EXTRA)

# ==============================================================================
# MAIN LOGIC
# ==============================================================================

async def async_setup(hass: HomeAssistant, config: dict):
    """Setup del componente Universal Notifier."""
    
    if DOMAIN not in config:
        return True
    
    conf = config[DOMAIN]
    
    channels_config = conf[CONF_CHANNELS]
    global_name = conf[CONF_ASSISTANT_NAME]
    global_date_fmt = conf[CONF_DATE_FORMAT]
    global_include_time = conf[CONF_INCLUDE_TIME]
    
    time_slots_conf = conf.get(CONF_TIME_SLOTS, DEFAULT_TIME_SLOTS)
    dnd_conf = conf.get(CONF_DND, DEFAULT_DND)
    base_greetings = conf.get(CONF_GREETINGS, DEFAULT_GREETINGS)

    async def async_send_notification(call: ServiceCall):
        """Handler principale del servizio 'send'."""
        
        # 1. Parsing Input
        global_raw_message = call.data.get(CONF_MESSAGE, "")
        global_title = call.data.get(CONF_TITLE) # Titolo originale
        runtime_data = call.data.get(CONF_DATA, {})
        target_specific_data = call.data.get(CONF_TARGET_DATA, {})
        targets = call.data.get(CONF_TARGETS, [])
        
        override_name = call.data.get(CONF_ASSISTANT_NAME, global_name)
        skip_greeting = call.data.get(CONF_SKIP_GREETING, False)
        include_time = call.data.get(CONF_INCLUDE_TIME, global_include_time)
        is_priority = call.data.get(CONF_PRIORITY, False)
        
        global_bold_setting = conf.get(CONF_BOLD_PREFIX, DEFAULT_BOLD_PREFIX)
        use_bold_prefix = call.data.get(CONF_BOLD_PREFIX, global_bold_setting)

        # 2. Analisi Contesto
        now = dt_util.now()
        now_time = now.time()
        
        slot_key, slot_volume = get_current_slot_info(time_slots_conf, now_time)
        is_dnd_active = is_time_in_range(dnd_conf["start"], dnd_conf["end"], now_time)
        
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
        
        # Dati base per prefissi
        raw_name = override_name
        raw_time_str = now.strftime(global_date_fmt) if include_time else ""

        if isinstance(targets, str): targets = [targets]
        tasks = [] # Lista per asyncio.gather

        # ======================================================================
        # 4. CICLO SUI CANALI
        # ======================================================================
        for target_alias in targets:
            if target_alias not in channels_config:
                _LOGGER.info(f"UniNotifier: Target '{target_alias}' sconosciuto.")
                continue

            channel_conf = channels_config[target_alias]
            _LOGGER.debug(f"UniNotifier: Channel Configuration {channel_conf }")
            
            # A. Preparazione Dati Specifici
            specific_data = {}
            if target_alias in target_specific_data:
                specific_data = target_specific_data[target_alias].copy()
            _LOGGER.debug(f"UniNotifier: Specific Data {specific_data}")

            target_raw_message = specific_data.pop(CONF_MESSAGE, global_raw_message)
            
            # B. Selezione Servizio
            service_type = specific_data.pop(CONF_TYPE, runtime_data.get(CONF_TYPE, None))
            alt_services_conf = channel_conf.get(CONF_ALT_SERVICES, {})
            _LOGGER.debug(f"UniNotifier: Service type {service_type}")
            _LOGGER.debug(f"UniNotifier: Service alt {alt_services_conf}")
            
            if service_type and service_type in alt_services_conf:
                target_service_conf = alt_services_conf[service_type]
                full_service_name = target_service_conf[CONF_SERVICE]
                base_service_payload = target_service_conf.get(CONF_SERVICE_DATA, {}) or {}
                is_voice_channel = False 
            else:
                full_service_name = channel_conf[CONF_SERVICE]
                base_service_payload = channel_conf.get(CONF_SERVICE_DATA, {}) or {}
                is_voice_channel = channel_conf[CONF_IS_VOICE]

            _LOGGER.debug(f"UniNotifier: Full Service Name {full_service_name}")
            _LOGGER.debug(f"UniNotifier: Base Service Payload {base_service_payload}")

            # Estrai domini per controlli successivi
            try:
                srv_domain, srv_name = full_service_name.split(".", 1)
            except ValueError:
                _LOGGER.error(f"UniNotifier: Servizio non valido {full_service_name}")
                continue

            # C. Check Comandi
            is_command_message = False
            if target_raw_message in COMPANION_COMMANDS or str(target_raw_message).startswith("command_"):
                is_command_message = True

            # D. COSTRUZIONE MESSAGGIO E TITOLO
            parse_mode = specific_data.get("parse_mode", runtime_data.get("parse_mode"))
            if not parse_mode and srv_domain == "telegram_bot":
                parse_mode = "html"

            final_msg = ""
            final_title = global_title # Start col titolo originale
            
            if is_command_message:
                final_msg = target_raw_message
            else:
                # --- LOGICA 1: CANALI VOCALI (TTS) ---
                if is_voice_channel:
                    # 1. Pulizia testo per TTS
                    clean_msg = clean_text_for_tts(str(target_raw_message))
                    clean_greet = clean_text_for_tts(current_greeting)
                    # 2. Incorporazione del TITOLO nel messaggio vocale
                    full_spoken_text = ""
                    
                    if final_title:
                        clean_title = clean_text_for_tts(final_title)
                        if clean_title:
                            full_spoken_text += f"{clean_title}. "
                    
                    if clean_greet:
                        full_spoken_text += f"{clean_greet}. "
                    
                    full_spoken_text += clean_msg
                    
                    final_msg = full_spoken_text
                    
                    # 3. Rimuoviamo il titolo dal payload finale per evitare errori TTS
                    final_title = None 

                # --- LOGICA 2: CANALI VISUALI ---
                else:
                    # 1. Sanitizzazione base
                    clean_name = sanitize_text_visual(raw_name, parse_mode)
                    clean_time = sanitize_text_visual(raw_time_str, parse_mode)
                    clean_msg = sanitize_text_visual(str(target_raw_message), parse_mode)
                    clean_greet = sanitize_text_visual(current_greeting, parse_mode)
                    # Sanitizza anche il titolo originale se presente
                    clean_orig_title = sanitize_text_visual(final_title, parse_mode) if final_title else None

                    # 2. Bolding
                    if use_bold_prefix:
                        clean_name = apply_formatting(clean_name, parse_mode, "bold")
                        clean_time = apply_formatting(clean_time, parse_mode, "bold")

                    # 3. Costruzione stringa Prefisso
                    # Formato: [Nome - 12:00]
                    prefix_content = clean_name
                    if clean_time:
                        prefix_content += f" - {clean_time}"
                    clean_prefix = f"[{prefix_content}]" # Nota: niente spazio finale qui, lo gestiamo dopo

                    # 4. Distribuzione Prefisso (Richiesta 2)
                    greeting_part = f"{clean_greet}. " if clean_greet else ""
                    
                    if clean_orig_title:
                        # CASO A: Esiste un titolo -> Prefisso va nel Titolo
                        final_title = f"{clean_prefix} {clean_orig_title}"
                        final_msg = f"{greeting_part}{clean_msg}"
                    else:
                        # CASO B: Niente titolo -> Prefisso va nel Messaggio
                        # (clean_prefix + spazio + saluti + messaggio)
                        final_msg = f"{clean_prefix} {greeting_part}{clean_msg}"
                        
            ####################################################################
            # E. Determinazione del Volume
            override_volume = specific_data.get("volume", runtime_data.get("volume"))
            if override_volume is not None:
                try: target_volume = float(override_volume)
                except ValueError: target_volume = slot_volume
            elif is_priority:
                target_volume = PRIORITY_VOLUME
            else:
                target_volume = slot_volume

            # F. IDENTIFICAZIONE DEI PLAYER FISICI (Per Volume e Invio)
            # 1. Cerca in tts (media_player_entity_id standard)
            tts_players = base_service_payload.get("media_player_entity_id", [])
            if isinstance(tts_players, str): tts_players = [tts_players]
            
            # 2. Cerca in notify/alexa (target nel config del canale)
            notify_targets = channel_conf.get(CONF_TARGET, [])
            if isinstance(notify_targets, str): notify_targets = [notify_targets]
            
            _LOGGER.debug(f"UniNotifier: MediaPlayer o ChatId o tts target {notify_targets}")

            # 3. Lista unificata dei player a cui impostare il volume
            media_players_targets = []
            if tts_players:
                media_players_targets.extend(tts_players)
            if notify_targets and is_voice_channel:
                media_players_targets.extend(notify_targets)

            # G. Applicazione Volume e Check DND (Solo Canali Voce)
            if is_voice_channel:
                if is_dnd_active and not is_priority and override_volume is None:
                    _LOGGER.info(f"UniNotifier: Skipped '{target_alias}' (DND attivo)")
                    continue
                
                _LOGGER.debug(f"UniNotifier: MediaPlayer {media_players_targets} - Volume {target_volume}")
                
                # Imposta volume se abbiamo player identificati
                if media_players_targets:
                    tasks.append(hass.services.async_call(
                        "media_player", "volume_set", 
                        {"entity_id": media_players_targets, "volume_level": target_volume}
                    ))

            # F. Costruzione Payload Finale
            service_payload = base_service_payload.copy()

            # Mapping Messaggio
            if srv_domain == "telegram_bot":
                if "parse_mode" not in service_payload and parse_mode:
                    service_payload["parse_mode"] = parse_mode
                if service_type in ["photo", "video"]: 
                    service_payload["caption"] = final_msg
                else: 
                    service_payload["message"] = final_msg
            else:
                service_payload["message"] = final_msg # Standard per TTS e Notify

            if final_title: service_payload["title"] = final_title
            
            # I. Routing dei Target nel Payload
            # Caso 1: TTS usa 'media_player_entity_id' già presente nei dati base.
            # Caso 2: Provider TTS (es. google_translate)
            if srv_domain == "tts" and CONF_TARGET in channel_conf:
                provider_entity = channel_conf.get(CONF_TARGET)
                if provider_entity:
                    service_payload[ATTR_ENTITY_ID] = provider_entity
            
            # J. Merge Dati Accessori (alexa type, telegram images, etc.)
            all_additional_data = {}
            if runtime_data: all_additional_data.update(runtime_data)
            if specific_data: all_additional_data.update(specific_data)
            
            # Pulizia chiavi interne
            for k in ["volume", CONF_TYPE, "parse_mode"]: all_additional_data.pop(k, None)

            if all_additional_data:
                if srv_domain == "notify":
                    # Per Alexa e Mobile App i dati vanno in "data"
                    if "data" not in service_payload: service_payload["data"] = {}
                    service_payload["data"].update(all_additional_data)
                else:
                    # Per altri servizi, merge diretto
                    service_payload.update(all_additional_data)

            # G. Fix Entity ID Injection
            # Iniettiamo CONF_TARGET come entity_id SOLO se il servizio è un TTS
            # if srv_domain == "tts" and CONF_TARGET in channel_conf:
            #     final_payload[CONF_ENTITY_ID] = channel_conf[CONF_TARGET]

            # H. SEND 
            if srv_domain == "telegram_bot":
                p = service_payload.copy()
                p[CONF_TARGET] = str(notify_targets[0]) # Telegram vuole 'target' per il chat_id
                _LOGGER.debug(f"UniNotifier: Final payload {p} - Service data {srv_domain}/{srv_name}")
                tasks.append(hass.services.async_call(srv_domain, srv_name, p))
            else:
                # Chiamata Standard (TTS, Alexa, Notify)
                _LOGGER.debug(f"UniNotifier: Final payload {service_payload} - Service data {srv_domain}/{srv_name}")
                tasks.append(hass.services.async_call(srv_domain, srv_name, service_payload))

        # Esecuzione parallela di tutti i task (volumi e notifiche)
        if tasks:
            await asyncio.gather(*tasks)

    hass.services.async_register(
        DOMAIN, "send", async_send_notification, schema=SEND_SERVICE_SCHEMA
    )
    
    return True
