# /config/custom_components/universal_notifier/__init__.py

"""Universal Notifier Component: wrapper avanzato per notifiche e assistenti vocali."""
import logging
import asyncio
import random
import voluptuous as vol
import homeassistant.util.dt as dt_util
from datetime import time

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_SERVICE, CONF_SERVICE_DATA, CONF_ENTITY_ID, CONF_TARGET,
)

from .const import (
    DOMAIN, CONF_CHANNELS, CONF_ASSISTANT_NAME, CONF_DATE_FORMAT, 
    CONF_GREETINGS, CONF_IS_VOICE, CONF_OVERRIDE_GREETINGS, CONF_INCLUDE_TIME,
    CONF_TIME_SLOTS, CONF_DND, CONF_PRIORITY,
    DEFAULT_NAME, DEFAULT_DATE_FORMAT, DEFAULT_GREETINGS, DEFAULT_INCLUDE_TIME,
    DEFAULT_TIME_SLOTS, DEFAULT_DND, PRIORITY_VOLUME, COMPANION_COMMANDS
)

_LOGGER = logging.getLogger(__name__)

# --- SCHEMI DI VALIDAZIONE ---

# Schema singolo slot temporale
TIME_SLOT_SCHEMA = vol.Schema({
    vol.Required("start"): cv.time,          # Es. "06:00"
    vol.Optional("volume", default=0.5): vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
})

# Schema configurazione slot completa
TIME_SLOTS_CONFIG_SCHEMA = vol.Schema({
    vol.Optional("morning", default=DEFAULT_TIME_SLOTS["morning"]): TIME_SLOT_SCHEMA,
    vol.Optional("afternoon", default=DEFAULT_TIME_SLOTS["afternoon"]): TIME_SLOT_SCHEMA,
    vol.Optional("evening", default=DEFAULT_TIME_SLOTS["evening"]): TIME_SLOT_SCHEMA,
    vol.Optional("night", default=DEFAULT_TIME_SLOTS["night"]): TIME_SLOT_SCHEMA,
})

# Schema DND
DND_SCHEMA = vol.Schema({
    vol.Optional("start", default=DEFAULT_DND["start"]): cv.time,
    vol.Optional("end", default=DEFAULT_DND["end"]): cv.time,
})

# Schema Saluti
GREETINGS_SCHEMA = vol.Schema({
    vol.Optional("morning", default=DEFAULT_GREETINGS["morning"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("afternoon", default=DEFAULT_GREETINGS["afternoon"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("evening", default=DEFAULT_GREETINGS["evening"]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("night", default=DEFAULT_GREETINGS["night"]): vol.All(cv.ensure_list, [cv.string]),
})

# Schema Canali
CHANNEL_SCHEMA = vol.Schema({
    vol.Required(CONF_SERVICE): cv.string,
    vol.Optional(CONF_IS_VOICE, default=False): cv.boolean,
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_TARGET): vol.Any(cv.string, int, list),
    vol.Optional(CONF_SERVICE_DATA): dict,
})

# Schema Configurazione Globale
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ASSISTANT_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): cv.string,
        vol.Optional(CONF_INCLUDE_TIME, default=DEFAULT_INCLUDE_TIME): cv.boolean,
        vol.Optional(CONF_GREETINGS, default=GREETINGS_SCHEMA({})): GREETINGS_SCHEMA,
        vol.Optional(CONF_TIME_SLOTS, default=TIME_SLOTS_CONFIG_SCHEMA({})): TIME_SLOTS_CONFIG_SCHEMA,
        vol.Optional(CONF_DND, default=DND_SCHEMA({})): DND_SCHEMA,
        vol.Required(CONF_CHANNELS): vol.Schema({
            cv.string: CHANNEL_SCHEMA
        }),
    }),
}, extra=vol.ALLOW_EXTRA)

# --- HELPER FUNCTIONS ---

