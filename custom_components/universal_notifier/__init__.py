# /config/custom_components/universal_notifier/__init__.py

import logging
import random
import re
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, ServiceCall
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
    # Ordiniamo gli slot per orario di inizio
    sorted_slots = []
    for name, data in slots_conf.items():
        t_obj = dt_util.parse_time(data["start"])
        sorted_slots.append((name, t_obj, data.get("volume", 0.5)))
    
    sorted_slots.sort(key=lambda x: x[1]) # Ordina per orario
    
    current_slot = "day" # Fallback
    current_vol = 0.5
    
    # Logica semplice: trova l'ultimo slot passato
    for name, start_time, vol_val in sorted_slots:
        if now_time >= start_time:
            current_slot = name
            current_vol = vol_val
    
    # Se siamo prima del primo slot (es. 01:00 e il primo slot è 07:00),
    # allora siamo tecnicamente nell'ultimo slot della lista (notte)
    if now_time < sorted_slots[0][1]:
        current_slot = sorted_slots[-1][0]
        current_vol = sorted_slots[-1][2]
        
    return current_slot, current_vol

def clean_text_for_tts(text: str) -> str:
    """Rimuove caratteri speciali per la sintesi vocale."""
    if not text: return ""
    # Rimuove markdown base e parentesi
    text = re.sub(r'[*_`\[\]]', '', text)
    # Rimuove URL
    text = re.sub(r'http\S+', '', text)
    return text.strip()

def sanitize_text_visual(text: str, parse_mode: str = None) -> str:
    """Pulisce o esegue l'escape del testo per visualizzazione (HTML/Markdown)."""
    if not text: return ""
    # Se il target usa HTML (es. Telegram), dobbiamo fare l'escape di < e >
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
        # Telegram MarkdownV2 usa *bold*, Standard usa **bold**
        # Usiamo *text* che è spesso compatibile con V2
        return f"*{text}*" 
        
    return text

# ==============================================================================
# SCHEMAS
# ==============================================================================

CHANNEL_SCHEMA = vol.Schema({
    vol.Required(CONF_SERVICE): cv.string,
    vol.Optional(CONF_TARGET): cv.string, # Entity ID del provider (es. tts.google)
    vol.Optional(CONF_IS_VOICE, default=False): cv.boolean,
    vol.Optional(CONF_SERVICE_DATA): dict, # Dati statici (es. media_player target)
    vol.Optional(CONF_ALT_SERVICES): dict
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CHANNELS): vol.Schema({cv.string: CHANNEL_SCHEMA}),
        vol.Optional(CONF_ASSISTANT_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): cv.string,
        vol.Optional(CONF_INCLUDE_TIME, default=DEFAULT_INCLUDE_TIME): cv.boolean,
        vol.Optional(CONF_BOLD_PREFIX, default=DEFAULT_BOLD_PREFIX): cv.boolean, # <--- Config Globale
        vol.Optional(CONF_TIME_SLOTS, default=DEFAULT_TIME_SLOTS): dict,
        vol.Optional(CONF_DND, default=DEFAULT_DND): dict,
        vol.Optional(CONF_GREETINGS, default=DEFAULT_GREETINGS): dict,
    }),
}, extra=vol.ALLOW_EXTRA)

