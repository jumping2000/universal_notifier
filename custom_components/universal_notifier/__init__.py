# /config/custom_components/universal_notifier/__init__.py

"""Universal Notifier Component: wrapper unificato per l'invio di messaggi."""
import logging
import asyncio
import random
import voluptuous as vol
import homeassistant.util.dt as dt_util

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_SERVICE, CONF_SERVICE_DATA, CONF_ENTITY_ID, CONF_TARGET,
)

from .const import (
    DOMAIN, CONF_CHANNELS, CONF_ASSISTANT_NAME, CONF_DATE_FORMAT, 
    CONF_GREETINGS, CONF_IS_VOICE, CONF_OVERRIDE_GREETINGS, CONF_INCLUDE_TIME,
    DEFAULT_NAME, DEFAULT_DATE_FORMAT, DEFAULT_GREETINGS, DEFAULT_INCLUDE_TIME
)

_LOGGER = logging.getLogger(__name__)

# --- SCHEMI DI VALIDAZIONE ---

# Schema per i saluti: accetta liste o singole stringhe (convertite in liste da cv.ensure_list)
GREETINGS_SCHEMA = vol.Schema({
    vol.Optional("morning", default=DEFAULT_GREETINGS["morning"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("afternoon", default=DEFAULT_GREETINGS["afternoon"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("evening", default=DEFAULT_GREETINGS["evening"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("night", default=DEFAULT_GREETINGS["night"]): vol.All(cv.ensure_list, [cv.string]),
})

# Schema per ogni canale nel configuration.yaml
CHANNEL_SCHEMA = vol.Schema({
    vol.Required(CONF_SERVICE): cv.string,
    vol.Optional(CONF_IS_VOICE, default=False): cv.boolean,
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_TARGET): vol.Any(cv.string, int, list),
    vol.Optional(CONF_SERVICE_DATA): dict,
})

# Schema generale del componente in configuration.yaml
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ASSISTANT_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): cv.string,
        vol.Optional(CONF_INCLUDE_TIME, default=DEFAULT_INCLUDE_TIME): cv.boolean,
        # Default=GREETINGS_SCHEMA({}) assicura che se non specificato, si usino i default da const.py
        vol.Optional(CONF_GREETINGS, default=GREETINGS_SCHEMA({})): GREETINGS_SCHEMA, 
        vol.Required(CONF_CHANNELS): vol.Schema({
            cv.string: CHANNEL_SCHEMA
        }),
    }),
}, extra=vol.ALLOW_EXTRA)

# --- FUNZIONI DI LOGICA ---

def get_greeting(greetings_conf):
    """Restituisce un saluto random in base all'ora corrente."""
    now = dt_util.now()
    hour = now.hour
    
    key = "night"
    if 5 <= hour < 12:
        key = "morning"
    elif 12 <= hour < 18:
        key = "afternoon"
    elif 18 <= hour < 22:
        key = "evening"
    
    options = greetings_conf.get(key, [])
    
    if options:
        # Seleziona un saluto a caso dalla lista
        return random.choice(options)
    return ""

# --- FUNZIONE DI SETUP ---