def is_time_in_range(start: time, end: time, now: time) -> bool:
    """Verifica se l'orario 'now' è compreso tra start e end, gestendo la mezzanotte."""
    if start <= end:
        return start <= now < end
    else: # Scavalla la mezzanotte (es. 23:00 -> 06:00)
        return start <= now or now < end

def get_current_slot_info(time_slots_conf, now_time):
    """
    Determina la fascia oraria corrente (key) e il volume target.
    Utilizza i dati configurati, senza fallback hardcoded.
    """
    # 1. Creiamo una lista ordinabile: [(orario_start, key, volume)]
    slots = []
    for key, data in time_slots_conf.items():
        slots.append((data["start"], key, data["volume"]))
    
    # 2. Ordiniamo per orario di inizio (00:00 -> 23:59)
    slots.sort(key=lambda x: x[0])
    
    # Variabili per il risultato
    found_key = None
    found_vol = None
    
    # 3. Cerchiamo lo slot attuale
    for start, key, vol in slots:
        if now_time >= start:
            found_key = key
            found_vol = vol
        else:
            # Se l'orario attuale è minore dello start dello slot,
            # ci fermiamo. L'ultimo valido rimane in found_key.
            break
    
    # 4. Gestione del "Wrap Around" (Scavallamento Mezzanotte)
    # Se found_key è ancora None, significa che now_time è prima del primo slot della giornata
    # (es. sono le 04:00 e il primo slot è alle 06:00).
    # In questo caso, usiamo l'ultimo slot configurato (es. Night).
    if found_key is None and slots:
        last_slot = slots[-1] 
        found_key = last_slot[1]
        found_vol = last_slot[2]
        
    return found_key, found_vol

# --- MAIN SETUP ---

