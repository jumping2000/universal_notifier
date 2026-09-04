# /config/custom_components/universal_notifier/utils.py
import re

from homeassistant.util import dt as dt_util

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

DEFAULT_TIME_SLOTS = {
    "weekday": {
        "morning": {"start": "07:00", "volume": 0.35},
        "afternoon": {"start": "12:00", "volume": 0.40},
        "evening": {"start": "19:00", "volume": 0.30},
        "night": {"start": "22:00", "volume": 0.10},
    },
    "weekend": {
        "morning": {"start": "07:00", "volume": 0.35},
        "afternoon": {"start": "12:00", "volume": 0.40},
        "evening": {"start": "19:00", "volume": 0.30},
        "night": {"start": "22:00", "volume": 0.10},
    },
}

def estimate_tts_duration(text: str, buffer: float) -> float:
    """Stima la durata del messaggio in secondi basandosi sulle parole."""
    if not text: return 0
    words = len(text.split())
    estimated_seconds = (words / 1.5) + buffer
    return max(buffer + 2.0, estimated_seconds)

def is_time_in_range(start_str: str, end_str: str, now_time) -> bool:
    """Controlla se l'orario attuale è in un range (gestisce accavallamento della notte)."""
    start = dt_util.parse_time(start_str)
    end = dt_util.parse_time(end_str)
    if start <= end:
        return start <= now_time <= end
    else:
        return start <= now_time or now_time <= end

def get_current_slot_info(slots_conf: dict, now_time,
                          now_weekday: int,
                          weekend_days: list) -> tuple:
    """Restituisce (nome_slot, volume) basandosi sull'ora attuale e giorno."""
    # Se la config è vuota, usiamo i default
    if not slots_conf:
        slots_conf = DEFAULT_TIME_SLOTS

    # Determine which group to use: weekend vs weekday
    # Convert weekend_days to ints (HA selector now returns strings)
    if weekend_days is not None:
        weekend_days = [int(d) if isinstance(d, str) else d for d in weekend_days]
    if (weekend_days is not None and now_weekday is not None
            and now_weekday in weekend_days):
        group = slots_conf.get("weekend", slots_conf)
    else:
        group = slots_conf.get("weekday", slots_conf)

    # If the selected group is itself flat (old format or fallback),
    # "weekday" / "weekend" key won't exist, so group = slots_conf (flat dict).
    # If group is a nested dict with slot keys, use it; otherwise fall back.
    if not group or not isinstance(group, dict):
        group = slots_conf

    # Check if group is flat (old format: {"morning": {...}, ...})
    # vs nested (new format). If the first value is a dict with "start", it's flat.
    sample_val = next(iter(group.values()), None)
    if isinstance(sample_val, dict) and "start" in sample_val:
        working_slots = group
    else:
        # Fallback: use the original slots_conf directly (old flat format)
        working_slots = slots_conf

    sorted_slots = []
    for name, data in working_slots.items():
        if not isinstance(data, dict):
            continue
        t_str = data.get("start")
        t_obj = dt_util.parse_time(t_str) if t_str else None
        vol_val = data.get("volume", 0.2)
        if t_obj:
            sorted_slots.append((name, t_obj, vol_val))
    # Ordina per orario di inizio
    sorted_slots.sort(key=lambda x: x[1])
    if not sorted_slots:
        return "default", 0.2
    # Logica: Inizializziamo con l'ultimo slot della lista.
    # Questo copre il caso "notte" (es. dalle 23:00 alle 07:00).
    current_slot = sorted_slots[-1][0]
    current_vol = sorted_slots[-1][2]
    for name, start_time, vol_val in sorted_slots:
        if now_time >= start_time:
            current_slot = name
            current_vol = vol_val
    return current_slot, current_vol

# Tag SSML supportati dai motori TTS (Alexa, Google): vanno preservati.
SSML_TAGS = {
    "speak", "voice", "prosody", "break", "say-as", "emphasis",
    "lang", "phoneme",
}
_TAG_PATTERN = re.compile(r'<\s*/?\s*([a-zA-Z][\w:-]*)[^>]*>')

def _strip_non_ssml_tags(text: str) -> str:
    """Rimuove i tag HTML mantenendo i tag SSML noti."""
    return _TAG_PATTERN.sub(
        lambda m: m.group(0) if m.group(1).lower() in SSML_TAGS else '', text
    )

def clean_text_for_tts(text: str) -> str:
    """Rimuove caratteri speciali per la sintesi vocale."""
    if not text: return ""
    text = _strip_non_ssml_tags(text)      # Via HTML tags, tiene SSML
    text = re.sub(r'[*_`\[\]]', '', text) # Via markdown
    text = re.sub(r'http\S+', '', text)    # Via URL
    # Via emoji/icon (preserva lettere accentate latin-1)
    text = re.sub(
        r'[\U00002100-\U000027BF'   # Simboli BMP: frecce, box drawing, geometrici, dingbats, ⏰⌨ etc.
        r'\U00002B00-\U00002BFF'    # Misc Symbols & Arrows (⬜⬆⬇⬅➡)
        r'\U00003000-\U0000303F'    # CJK Symbols (〇〒など)
        r'\U00003200-\U000032FF'    # Enclosed CJK Letters (㋀㋁㋂)
        r'\U0000FE00-\U0000FE0F'    # Variation Selectors
        r'\U0000200D'               # Zero Width Joiner
        r'\U000E0000-\U000E007F'    # Tag characters (flag subtags)
        r'\U0001F000-\U0001FBFF'    # Simboli SMP: mahjong, carte, bandiere, emoticons, trasporti, ecc.
        r'\U0001FC00-\U0001FFFF'    # Symbols Extended, compatibilità
        r']+', '', text)
    return re.sub(r'\s{2,}', ' ', text).strip()