# Schema specifico per il servizio 'send' usando le COSTANTI
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
    
    # Caricamento configurazioni globali
    channels_config = conf[CONF_CHANNELS]
    global_name = conf[CONF_ASSISTANT_NAME]
    global_date_fmt = conf[CONF_DATE_FORMAT]
    global_include_time = conf[CONF_INCLUDE_TIME]
    
    time_slots_conf = conf.get(CONF_TIME_SLOTS, DEFAULT_TIME_SLOTS)
    dnd_conf = conf.get(CONF_DND, DEFAULT_DND)
    base_greetings = conf.get(CONF_GREETINGS, DEFAULT_GREETINGS)

    async def async_send_notification(call: ServiceCall):
        """
        Handler principale del servizio 'send'.
        """
        # 1. Parsing Input Runtime
        global_raw_message = call.data.get(CONF_MESSAGE, "")
        title = call.data.get(CONF_TITLE)
        runtime_data = call.data.get(CONF_DATA, {})
        target_specific_data = call.data.get(CONF_TARGET_DATA, {})
        targets = call.data.get(CONF_TARGETS, [])
        
        # Override parametri opzionali
        override_name = call.data.get(CONF_ASSISTANT_NAME, global_name)
        skip_greeting = call.data.get(CONF_SKIP_GREETING, False)
        include_time = call.data.get(CONF_INCLUDE_TIME, global_include_time)
        is_priority = call.data.get(CONF_PRIORITY, False)
        
        # Gestione Bold
        global_bold_setting = conf.get(CONF_BOLD_PREFIX, DEFAULT_BOLD_PREFIX)
        use_bold_prefix = call.data.get(CONF_BOLD_PREFIX, global_bold_setting)

        # 2. Analisi Contesto (Ora, Slot, DND)
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

        if isinstance(targets, str):
            targets = [targets]

        # ======================================================================
        # 4. CICLO SUI CANALI (TARGETS)
        # ======================================================================
        for target_alias in targets:
            if target_alias not in channels_config:
                _LOGGER.warning(f"UniNotifier: Target '{target_alias}' sconosciuto.")
                continue

            channel_conf = channels_config[target_alias]
            
            # A. Preparazione Dati Specifici
            specific_data = {}
            if target_alias in target_specific_data:
                specific_data = target_specific_data[target_alias].copy()
            
            # Recupero messaggio specifico o globale
            target_raw_message = specific_data.pop(CONF_MESSAGE, global_raw_message)

            # B. Selezione Servizio (Fallback o Principale)
            service_type = specific_data.pop(CONF_TYPE, runtime_data.get(CONF_TYPE, None))
            alt_services_conf = channel_conf.get(CONF_ALT_SERVICES, {})
            
            if service_type and service_type in alt_services_conf:
                target_service_conf = alt_services_conf[service_type]
                full_service_name = target_service_conf[CONF_SERVICE]
                base_service_payload = target_service_conf.get(CONF_SERVICE_DATA, {}) or {}
                # I servizi alternativi di solito non sono considerati "Voice" per logica volume/saluti
                is_voice_channel = False 
            else:
                full_service_name = channel_conf[CONF_SERVICE]
                base_service_payload = channel_conf.get(CONF_SERVICE_DATA, {}) or {}
                is_voice_channel = channel_conf[CONF_IS_VOICE]

            # C. Check Comandi (per mobile app)
            is_command_message = False
            if target_raw_message in COMPANION_COMMANDS or str(target_raw_message).startswith("command_"):
                is_command_message = True

            # D. Costruzione Messaggio Finale e Formattazione
            # Tentiamo di indovinare o leggere il parse_mode
            parse_mode = specific_data.get("parse_mode", runtime_data.get("parse_mode"))
            if not parse_mode and "telegram_bot" in full_service_name:
                # Default Telegram è spesso HTML se non specificato altrimenti
                parse_mode = "html"

            final_msg = ""
            
            if is_command_message:
                # Se è un comando, passiamo il raw message senza alterazioni
                final_msg = target_raw_message
            else:
                if is_voice_channel:
                    # Logica TTS (Niente Bolding, solo testo pulito)
                    clean_msg = clean_text_for_tts(str(target_raw_message))
                    clean_greet = clean_text_for_tts(current_greeting)
                    final_msg = f"{clean_greet}. {clean_msg}" if clean_greet else clean_msg
                else:
                    # Logica Visuale: Sanitizzazione + Bolding
                    
                    # 1. Sanitizziamo i componenti base
                    clean_name = sanitize_text_visual(raw_name, parse_mode)
                    clean_time = sanitize_text_visual(raw_time_str, parse_mode)
                    clean_msg = sanitize_text_visual(str(target_raw_message), parse_mode)
                    clean_greet = sanitize_text_visual(current_greeting, parse_mode)

                    # 2. Applichiamo il Bolding se richiesto
                    if use_bold_prefix:
                        clean_name = apply_formatting(clean_name, parse_mode, "bold")
                        clean_time = apply_formatting(clean_time, parse_mode, "bold")

                    # 3. Assemblaggio Prefisso
                    # Formato: [Nome - 12:00] oppure [Nome]
                    prefix_content = clean_name
                    if clean_time:
                        prefix_content += f" - {clean_time}"
                    
                    # Parentesi restano fuori dal grassetto
                    clean_prefix = f"[{prefix_content}] " 

                    greeting_part = f"{clean_greet}. " if clean_greet else ""
                    final_msg = f"{clean_prefix}{greeting_part}{clean_msg}"

            # E. Gestione Volume (Solo Canali Voice) e DND
            if is_voice_channel:
                if is_dnd_active and not is_priority:
                    _LOGGER.info(f"UniNotifier: DND attivo, skip audio su {target_alias}")
                    continue # Salta questo target
                
                target_volume = PRIORITY_VOLUME if is_priority else slot_volume
                
                # Cerchiamo l'entity_id del player per settare il volume
                # Può essere in service_data (config) o data (runtime)
                player_entity = base_service_payload.get(CONF_ENTITY_ID) or \
                                runtime_data.get(CONF_ENTITY_ID)
                
                if player_entity:
                    await hass.services.async_call(
                        "media_player",
                        "volume_set",
                        {CONF_ENTITY_ID: player_entity, "volume_level": target_volume}
                    )
            else:
                # Canali NON vocali (es. Telegram)
                # Se c'è DND, di solito inviamo comunque (silenzioso), a meno che tu non voglia bloccare tutto.
                # Qui lasciamo passare, la logica DND stringente è spesso solo audio.
                pass

            # F. Costruzione Payload Finale
            final_payload = base_service_payload.copy()
            final_payload.update(runtime_data) # Merge dati generali
            final_payload.update(specific_data) # Merge override target

            # Inseriamo il messaggio finale
            final_payload[CONF_MESSAGE] = final_msg
            if title:
                final_payload[CONF_TITLE] = title

            # F2. Rimozione entity_id per servizi notify.alexa_media (schema non lo accetta)
            if full_service_name.startswith("notify.alexa_media"):
                final_payload.pop(CONF_ENTITY_ID, None)

            # G. Gestione Entity ID del Provider (Fix CONF_TARGET)
            # Se la configurazione del canale ha 'target' (es. tts.google),
            # lo iniettiamo nel payload come 'entity_id' (o come richiesto dal servizio).
            if CONF_TARGET in channel_conf:
                final_payload[CONF_ENTITY_ID] = channel_conf[CONF_TARGET]

            # H. Chiamata al Servizio
            domain_service = full_service_name.split(".")
            if len(domain_service) == 2:
                srv_domain, srv_name = domain_service
                try:
                    await hass.services.async_call(srv_domain, srv_name, final_payload)
                except Exception as e:
                    _LOGGER.error(f"UniNotifier: Errore chiamata {full_service_name}: {e}")
            else:
                _LOGGER.error(f"UniNotifier: Servizio non valido {full_service_name}")

    # Registrazione del servizio con lo SCHEMA ESPLICITO
    hass.services.async_register(
        DOMAIN, 
        "send", 
        async_send_notification, 
        schema=SEND_SERVICE_SCHEMA
    )
    
    return True