async def async_setup(hass: HomeAssistant, config: dict):
    """Setup del componente Universal Notifier."""
    if DOMAIN not in config:
        return True
    
    conf = config[DOMAIN]
    channels_config = conf.get(CONF_CHANNELS, {})
    
    base_greetings = conf.get(CONF_GREETINGS) 
    time_slots_conf = conf.get(CONF_TIME_SLOTS)
    dnd_conf = conf.get(CONF_DND)
    
    global_name = conf.get(CONF_ASSISTANT_NAME)
    global_date_fmt = conf.get(CONF_DATE_FORMAT)
    global_include_time = conf.get(CONF_INCLUDE_TIME)

    async def async_send_notification(call: ServiceCall):
        """Servizio unificato di invio."""
        # 1. Parsing Input
        raw_message = call.data.get("message", "")
        title = call.data.get("title")
        runtime_data = call.data.get("data", {})
        target_specific_data = call.data.get("target_data", {})
        targets = call.data.get("targets", [])
        
        # Overrides & Flags
        override_name = call.data.get("assistant_name", global_name)
        skip_greeting = call.data.get("skip_greeting", False)
        include_time = call.data.get(CONF_INCLUDE_TIME, global_include_time)
        is_priority = call.data.get(CONF_PRIORITY, False)
        
        # 2. Contesto Temporale
        now = dt_util.now()
        now_time = now.time()
        
        # Recupera Slot e Volume base per l'ora attuale
        slot_key, slot_volume = get_current_slot_info(time_slots_conf, now_time)
        
        # Verifica DND
        is_dnd_active = is_time_in_range(dnd_conf["start"], dnd_conf["end"], now_time)
        
        _LOGGER.debug(f"UniNotifier: Time={now_time}, Slot={slot_key}, Vol={slot_volume}, DND={is_dnd_active}, Priority={is_priority}")

        # 3. Check Comandi Speciali (Companion App)
        is_command_message = False
        if raw_message in COMPANION_COMMANDS or str(raw_message).startswith("command_"):
            is_command_message = True
            _LOGGER.debug(f"UniNotifier: Comando rilevato '{raw_message}'. Modalità RAW attiva.")

        # 4. Costruzione Messaggi (Text vs Voice)
        if is_command_message:
            msg_voice = raw_message
            msg_text = raw_message
        else:
            # Gestione Greetings
            override_greetings_data = call.data.get(CONF_OVERRIDE_GREETINGS)
            effective_greetings = base_greetings 
            if override_greetings_data:
                effective_greetings = base_greetings.copy() 
                for key, value in override_greetings_data.items():
                    if key in effective_greetings:
                        if not isinstance(value, list): value = [value]
                        effective_greetings[key] = value

            # Selezione saluto in base allo slot corrente (slot_key)
            options = effective_greetings.get(slot_key, [])
            current_greeting = random.choice(options) if options and not skip_greeting else ""
            
            # Prefisso
            prefix_parts = [f"[{override_name}"]
            if include_time:
                current_time_str = now.strftime(global_date_fmt)
                prefix_parts.append(f" - {current_time_str}")
            prefix_text = "".join(prefix_parts) + "] "
            
            msg_voice = f"{current_greeting}. {raw_message}" if current_greeting else raw_message
            msg_text = f"{prefix_text}{msg_voice}"

        if isinstance(targets, str):
            targets = [targets]

        tasks = []

        # 5. Iterazione Targets
        for target_alias in targets:
            if target_alias not in channels_config:
                _LOGGER.warning(f"UniNotifier: Target '{target_alias}' sconosciuto.")
                continue

            channel_conf = channels_config[target_alias]
            full_service_name = channel_conf[CONF_SERVICE]
            is_voice_channel = channel_conf[CONF_IS_VOICE]
            entity_ids = channel_conf.get(CONF_ENTITY_ID)

            # --- LOGICA DND E VOLUME (Solo per canali Voice) ---
            if is_voice_channel:
                # Caso A: DND Attivo e NO Priorità -> Salta
                if is_dnd_active and not is_priority:
                    _LOGGER.info(f"UniNotifier: Skipped '{target_alias}' (DND attivo: {dnd_conf['start']}-{dnd_conf['end']})")
                    continue
                
                # Caso B: Priorità -> Volume Max (90%)
                # Caso C: Normale -> Volume dello Slot
                target_volume = PRIORITY_VOLUME if is_priority else slot_volume
                
                # Impostazione Volume (se c'è un entity_id)
                if entity_ids:
                    _LOGGER.debug(f"UniNotifier: Setting volume {target_volume} for {target_alias}")
                    vol_task = hass.services.async_call(
                        "media_player", 
                        "volume_set", 
                        {"entity_id": entity_ids, "volume_level": target_volume}
                    )
                    tasks.append(vol_task)

            # --- Preparazione Payload Servizio ---
            try:
                domain, service = full_service_name.split(".", 1)
            except ValueError:
                continue

            if domain not in hass.config.components:
                _LOGGER.warning(f"UniNotifier: Integrazione '{domain}' non caricata.")
                continue

            service_payload = channel_conf.get(CONF_SERVICE_DATA, {}).copy()
            service_payload["message"] = msg_voice if is_voice_channel else msg_text
            
            if title: service_payload["title"] = title
            if entity_ids: service_payload["entity_id"] = entity_ids
            if CONF_TARGET in channel_conf: service_payload["target"] = channel_conf[CONF_TARGET]
                
            # Merge Dati
            if runtime_data:
                if domain == "notify":
                    if "data" not in service_payload: service_payload["data"] = {}
                    service_payload["data"].update(runtime_data)
                else:
                    service_payload.update(runtime_data)

            if target_alias in target_specific_data:
                specific_data = target_specific_data[target_alias]
                if domain == "notify":
                    if "data" not in service_payload: service_payload["data"] = {}
                    service_payload["data"].update(specific_data)
                else:
                    service_payload.update(specific_data)

            # Aggiungi il task di invio messaggio
            tasks.append(hass.services.async_call(domain, service, service_payload))

        if tasks:
            await asyncio.gather(*tasks)

    hass.services.async_register(DOMAIN, "send", async_send_notification)
    return True