def sanitize_text_visual(text: str, parse_mode: str) -> str:
    """Pulisce il testo in base al parse_mode del canale."""
    if not text: return ""
    mode = (parse_mode or "").lower()
    if "html" in mode:
        # HTML mode (mobile_app, telegram HTML): rimuove markdown, tiene HTML e icone
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold** → bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)         # *italic* → italic
    elif "markdown" in mode:
        # Markdown / MarkdownV2 mode (telegram): rimuove HTML, tiene markdown e icone
        text = re.sub(r'<[^>]+>', '', text)
    else:
        # plain_text o None: rimuovi marker markdown che altrimenti restano visibili
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold** → bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)         # *italic* → italic
    return text

def apply_formatting(text: str, parse_mode: str, style: str = "bold") -> str:
    """Applica la formattazione (grassetto) in base al parse_mode."""
    if not text: return ""
    mode = parse_mode.lower() if parse_mode else ""
    if "html" in mode:
        if style == "bold": return f"<b>{text}</b>"
    elif "markdownv2" in mode:
        # Telegram MarkdownV2 usa * singolo per bold
        if style == "bold": return f"*{text}*"
    elif "markdown" in mode:
        return f"**{text}**" 
    return text


def escape_markdownv2(text: str) -> str:
    """Escape caratteri speciali per Telegram MarkdownV2, preservando **bold** → *bold* e *italic*."""
    if not text: return ""
    special = r'\_[]()~`>#+=|{}.!-'
    saved = {}
    counter = [0]

    def _protect(m):
        key = f'\x00{counter[0]}\x00'
        counter[0] += 1
        inner = m.group(1)
        for ch in special:
            inner = inner.replace(ch, '\\' + ch)
        saved[key] = f'*{inner}*'
        return key

    # Protegge **bold** (→ *bold*) e *italic*
    result = re.sub(r'\*\*(.+?)\*\*', _protect, text)
    result = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', _protect, result)
    # Escape di tutti i caratteri speciali rimasti
    for ch in special:
        result = result.replace(ch, '\\' + ch)
    # Ripristina i blocchi protetti
    for key, val in saved.items():
        result = result.replace(key, val)
    return result


def strip_html(text: str) -> str:
    """Strip HTML tags from text, returning plain text."""
    return re.sub(r'<[^>]+>', '', str(text)).strip()


def is_apple_device(hass, entity_ids: list) -> bool:
    """Return True if any target notify entity belongs to an Apple (iOS) device."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for eid in (entity_ids or []):
        ent = ent_reg.async_get(eid)
        if ent and ent.device_id:
            dev = dev_reg.async_get(ent.device_id)
            if dev and (dev.manufacturer or "").lower() == "apple":
                return True
    return False


def apply_apple_notify_text_formatting(
    message: str,
    title: str | None,
) -> tuple:
    """iOS: plain text only, no HTML tags, no HA prefix, no greeting."""
    return strip_html(str(message)), strip_html(str(title)) if title else title


def apply_android_notify_text_formatting(
    message: str,
    title: str | None,
    name: str = "",
    time_str: str = "",
    greeting: str = "",
    parse_mode: str | None = None,
    use_bold_prefix: bool = True,
    skip_assistant_name: bool = False,
) -> tuple:
    """Android: HTML formatting with HA prefix [name - time] and greeting."""
    clean_name = sanitize_text_visual(name, parse_mode)
    clean_time = sanitize_text_visual(time_str, parse_mode)
    clean_msg = sanitize_text_visual(str(message), parse_mode)
    clean_greet = sanitize_text_visual(greeting, parse_mode)
    clean_orig_title = sanitize_text_visual(title, parse_mode) if title else None
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
    return final_msg, final_title


def apply_mobile_notify_text_formatting(
    message: str,
    title: str | None,
    device_type: str,
    name: str = "",
    time_str: str = "",
    greeting: str = "",
    parse_mode: str | None = None,
    use_bold_prefix: bool = True,
    skip_assistant_name: bool = False,
) -> tuple:
    """Dispatch to iOS or Android formatting based on device_type ('apple' | 'android')."""
    if device_type == "apple":
        return apply_apple_notify_text_formatting(message, title)
    return apply_android_notify_text_formatting(
        message, title, name, time_str, greeting,
        parse_mode, use_bold_prefix, skip_assistant_name,
    )


def normalize_parse_mode(parse_mode: str, srv_domain: str) -> str | None:
    """Normalizza parse_mode per il dominio di servizio specifico."""
    if not parse_mode:
        return None
    pm = parse_mode.strip()
    if srv_domain == "telegram_bot":
        low = pm.lower()
        # [0.8.1] Fix: HA ora valida parse_mode strict lowercase.
        # Valori validi: html, markdown, markdownv2, plain_text.
        # Qualsiasi altro valore → fallback a "html".
        VALID = ("html", "markdown", "markdownv2", "plain_text")
        return low if low in VALID else "html"
    else:
        return pm.lower()