async def async_setup(hass: HomeAssistant, config: dict):
    """Setup del componente Universal Notifier."""
    if DOMAIN not in config:
        return True
    
    conf = config[DOMAIN]
    channels_config = conf.get(CONF_CHANNELS, {})
    
    # Valori di base (config.yaml o const.py)
    base_greetings = conf.get(CONF_GREETINGS) 
    global_name = conf.get(CONF_ASSISTANT_NAME)
    global_date_fmt = conf.get(CONF_DATE_FORMAT)
    global_include_time = conf.get(CONF_INCLUDE_TIME)

    # --- FUNZIONE SERVIZIO ---
    async def async_send_notification(call: ServiceCall):
        """Servizio unificato di invio con logica Smart Assistant."""
        raw_message = call.data.get("message")
        title = call.data.get("title")
        runtime_data = call.data.get("data", {})
        targets = call.data.get("targets", [])
        
        # Override opzionali dalla chiamata servizio
        override_name = call.data.get("assistant_name", global_name)
        skip_greeting = call.data.get("skip_greeting", False)
        include_time = call.data.get(CONF_INCLUDE_TIME, global_include_time)
        
        # --- LOGICA DI SOVRASCRITTURA SALUTI ---
        override_greetings_data = call.data.get(CONF_OVERRIDE_GREETINGS)
        
        effective_greetings = base_greetings 
        
        if override_greetings_data:
            effective_greetings = base_greetings.copy() 
            
            for key, value in override_greetings_data.items():
                if key in effective_greetings:
                    # Garantiamo che il valore sovrascritto sia trattato come lista
                    if not isinstance(value, list):
                        value = [value]
                    effective_greetings[key] = value
        
        if isinstance(targets, str):
            targets = [targets]

        # Calcolo del saluto
        current_greeting = get_greeting(effective_greetings) if not skip_greeting else ""
        
        # Formattazione del prefisso TESTO
        # 1. Parte: Nome Assistente
        prefix_parts = [f"[{override_name}"]
        
        # 2. Parte: Orario (Condizionale)
        if include_time:
            current_time_str = dt_util.now().strftime(global_date_fmt)
            prefix_parts.append(f" - {current_time_str}")
        
        # 3. Chiusura parentesi e Spazio
        prefix_text = "".join(prefix_parts) + "] "
        
        # Preparazione messaggi formattati
        # Messaggio VOCE (Pulito): evita il prefisso per una pronuncia naturale
        msg_voice = f"{current_greeting}. {raw_message}" if current_greeting else raw_message
        
        # Messaggio TESTO (Formattato): include il prefisso per l'identificazione
        msg_text = f"{prefix_text}{msg_voice}"

        tasks = []

        for target_alias in targets:
            # 1. Verifica alias
            if target_alias not in channels_config:
                _LOGGER.warning(f"Universal Notifier: Target '{target_alias}' non definito in configuration.yaml")
                continue

            channel_conf = channels_config[target_alias]
            full_service_name = channel_conf[CONF_SERVICE]
            is_voice_channel = channel_conf[CONF_IS_VOICE]
            
            try:
                domain, service = full_service_name.split(".", 1)
            except ValueError:
                _LOGGER.error(f"Universal Notifier: Servizio malformato '{full_service_name}' per target '{target_alias}'")
                continue

            # 2. Verifica che l'integrazione sia caricata
            if domain not in hass.config.components:
                _LOGGER.warning(
                    f"Universal Notifier: Impossibile inviare a '{target_alias}'. "
                    f"L'integrazione '{domain}' non è caricata."
                )
                continue

            # 3. Costruzione Payload Dinamico
            service_payload = channel_conf.get(CONF_SERVICE_DATA, {}).copy()
            
            # SCELTA DEL MESSAGGIO: Voice vs Text
            service_payload["message"] = msg_voice if is_voice_channel else msg_text
            
            if title:
                service_payload["title"] = title

            # Gestione Entity ID, Target e Dati extra (come nelle notifiche standard)
            if CONF_ENTITY_ID in channel_conf:
                service_payload["entity_id"] = channel_conf[CONF_ENTITY_ID]
            
            if CONF_TARGET in channel_conf:
                service_payload["target"] = channel_conf[CONF_TARGET]

            # Merge dati extra
            if runtime_data:
                if domain == "notify":
                    if "data" not in service_payload:
                        service_payload["data"] = {}
                    service_payload["data"].update(runtime_data)
                else:
                    service_payload.update(runtime_data)

            # 4. Creazione Task Asincrono
            tasks.append(hass.services.async_call(domain, service, service_payload))

        if tasks:
            # Esegue tutti gli invii in parallelo
            await asyncio.gather(*tasks)

    # Registrazione del servizio
    hass.services.async_register(DOMAIN, "send", async_send_notification)

    return True
