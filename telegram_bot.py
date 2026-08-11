import logging
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
from html import escape
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests
import telebot
from telebot import apihelper
from telebot.apihelper import ApiTelegramException
from telebot.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_local_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_local_env()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()
GROUP_JOIN_LINK = os.getenv("GROUP_JOIN_LINK", "")
REQUIRED_CHANNELS = [c.strip() for c in os.getenv("REQUIRED_CHANNELS", "").split(",") if c.strip()]
DAILY_LIMIT = 1
CAMBODIA_TZ = timezone(timedelta(hours=7), "ICT")
DAILY_RESET_HOUR = 5
DAILY_RESET_MINUTE = 30
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UIDPASS_FILE_SETS = {
    "like": ("uidpass.json", "tokens.json"),
    "likeff": ("uidpass_likeff.json", "tokens_likeff.json"),
}
TOKEN_AUTO_REFRESH_INTERVAL = 7 * 60 * 60
AUTOLIKEFF_CHECK_INTERVAL = 60
AUTOLIKEFF_DEFAULT_BATCH = 220
AUTOLIKEFF_RUN_HOUR = 9
AUTOLIKEFF_RUN_MINUTE = 0
AUTOLIKEFF_NOTICE_HOUR = 19
AUTOLIKEFF_NOTICE_MINUTE = 0
AUTOLIKEFF_NEAR_END_THRESHOLD = AUTOLIKEFF_DEFAULT_BATCH * 3
AUTOLIKEFF_ORDER_DELAY = 30
AUTOLIKEFF_ORDERS_FILE = os.path.join(BASE_DIR, "autolikeff_orders.json")
AUTOLIKEFF_GROUPS_FILE = os.path.join(BASE_DIR, "autolikeff_groups.json")
PREMIUM_EMOJIS = [
    "6235355429237430006", "6147815573314082674", "5350427505805238170",
    "5287267357427776826", "5222447122586036397", "5224180824789770658",
    "5224663892646452625", "5224205542326557875", "5221953158397321906",
    "5309981979167463973", "5309928798882395910", "5246765089977037900",
    "5285161474833006232", "5285078504654783223", "5426918974971486256",
    "5474143948572223102", "5472057595193743789", "5472159355853888315",
    "6307665627481903641", "6088957586302831521", "6109328624777694916",
    "6109693533789096849", "6109213820301872263", "6109557847182281178",
    "6109447084270684884", "6109281659310312426", "6111423933162981989",
    "6109211870386720327", "6109655025112320594", "6123114099703287427",
    "6122990988760715630", "6123066743393881068", "6120791828066208322",
    "6221756527691173256", "6168137610507062619", "6192627406654671561",
    "6190651597144461028", "6192895915125116350", "6192532968913767492",
    "6217491333108470219", "5463071033256848094", "6235403472741603087",
    "6147565374289220368", "6147464060305676048", "6147524086768604985",
    "5449449325434266744", "6273840152980755328", "6276057176444246654",
    "6273997026661241933", "6273726078649372769", "6274007313107915274",
    "5978776771623914876", "5978686323907628843", "5852873584912896283",
    "5895297528106061174", "5895735846698487922", "5895343514320899727",
    "5913754823643107921", "5197434882321567830", "5463256910851546817",
    "5463423955014529788", "5465443379917629504", "5465465194056525619",
    "6235620067942341623", "6235717714023814969", "6235593671073339928",
    "6147617184479711380", "5346181118884331907", "5971944878815317190",
    "6132184924603554220", "6237519835056575931", "6086702706997597042",
    "6089117655438990048", "6129711392808247546", "6129732880529628243",
    "6120464813551260125", "6120726896750629340", "5312361253610475399",
    "6104631352190043951", "6123129707614441341", "6237825705447527988",
]

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is required")

if TELEGRAM_PROXY:
    apihelper.proxy = {
        "http": TELEGRAM_PROXY,
        "https": TELEGRAM_PROXY,
    }
    logger.info("Telegram proxy configured")

bot = telebot.TeleBot(BOT_TOKEN)
INSTANCE_LOCK_SOCKET = None
usage_tracker = {}
chat_title_cache = {}
seen_users_db = {}
notes_db = {}
filters_db = {}
warns_db = {}
rules_db = {}
welcome_db = {}
goodbye_db = {}
pending_template_db = {}
locked_db = {}
linkban_db = {}
spamban_db = {}
flood_db = {}
afk_db = {}
spam_track = {}
autolike_lock = threading.Lock()

MAX_WARNS = 3
FLOOD_LIMIT = 5
SPAM_LIMIT = 8
LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/|youtu\.be/|youtube\.com/|instagram\.com|facebook\.com|twitter\.com|x\.com|wa\.me|whatsapp\.com)",
    re.IGNORECASE,
)
BR_RANK_SCORES = [
    (1000, 1099, "Bronze I"),
    (1100, 1199, "Bronze II"),
    (1200, 1299, "Bronze III"),
    (1300, 1399, "Silver I"),
    (1400, 1499, "Silver II"),
    (1500, 1599, "Silver III"),
    (1600, 1724, "Gold I"),
    (1725, 1849, "Gold II"),
    (1850, 1974, "Gold III"),
    (1975, 2099, "Gold IV"),
    (2100, 2224, "Platinum I"),
    (2225, 2349, "Platinum II"),
    (2350, 2474, "Platinum III"),
    (2475, 2599, "Platinum IV"),
    (2600, 2749, "Platinum V"),
    (2750, 2899, "Diamond I"),
    (2900, 3049, "Diamond II"),
    (3050, 3199, "Diamond III"),
    (3200, 3349, "Diamond IV"),
    (3350, 3499, "Diamond V"),
    (3500, 3799, "Heroic"),
    (3800, 4299, "Heroic II"),
    (4300, 4899, "Elite Heroic III"),
    (4900, 5499, "Elite Heroic IV"),
    (5500, 6299, "Elite Heroic V"),
    (6300, 7099, "Master"),
    (7100, 7999, "Master II"),
    (8000, 8999, "Elite Master III"),
    (9000, 9999, "Elite Master IV"),
    (10000, 19999, "Elite Master V"),
    (20000, 999999, "Grand Master"),
]
CS_RANK_MAPPING = {
    301: "Bronze I",
    302: "Bronze II",
    303: "Bronze III",
    304: "Silver I",
    305: "Silver II",
    306: "Silver III",
    307: "Gold I",
    308: "Gold II",
    309: "Gold III",
    310: "Gold IV",
    311: "Platinum I",
    312: "Platinum II",
    313: "Platinum III",
    314: "Platinum IV",
    315: "Platinum V",
    316: "Diamond I",
    317: "Diamond II",
    318: "Diamond III",
    319: "Diamond IV",
    320: "Diamond V",
    321: "Heroic",
    322: "Elite Heroic",
    323: "Master",
    324: "Elite Master",
    325: "Grandmaster",
}
LEVELS = {
    1: 0,
    2: 48,
    3: 202,
    4: 544,
    5: 1012,
    6: 1844,
    7: 2792,
    8: 3800,
    9: 4870,
    10: 6004,
    11: 7192,
    12: 8448,
    13: 9776,
    14: 11140,
    15: 12566,
    16: 14060,
    17: 15610,
    18: 17224,
    19: 18902,
    20: 20632,
    21: 22424,
    22: 24728,
    23: 26192,
    24: 28166,
    25: 30200,
    26: 32294,
    27: 34448,
    28: 37804,
    29: 41174,
    30: 44870,
    31: 48852,
    32: 53334,
    33: 58566,
    34: 64096,
    35: 69994,
    36: 76460,
    37: 83108,
    38: 91128,
    39: 99322,
    40: 108092,
    41: 120144,
    42: 133266,
    43: 147472,
    44: 162760,
    45: 179126,
    46: 196572,
    47: 215368,
    48: 235516,
    49: 257010,
    50: 279860,
    51: 304056,
    52: 348318,
    53: 394982,
    54: 444044,
    55: 495508,
    56: 549364,
    57: 633756,
    58: 721744,
    59: 813336,
    60: 908522,
    61: 1041438,
    62: 1180352,
    63: 1325256,
    64: 1476184,
    65: 1634300,
    66: 1840946,
    67: 2056594,
    68: 2281242,
    69: 2514880,
    70: 2757530,
    71: 3059506,
    72: 3372284,
    73: 3699456,
    74: 4041030,
    75: 4397020,
    76: 4829104,
    77: 5282204,
    78: 5756304,
    79: 6251404,
    80: 6767504,
    81: 7381324,
    82: 8043154,
    83: 8752952,
    84: 9510808,
    85: 10316638,
    86: 11277190,
    87: 12360748,
    88: 13360304,
    89: 14482858,
    90: 15659418,
    91: 17026708,
    92: 18453688,
    93: 19941280,
    94: 21488570,
    95: 23095858,
    96: 24763138,
    97: 26490138,
    98: 28277708,
    99: 30124996,
    100: 32032284,
}


def reset_limits():
    while True:
        now = datetime.now(CAMBODIA_TZ)
        next_reset = now.replace(hour=DAILY_RESET_HOUR, minute=DAILY_RESET_MINUTE, second=0, microsecond=0)
        if now >= next_reset:
            next_reset += timedelta(days=1)
        time.sleep(max(1, (next_reset - now).total_seconds()))
        usage_tracker.clear()
        logger.info("Daily usage limits reset at %s", next_reset.strftime("%Y-%m-%d %H:%M:%S %Z"))


def usage_reset_period(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc).astimezone(CAMBODIA_TZ)
    else:
        value = value.astimezone(CAMBODIA_TZ)
    reset_time = value.replace(hour=DAILY_RESET_HOUR, minute=DAILY_RESET_MINUTE, second=0, microsecond=0)
    if value < reset_time:
        reset_time -= timedelta(days=1)
    return reset_time.date()


def chat_title(chat_ref, fallback=None):
    if chat_ref in chat_title_cache:
        return chat_title_cache[chat_ref]
    try:
        chat = bot.get_chat(chat_ref)
        title = chat.title or chat.first_name or chat.username or fallback or str(chat_ref)
        chat_title_cache[chat_ref] = title
        return title
    except Exception as exc:
        logger.warning("Could not resolve chat title for %s: %s", chat_ref, exc)
        return fallback or str(chat_ref)


def channel_url(channel):
    if str(channel).startswith("@"):
        return f"https://t.me/{channel.lstrip('@')}"
    if str(channel).startswith("-100"):
        return GROUP_JOIN_LINK or "https://t.me/"
    return f"https://t.me/{str(channel).lstrip('@')}"


def required_membership_status(user_id):
    if not REQUIRED_CHANNELS:
        return True, []
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in {"member", "administrator", "creator"}:
                missing.append(channel)
        except Exception as exc:
            logger.warning("Channel check failed for %s and user %s: %s", channel, user_id, exc)
            missing.append(channel)
    return not missing, missing


def is_user_in_channels(user_id):
    ok, _ = required_membership_status(user_id)
    return ok


def join_markup(missing_channels=None):
    markup = InlineKeyboardMarkup()
    channels = missing_channels if missing_channels is not None else REQUIRED_CHANNELS
    for channel in channels:
        title = chat_title(channel, channel)
        markup.add(InlineKeyboardButton(f"Join {title}", url=channel_url(channel)))
    if GROUP_JOIN_LINK:
        markup.add(InlineKeyboardButton("Join Group", url=GROUP_JOIN_LINK))
    markup.add(InlineKeyboardButton("Try again", callback_data="verify_join"))
    return markup


def get_user_limit(user_id):
    return 999999999 if OWNER_ID and user_id == OWNER_ID else DAILY_LIMIT


def acquire_bot_instance_lock():
    global INSTANCE_LOCK_SOCKET
    lock_port = int(os.getenv("BOT_INSTANCE_LOCK_PORT", "47891"))
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        lock_socket.bind(("127.0.0.1", lock_port))
        lock_socket.listen(1)
    except OSError:
        lock_socket.close()
        logger.error("Another telegram_bot.py instance is already running. Stop the old bot before starting a new one.")
        return False
    INSTANCE_LOCK_SOCKET = lock_socket
    return True


def call_api(endpoint, params, timeout=120):
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.Timeout:
        return {"success": False, "error": f"API timeout after {timeout} seconds"}
    except requests.RequestException as exc:
        return {"success": False, "error": str(exc)}
    try:
        data = response.json()
    except ValueError:
        data = {"success": False, "error": response.text[:300] or "Invalid API response"}
    if response.status_code >= 400 and "error" not in data:
        data["error"] = f"API returned HTTP {response.status_code}"
    return data


def cached_region_for_uid(uid):
    cache = read_json_file(os.path.join(BASE_DIR, "regions.json"), {})
    item = cache.get(str(uid))
    if isinstance(item, dict):
        region = item.get("region") or item.get("Region")
    else:
        region = item
    return str(region).upper() if region else None


def resolve_like_region(uid, requested_region=None):
    cached_region = cached_region_for_uid(uid)
    if cached_region:
        return cached_region, "cache"
    if requested_region:
        data = call_api("check-region", {"uid": uid}, timeout=180)
        if "error" in data:
            error_text = str(data.get("error") or "")
            if "timeout" in error_text.lower() or "timed out" in error_text.lower():
                return None, "timeout"
            return None, "not_found"
        detected = data.get("Region") or data.get("region")
        if detected:
            return str(detected).upper(), "check-region"
        return None, "not_found"
    return None, "auto"


def utf16_len(text):
    return len(str(text).encode("utf-16-le")) // 2


def is_emoji_char(char):
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x2300 <= code <= 0x23FF
        or code in {0x00A9, 0x00AE, 0x3030, 0x303D, 0x3297, 0x3299}
    )


def premiumize_text(text):
    if not PREMIUM_EMOJIS:
        return text, None
    output = []
    entities = []
    offset = 0
    skip_joined = False
    for char in str(text):
        code = ord(char)
        if code in {0xFE0E, 0xFE0F}:
            continue
        if code == 0x200D:
            skip_joined = True
            continue
        if is_emoji_char(char):
            if skip_joined and output:
                skip_joined = False
                continue
            placeholder = "✨"
            output.append(placeholder)
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=offset,
                    length=utf16_len(placeholder),
                    custom_emoji_id=random.choice(PREMIUM_EMOJIS),
                )
            )
            offset += utf16_len(placeholder)
            skip_joined = False
            continue
        output.append(char)
        offset += utf16_len(char)
        skip_joined = False
    return "".join(output), entities or None


def send_premium_message(chat_id, text, **kwargs):
    premium_text, entities = premiumize_text(text)
    kwargs.pop("parse_mode", None)
    try:
        return bot.send_message(chat_id, premium_text, entities=entities, parse_mode=None, **kwargs)
    except ApiTelegramException as exc:
        logger.warning("Premium emoji send failed, falling back: %s", exc)
        return bot.send_message(chat_id, text, parse_mode=None, **kwargs)


def reply_premium(message, text, **kwargs):
    kwargs["reply_to_message_id"] = message.message_id
    return send_premium_message(message.chat.id, text, **kwargs)


def edit_premium_message(chat_id, message_id, text, **kwargs):
    premium_text, entities = premiumize_text(text)
    kwargs.pop("parse_mode", None)
    try:
        return bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=premium_text,
            entities=entities,
            parse_mode=None,
            **kwargs,
        )
    except ApiTelegramException as exc:
        logger.warning("Premium emoji edit failed, falling back: %s", exc)
        return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=None, **kwargs)


def uidpass_path(set_name):
    if set_name not in UIDPASS_FILE_SETS:
        return None
    return os.path.join(BASE_DIR, UIDPASS_FILE_SETS[set_name][0])


def token_path(set_name):
    if set_name not in UIDPASS_FILE_SETS:
        return None
    return os.path.join(BASE_DIR, UIDPASS_FILE_SETS[set_name][1])


def load_uidpass(set_name):
    path = uidpass_path(set_name)
    if not path:
        raise ValueError("Unknown set. Use like or likeff.")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as uidpass_file:
        data = json.load(uidpass_file)
    if not isinstance(data, list):
        raise ValueError(f"{os.path.basename(path)} must contain a JSON list.")
    return data


def save_uidpass(set_name, accounts):
    path = uidpass_path(set_name)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as uidpass_file:
        json.dump(accounts, uidpass_file, ensure_ascii=False, indent=4)
    os.replace(tmp_path, path)


def find_uidpass_index(accounts, uid):
    uid = str(uid)
    for index, account in enumerate(accounts):
        if str(account.get("uid")) == uid:
            return index
    return -1


def run_token_update(set_name):
    command = [sys.executable, os.path.join(BASE_DIR, "update_like_tokens.py"), set_name]
    result = subprocess.run(command, cwd=BASE_DIR, capture_output=True, text=True, timeout=900)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def run_single_token_update(set_name, uid, password):
    command = [sys.executable, os.path.join(BASE_DIR, "update_like_tokens.py"), set_name, str(uid), str(password)]
    result = subprocess.run(command, cwd=BASE_DIR, capture_output=True, text=True, timeout=180)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def load_token_list(set_name):
    path = token_path(set_name)
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as token_file:
        data = json.load(token_file)
    return data if isinstance(data, list) else []


def region_counts(tokens):
    counts = {}
    for item in tokens:
        if not isinstance(item, dict):
            continue
        region = str(item.get("region") or item.get("Region") or "UNKNOWN").upper()
        counts[region] = counts.get(region, 0) + 1
    return counts


def read_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as data_file:
            data = json.load(data_file)
        return data if isinstance(data, type(default)) else default
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return default


def write_json_file(path, data):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as data_file:
        json.dump(data, data_file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def load_autolike_groups():
    groups = read_json_file(AUTOLIKEFF_GROUPS_FILE, [])
    return [str(group_id) for group_id in groups]


def save_autolike_groups(groups):
    write_json_file(AUTOLIKEFF_GROUPS_FILE, sorted({str(group_id) for group_id in groups}, key=str))


def load_autolike_orders():
    return read_json_file(AUTOLIKEFF_ORDERS_FILE, [])


def save_autolike_orders(orders):
    write_json_file(AUTOLIKEFF_ORDERS_FILE, orders)


def merge_save_autolike_orders(updated_orders):
    current_orders = load_autolike_orders()
    current_by_id = {str(order.get("order_id")): order for order in current_orders}
    for order in updated_orders:
        order_id = str(order.get("order_id"))
        if order_id:
            if order.get("remove_after_save"):
                current_by_id.pop(order_id, None)
            else:
                current_by_id[order_id] = order
    merged = list(current_by_id.values())
    merged.sort(key=lambda order: int(order.get("order_id", 0) or 0))
    save_autolike_orders(merged)


def next_autolike_order_id(orders):
    max_id = 0
    for order in orders:
        try:
            max_id = max(max_id, int(order.get("order_id", 0)))
        except (TypeError, ValueError):
            continue
    return str(max_id + 1)


def current_reset_period():
    return usage_reset_period(datetime.now(CAMBODIA_TZ)).isoformat()


def autolike_run_datetime(value=None):
    value = value or datetime.now(CAMBODIA_TZ)
    return value.replace(hour=AUTOLIKEFF_RUN_HOUR, minute=AUTOLIKEFF_RUN_MINUTE, second=0, microsecond=0)


def next_autolike_run_date(value=None):
    value = value or datetime.now(CAMBODIA_TZ)
    run_time = autolike_run_datetime(value)
    if value >= run_time:
        run_time += timedelta(days=1)
    return run_time.date().isoformat()


def current_autolike_period(value=None):
    value = value or datetime.now(CAMBODIA_TZ)
    return value.date().isoformat()


def autolike_group_allowed(chat_id):
    return str(chat_id) in set(load_autolike_groups())


def resolve_autolike_group_id(message):
    allowed_groups = load_autolike_groups()
    current_chat_id = str(message.chat.id)
    if current_chat_id in allowed_groups:
        return current_chat_id
    if allowed_groups:
        return allowed_groups[0]
    if message.chat.type in {"group", "supergroup"}:
        return current_chat_id
    return ""


def can_manage_autolike(message):
    if is_owner(message.from_user.id):
        return True
    if message.chat.type not in {"group", "supergroup"}:
        return False
    return autolike_group_allowed(message.chat.id) and is_admin(message.chat.id, message.from_user.id)


def autolike_order_status(order):
    sent = int(order.get("sent_likes", 0) or 0)
    total = int(order.get("total_likes", 0) or 0)
    remaining = total - sent
    return sent, total, remaining


def format_autolike_order(order, title="✅ AUTOLIKEFF ORDER CREATED"):
    sent, total, remaining = autolike_order_status(order)
    telegram_user = telegram_user_display(order.get("telegram_user_id"), html=True)
    return "\n".join([
        title,
        "━━━━━━━━━━━━━━━━━━",
        f"🧾 Order ID: {order.get('order_id', 'N/A')}",
        f"🆔 UID: {order.get('uid', 'N/A')}",
        f"👤 Telegram User: {telegram_user}",
        f"🎯 Total Likes: {total:,}",
        f"✅ Delivered: {sent:,}",
        f"⏳ Remaining: {max(0, remaining):,}",
        f"📌 Status: {order.get('status', 'active')}",
        f"🕘 Next Run: {order.get('next_run_date', 'N/A')} {AUTOLIKEFF_RUN_HOUR:02d}:{AUTOLIKEFF_RUN_MINUTE:02d} Cambodia",
    ])


def format_autolike_list(orders):
    if not orders:
        return "ℹ️ AUTOLIKEFF ORDERS\n━━━━━━━━━━━━━━━━━━\nNo AutoLikeFF orders found."
    lines = [
        "📋 AUTOLIKEFF ORDER LIST",
        "━━━━━━━━━━━━━━━━━━",
        f"📦 Total Orders: {len(orders)}",
    ]
    for order in orders:
        sent, total, remaining = autolike_order_status(order)
        lines.extend([
            "",
            f"🧾 Order ID: {order.get('order_id', 'N/A')}",
            f"🆔 UID: {order.get('uid', 'N/A')}",
            f"👤 Telegram User: {telegram_user_display(order.get('telegram_user_id'))}",
            f"🎯 Total Likes: {total:,}",
            f"✅ Delivered: {sent:,}",
            f"⏳ Remaining: {max(0, remaining):,}",
        ])
        if order.get("last_error"):
            lines.append(f"⚠️ Last Error: {order.get('last_error')}")
    return "\n".join(lines)


def format_autolike_summary(orders):
    total_orders = len(orders)
    completed_orders = sum(1 for order in orders if order.get("status") == "completed")
    total_likes = 0
    delivered_likes = 0
    remaining_likes = 0
    for order in orders:
        sent, total, remaining = autolike_order_status(order)
        total_likes += total
        delivered_likes += sent
        remaining_likes += max(0, remaining)
    progress = (delivered_likes / total_likes * 100) if total_likes > 0 else 0
    return "\n".join([
        "📊 AUTOLIKEFF SUMMARY",
        "━━━━━━━━━━━━━━━━━━",
        f"📦 Total Orders: {total_orders}",
        f"🏁 Completed Orders: {completed_orders}",
        "",
        f"🎯 Total Likes Ordered: {total_likes:,}",
        f"✅ Total Delivered: {delivered_likes:,}",
        f"⏳ Total Remaining: {remaining_likes:,}",
        f"📈 Progress: {progress:.2f}%",
        "",
        f"🕘 Daily Run: {AUTOLIKEFF_RUN_HOUR:02d}:{AUTOLIKEFF_RUN_MINUTE:02d} Cambodia",
        f"⏱ Delay Between Orders: {AUTOLIKEFF_ORDER_DELAY}s",
    ])


def autolike_purchase_date(order):
    raw = str(order.get("created_at") or "")
    for fmt in ("%d %b %Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw.split()[0] if raw else "N/A"


def format_my_autolike_orders(user, orders):
    full_name = requester_name(user)
    user_orders = [
        order for order in orders
        if str(order.get("telegram_user_id")) == str(user.id)
        and order.get("status", "active") == "active"
        and autolike_order_status(order)[2] > 0
    ]
    if not user_orders:
        owner_contact = owner_contact_text()
        return "\n".join([
            f"👋 Hello {full_name}",
            "",
            "❌ You don't have any autolike tasks!",
            f"🚀 Contact {owner_contact} to renew AutoLikeFF.",
        ])

    lines = [
        f"👋 Hello {full_name}",
        "",
        "📦 Your AutoLikeFF Details",
        "━━━━━━━━━━━━━━━━━━",
    ]
    for index, order in enumerate(user_orders, 1):
        sent, total, remaining = autolike_order_status(order)
        progress = (sent / total * 100) if total > 0 else 0
        lines.extend([
            "",
            f"#{index}",
            f"🆔 UID: {order.get('uid', 'N/A')}",
            f"👤 Player: {order.get('player_name') or 'N/A'}",
            f"👍 Likes Before Purchase: {fmt_num(order.get('likes_before_purchase'))}",
            f"🎯 Likes Purchased: {total:,}",
            f"📅 Purchase Date: {autolike_purchase_date(order)}",
            f"✅ Likes Given By Bot: {sent:,}",
            f"📈 Progress: {progress:.2f}%",
            f"⏳ Remaining: {max(0, remaining):,}",
        ])
    return "\n".join(lines)


def telegram_name_by_id(user_id):
    try:
        chat = bot.get_chat(int(user_id))
        first_name = getattr(chat, "first_name", None) or ""
        last_name = getattr(chat, "last_name", None) or ""
        full_name = " ".join(part for part in (first_name, last_name) if part).strip()
        name = full_name or getattr(chat, "title", None) or getattr(chat, "username", None)
        if name:
            return name
    except Exception:
        pass
    return str(user_id or "User")


def telegram_user_display(user_id, html=False):
    try:
        chat = bot.get_chat(int(user_id))
        first_name = getattr(chat, "first_name", None) or ""
        last_name = getattr(chat, "last_name", None) or ""
        full_name = " ".join(part for part in (first_name, last_name) if part).strip()
        username = getattr(chat, "username", None)
        label = full_name or (f"@{username}" if username else str(user_id))
        if html and username:
            return f'<a href="https://t.me/{escape(username)}">{escape(label)}</a>'
        if html:
            return escape(label)
        return label
    except Exception:
        return escape(str(user_id or "User")) if html else str(user_id or "User")


def autolike_progress_values(order, likes_sent):
    sent, total, remaining = autolike_order_status(order)
    progress = (sent / total * 100) if total > 0 else 0
    return sent, total, remaining, progress


def infer_region_from_error(error_text):
    text = str(error_text or "")
    match = re.search(r"client\.([a-z]+)\.freefiremobile\.com", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r"Unsupported region:\s*([A-Z]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "N/A"


def format_autolike_delivery(order, data, likes_sent, private=False):
    sent, total, remaining, progress = autolike_progress_values(order, likes_sent)
    player = data.get("PlayerNickname") or "N/A"
    uid = data.get("UID") or order.get("uid", "N/A")
    title_name = "Your" if private else f"{telegram_name_by_id(order.get('telegram_user_id'))}"
    return "\n".join([
        f"💎 {title_name} Daily AutoLike Update",
        "",
        f"🆔 UID: {uid}",
        f"👤 Player: {player}",
        "",
        "📊 Progress",
        f"👍 Likes Before: {data.get('LikesbeforeCommand', 'N/A')}",
        f"➕ Likes Added: {likes_sent:,}",
        f"❤️ Current Likes: {data.get('LikesafterCommand', 'N/A')}",
        f"🎯 Total Delivered: {sent}/{total}",
        "",
        "📌 Status",
        f"📈 Progress: {progress:.2f}%",
        f"⏳ Remaining: {max(0, remaining)}",
    ])


def notify_autolike_order(order, group_text, private_text=None):
    group_id = order.get("group_id")
    if group_id:
        try:
            bot.send_message(int(group_id), group_text, parse_mode=None)
        except Exception as exc:
            logger.warning("Autolike group notify failed for %s: %s", group_id, exc)


def find_existing_autolike_order(orders, uid):
    uid = str(uid)
    for order in orders:
        if str(order.get("uid")) != uid or order.get("status") == "cancelled":
            continue
        sent, total, remaining = autolike_order_status(order)
        if remaining > 0 or order.get("status") == "active":
            return order
    return None


def deliver_autolikeff_order(order, period=None, schedule_next=True, notify_failure=True):
    now = datetime.now(CAMBODIA_TZ)
    period = period or current_autolike_period(now)
    sent, total, remaining = autolike_order_status(order)
    if remaining <= 0:
        order["status"] = "completed"
        order["next_run_date"] = ""
        return True

    uid = str(order.get("uid") or "")
    if not uid.isdigit():
        order["last_error"] = "Invalid UID"
        order["last_attempt_period"] = period
        if schedule_next:
            order["next_run_date"] = (now + timedelta(days=1)).date().isoformat()
        return False

    data = call_api("likeff", {"uid": uid}, timeout=240)
    error_text = str(data.get("error") or "")
    if not data.get("success") and ("401" in error_text or "Unauthorized" in error_text):
        logger.info("AutoLikeFF auth error for UID %s; refreshing likeff tokens and retrying once", uid)
        run_token_update("likeff")
        data = call_api("likeff", {"uid": uid}, timeout=240)
    order["last_attempt_period"] = period
    order["last_run_at"] = now.strftime("%d %b %Y %H:%M:%S")

    if not data.get("success") or data.get("error"):
        raw_error = data.get("error") or "LikeFF request failed"
        order["last_error"] = "This region is not support"
        if notify_failure:
            region = data.get("Region") or order.get("region") or infer_region_from_error(raw_error)
            notify_autolike_order(
                order,
                "\n".join([
                    "❌ AUTOLIKEFF DELIVERY FAILED",
                    "━━━━━━━━━━━━━━━━━━",
                    f"🧾 Order ID: {order.get('order_id', 'N/A')}",
                    f"🆔 UID: {uid}",
                    f"🌍 Region: {region}",
                    f"📌 Error: {order['last_error']}",
                ]),
            )
        if schedule_next:
            order["next_run_date"] = (now + timedelta(days=1)).date().isoformat()
        return False

    try:
        likes_sent = int(data.get("LikesGivenByAPI", 0) or 0)
    except (TypeError, ValueError):
        likes_sent = 0
    credited_likes = max(0, likes_sent)
    if not order.get("player_name") and data.get("PlayerNickname"):
        order["player_name"] = data.get("PlayerNickname")
    if not order.get("likes_before_purchase"):
        order["likes_before_purchase"] = data.get("LikesbeforeCommand")
    order["current_likes"] = data.get("LikesafterCommand")
    order["region"] = data.get("Region") or order.get("region")
    order["sent_likes"] = sent + credited_likes
    order["last_period"] = period
    order["last_error"] = ""
    if order["sent_likes"] >= total:
        order["status"] = "completed"
        order["next_run_date"] = ""
        order["remove_after_save"] = True
    elif schedule_next:
        order["next_run_date"] = (now + timedelta(days=1)).date().isoformat()

    notify_autolike_order(
        order,
        format_autolike_delivery(order, data, credited_likes, private=False),
        format_autolike_delivery(order, data, credited_likes, private=True),
    )
    return True


def deliver_autolikeff_order_now(order_id):
    with autolike_lock:
        orders = load_autolike_orders()
    target_order = None
    for order in orders:
        if str(order.get("order_id")) == str(order_id):
            target_order = order
            break
    if not target_order:
        return
    deliver_autolikeff_order(target_order, period=current_autolike_period(), schedule_next=True)
    with autolike_lock:
        merge_save_autolike_orders([target_order])


def check_access(message):
    user_id = message.from_user.id
    if message.chat.type == "private" and user_id != OWNER_ID:
        bot.reply_to(message, "⚠️ Group access required.\n📌 Use this bot in the official group.", reply_markup=join_markup(), parse_mode=None)
        return False
    ok, missing = required_membership_status(user_id)
    if not ok:
        bot.reply_to(message, "⚠️ Join required.\n📌 You must join the required channel(s) first.", reply_markup=join_markup(missing), parse_mode=None)
        return False
    return True


def is_owner(user_id):
    return bool(OWNER_ID and user_id == OWNER_ID)


def is_admin(chat_id, user_id):
    if is_owner(user_id):
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False


def require_admin(message):
    if message.chat.type == "private":
        bot.reply_to(message, "⚠️ Group command only.\n📌 This command works in groups.", parse_mode=None)
        return False
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ Admin-only action.", parse_mode=None)
        return False
    return True


def split_command(message, maxsplit=2):
    return (message.text or "").split(maxsplit=maxsplit)


def get_target_user(message):
    remember_user(message.from_user)
    if message.reply_to_message:
        replied_user = getattr(message.reply_to_message, "from_user", None)
        if replied_user:
            remember_user(replied_user)
            return replied_user
        sender_chat = getattr(message.reply_to_message, "sender_chat", None)
        if sender_chat:
            return SimpleNamespace(
                id=sender_chat.id,
                first_name=sender_chat.title or str(sender_chat.id),
                username=getattr(sender_chat, "username", None),
                is_bot=False,
            )
        return SimpleNamespace(id=None, first_name="Unknown", username=None, is_bot=False)
    parts = split_command(message, 1)
    if len(parts) < 2:
        return None
    raw = parts[1].split()[0].strip()
    if raw.isdigit():
        try:
            return bot.get_chat_member(message.chat.id, int(raw)).user
        except Exception:
            return SimpleNamespace(id=int(raw), first_name=raw, username=None)
    if raw.startswith("@"):
        seen_user = seen_users_db.get(raw.lower().lstrip("@"))
        if seen_user:
            return seen_user
        try:
            chat = bot.get_chat(raw)
            return SimpleNamespace(
                id=chat.id,
                first_name=chat.first_name or chat.title or raw,
                username=chat.username,
                is_bot=False,
            )
        except Exception:
            return SimpleNamespace(id=None, first_name=raw, username=raw.lstrip("@"), is_bot=False)
    return None


def remember_user(user):
    if not user:
        return
    username = getattr(user, "username", None)
    if username:
        seen_users_db[username.lower()] = SimpleNamespace(
            id=user.id,
            first_name=getattr(user, "first_name", "") or getattr(user, "full_name", "") or username,
            username=username,
            is_bot=getattr(user, "is_bot", False),
        )


def raw_reply_user(message):
    raw_reply = getattr(message, "json", {}).get("reply_to_message") if hasattr(message, "json") else None
    if not isinstance(raw_reply, dict):
        return None, None
    raw_from = raw_reply.get("from")
    if isinstance(raw_from, dict):
        username = raw_from.get("username")
        return SimpleNamespace(
            id=raw_from.get("id"),
            first_name=raw_from.get("first_name") or raw_from.get("last_name") or str(raw_from.get("id")),
            username=username,
            is_bot=raw_from.get("is_bot", False),
        ), None
    raw_sender_chat = raw_reply.get("sender_chat")
    if isinstance(raw_sender_chat, dict):
        return None, SimpleNamespace(
            id=raw_sender_chat.get("id"),
            title=raw_sender_chat.get("title") or str(raw_sender_chat.get("id")),
            username=raw_sender_chat.get("username"),
        )
    return None, None


def user_label(user):
    if not user:
        return "Unknown"
    name = getattr(user, "first_name", None) or getattr(user, "username", None) or str(user.id)
    return f"{name} ({user.id})"


def requester_name(user):
    if not user:
        return "N/A"
    first_name = getattr(user, "first_name", None) or ""
    last_name = getattr(user, "last_name", None) or ""
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return full_name or getattr(user, "username", None) or str(getattr(user, "id", "N/A"))


def parse_duration(value):
    if not value:
        return None
    match = re.fullmatch(r"(\d+)([mhd])", value.lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    return timedelta(days=amount)


def muted_permissions():
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


def normal_permissions():
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


def safe_delete(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
        return True
    except Exception:
        return False


def safe_reply(message, text, **kwargs):
    try:
        return bot.reply_to(message, text, **kwargs)
    except ApiTelegramException as exc:
        logger.error("Telegram send failed: %s", exc)
        return None


def warn_user(chat_id, user, reason="No reason"):
    key = (chat_id, user.id)
    warns_db[key] = warns_db.get(key, 0) + 1
    count = warns_db[key]
    if count >= MAX_WARNS:
        bot.ban_chat_member(chat_id, user.id)
        warns_db[key] = 0
        return f"🚫 {user_label(user)} has been banned after {MAX_WARNS} warnings."
    return f"⚠️ {user_label(user)} warned ({count}/{MAX_WARNS}).\n📌 Reason: {reason}"


@bot.message_handler(commands=["start"])
def start_command(message):
    ok, missing = required_membership_status(message.from_user.id)
    if not ok:
        bot.reply_to(message, "⚠️ Join the required channel(s) first, then press Try again.", reply_markup=join_markup(missing))
        return
    markup = InlineKeyboardMarkup()
    try:
        username = bot.get_me().username
        markup.add(InlineKeyboardButton("Add to Group", url=f"https://t.me/{username}?startgroup=true"))
    except Exception:
        pass
    markup.add(InlineKeyboardButton("Commands", callback_data="help_main"))
    bot.reply_to(
        message,
        f"✅ Ready, {message.from_user.first_name}.\n📌 Use /help for all commands or /ffinfo <uid> for Free Fire info.",
        reply_markup=markup,
        parse_mode=None,
    )


@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    ok, missing = required_membership_status(call.from_user.id)
    if ok:
        bot.answer_callback_query(call.id, "✅ Verified")
        bot.edit_message_text(
            "✅ Verification complete. You can use the bot now.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        return
    bot.answer_callback_query(call.id, "⚠️ Not verified yet. Join all required chats first.", show_alert=True)
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=join_markup(missing),
    )


@bot.callback_query_handler(func=lambda call: call.data == "help_main")
def help_callback(call):
    bot.answer_callback_query(call.id)
    help_text = build_help_text(call.message.chat.id, call.from_user.id)
    bot.send_message(call.message.chat.id, help_text, parse_mode=None)


@bot.message_handler(commands=["help"])
def help_command(message):
    safe_reply(message, build_help_text(message.chat.id, message.from_user.id), parse_mode=None)


def build_help_text(chat_id=None, user_id=None):
    try:
        bot_name = bot.get_me().first_name
    except Exception:
        bot_name = "Bot"
    admin_view = bool(chat_id and user_id and is_admin(chat_id, user_id))
    lines = [
        f"📖 {bot_name} COMMAND CENTER",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "🎮 FREE FIRE",
        "━━━━━━━━━━━━━━━━━━",
        "❤️ /like <uid> - Send likes to a player",
        "💎 /likeff <uid> - Send premium like",
        "👤 /ffinfo <uid> - View full player profile",
        "📊 /level <uid> - Check level EXP progress",
        "🌍 /region <uid> - Check player region",
        "📦 /myautolike - View your AutoLikeFF orders",
        "📝 /bio <access_token|jwt|uidpass> <new_bio> - Update profile bio",
    ]
    if is_owner(user_id):
        lines.extend([
            "🎟 /jwt <uid> <password> - Generate/check JWT token",
            "🧾 /guestgen <region> <name> [total] - Create guest account(s)",
            "💎 /autolikeff <uid> <total_likes> <telegram_user_id> - Create AutoLikeFF order",
            "📋 /autolikeff ls - List AutoLikeFF orders",
            "📊 /autolikeff summary - View AutoLikeFF totals",
            "🗑 /autolikeff del <uid> - Remove AutoLikeFF order",
            "➕ /extend <uid> <extra_likes> - Extend AutoLikeFF order",
            "🏷 /autolikegroup <set|del|ls> [group_id] - Manage AutoLikeFF groups",
            "📦 /uidpass <ls|add|set|del|up> - Manage like accounts",
            "📦 /uidpassff <ls|add|set|del|up> - Manage likeff accounts",
            "⏳ /remain - Check daily request usage",
        ])
    if admin_view:
        lines.extend([
            "",
            "🛡 ADMIN COMMANDS",
            "━━━━━━━━━━━━━━━━━━",
            "🚫 /ban, /unban, /kick, /tban",
            "🔇 /mute, /unmute, /tmute",
            "👮 /promote, /demote",
            "📌 /pin, /unpin, /unpinall",
            "🧹 /purge, /del, /echo <text>",
            "",
            "⚠️ WARN SYSTEM",
            "━━━━━━━━━━━━━━━━━━",
            "⚠️ /warn, /unwarn, /warns, /resetwarns",
            "",
            "📝 NOTES",
            "━━━━━━━━━━━━━━━━━━",
            "💾 /save <name> <text>",
            "📄 /get <name>, #notename, /notes",
            "🗑 /clear <name>, /clearall",
            "",
            "🔎 FILTERS",
            "━━━━━━━━━━━━━━━━━━",
            "➕ /filter <word> <reply>",
            "📋 /filters, /stop <word>, /stopall",
            "",
            "📜 RULES",
            "━━━━━━━━━━━━━━━━━━",
            "⚙️ /setrules <text>, /rules, /clearrules",
            "",
            "👋 WELCOME / GOODBYE",
            "━━━━━━━━━━━━━━━━━━",
            "✅ /setwelcome <text>, /welcome, /clearwelcome",
            "✅ /setgoodbye <text>, /goodbye, /cleargoodbye",
            "",
            "🔐 PROTECTION",
            "━━━━━━━━━━━━━━━━━━",
            "🔒 /lock, /unlock, /lockall, /unlockall, /locks",
            "🔗 /linkban, /linkban on, /linkban off",
            "🚫 /spamban, /spamban on, /spamban off",
            "🌊 /setflood <n>, /flood, /noflood",
            "",
            "🌙 AFK",
            "━━━━━━━━━━━━━━━━━━",
            "💤 /afk <reason>, /brb <reason>",
        ])
    if is_owner(user_id):
        lines.extend([
            "",
            "👑 OWNER INFO",
            "━━━━━━━━━━━━━━━━━━",
            "🆔 /id, /info, /tginfo",
            "👮 /adminlist, /chatinfo",
            "📊 /stats, /owner",
            "🚨 /report - reply to message",
            "",
            "🧰 OWNER UTILITY",
            "━━━━━━━━━━━━━━━━━━",
            "🏓 /ping",
            "🕒 /time",
            "🧮 /calc <math>",
        ])
    return "\n".join(lines)


def process_like(message, endpoint, uid, region=None):
    user_id = message.from_user.id
    now = datetime.now(CAMBODIA_TZ)
    usage = usage_tracker.get(user_id, {"used": 0, "last_used": now - timedelta(days=1)})
    if usage_reset_period(now) > usage_reset_period(usage["last_used"]):
        usage["used"] = 0

    limit = get_user_limit(user_id)
    if usage["used"] >= limit:
        bot.reply_to(message, "⛔ Daily request limit reached.\n━━━━━━━━━━━━━━━━━━\n📌 Please try again tomorrow.", parse_mode=None)
        return

    status_msg = bot.reply_to(
        message,
        "⏳ Processing like request...",
        parse_mode=None,
    )
    resolved_region, region_source = resolve_like_region(uid, region)
    if region and not resolved_region:
        error_text = "Request timeout. Please try again later." if region_source == "timeout" else "User not found or region is incorrect."
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ LIKE REQUEST FAILED\n━━━━━━━━━━━━━━━━━━\n{error_text}",
            parse_mode=None,
        )
        return
    params = {"uid": uid}
    if resolved_region:
        params["region"] = resolved_region
    data = call_api(endpoint, params)
    if not data.get("success") or "error" in data:
        error_text = str(data.get("error") or "Request failed")
        if (
            "Client error" in error_text
            or "Bad Request" in error_text
            or "GetPlayerPersonalShow" in error_text
            or "developer.mozilla.org" in error_text
            or "UID not found" in error_text
        ):
            error_text = "User not found or region is incorrect."
        elif "timeout" in error_text.lower() or "timed out" in error_text.lower():
            error_text = "Request timeout. Please try again later."
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ LIKE REQUEST FAILED\n━━━━━━━━━━━━━━━━━━\n{error_text}",
            parse_mode=None,
        )
        return

    try:
        likes_added = int(data.get("LikesGivenByAPI", 0) or 0)
    except (TypeError, ValueError):
        likes_added = 0
    if likes_added <= 0:
        owner_contact = owner_contact_text()
        text = "\n".join([
            "⚠️ UID Already Reached Max Likes For Now.",
            "━━━━━━━━━━━━━━━━━━",
            f"👤 Name: {data.get('PlayerNickname', 'N/A')}",
            f"🆔 UID: {data.get('UID', uid)}",
            f"🌍 Region: {data.get('Region', 'N/A')}",
            f"👍 Likes Before: {data.get('LikesbeforeCommand', 'N/A')}",
            f"➕ Likes Added: {likes_added}",
            f"❤️ Total Now: {data.get('LikesafterCommand', 'N/A')}",
            "━━━━━━━━━━━━━━━━━━",
            "💥 Daily 220 Likes!",
            f"🚀 Contact {owner_contact} to purchase Likes.",
        ])
        bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text, parse_mode=None)
        return

    usage["used"] += 1
    usage["last_used"] = now
    usage_tracker[user_id] = usage

    owner_contact = owner_contact_text()
    text = "\n".join([
        "✅ Like Request Processed Successfully",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 Name: {data.get('PlayerNickname', 'N/A')}",
        f"🆔 UID: {data.get('UID', uid)}",
        f"🌍 Region: {data.get('Region', 'N/A')}",
        f"👍 Likes Before: {data.get('LikesbeforeCommand', 'N/A')}",
        f"➕ Likes Added: {likes_added}",
        f"❤️ Total Now: {data.get('LikesafterCommand', 'N/A')}",
        f"📌 Requests Left: {'∞' if limit >= 999999 else limit - usage['used']}",
        "━━━━━━━━━━━━━━━━━━",
        "💥 Daily 220 Likes!",
        f"🚀 Contact {owner_contact} to purchase Likes.",
    ])
    bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text, parse_mode=None)


def handle_like_command(message, endpoint):
    if not check_access(message):
        return
    args = message.text.split()
    usage = "\n".join([
        "ℹ️ Usage:",
        f"• /{endpoint} <uid>",
        f"• /{endpoint} <region> <uid>",
    ])
    if len(args) == 2:
        region = None
        uid = args[1]
    elif len(args) == 3:
        region = args[1].upper()
        uid = args[2]
    else:
        bot.reply_to(message, usage, parse_mode=None)
        return
    if not uid.isdigit():
        bot.reply_to(message, f"⚠️ Invalid UID.\n━━━━━━━━━━━━━━━━━━\n{usage}", parse_mode=None)
        return
    threading.Thread(target=process_like, args=(message, endpoint, uid, region), daemon=True).start()


def pick(data, *keys, default="N/A"):
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def fmt_num(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value) if value not in (None, "") else "N/A"


def fmt_date(value):
    try:
        ts = int(value)
        if ts <= 0:
            return "N/A"
        return datetime.fromtimestamp(ts).strftime("%d %b %Y")
    except (TypeError, ValueError, OSError):
        return "N/A"


def fmt_datetime(value):
    try:
        ts = int(value)
        if ts <= 0:
            return "N/A"
        return datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return datetime.now().strftime("%d %b %Y %H:%M:%S")


def br_rank_name(points):
    try:
        points = int(points)
    except (TypeError, ValueError):
        return "N/A"
    for min_points, max_points, name in BR_RANK_SCORES:
        if min_points <= points <= max_points:
            return name
    return "N/A"


def cs_rank_name(rank_id):
    try:
        return CS_RANK_MAPPING.get(int(rank_id), "N/A")
    except (TypeError, ValueError):
        return "N/A"


def level_progress(level, exp):
    try:
        level = int(level)
        exp = int(exp)
    except (TypeError, ValueError):
        return "N/A", "N/A"
    current_level_exp = LEVELS.get(level)
    next_level_exp = LEVELS.get(level + 1)
    if current_level_exp is None or next_level_exp is None:
        return "100%" if level >= max(LEVELS) else "N/A", "0" if level >= max(LEVELS) else "N/A"
    level_span = max(1, next_level_exp - current_level_exp)
    gained = max(0, min(exp - current_level_exp, level_span))
    progress = (gained / level_span) * 100
    needed = max(0, next_level_exp - exp)
    return f"{progress:.2f}%", needed


def level_progress_details(level, exp):
    try:
        level = int(level)
        exp = int(exp)
    except (TypeError, ValueError):
        return {
            "next_level": "N/A",
            "needed": "N/A",
            "gained": 0,
            "span": 0,
            "percent": 0,
            "bar": "⬜" * 10,
        }
    current_level_exp = LEVELS.get(level)
    next_level_exp = LEVELS.get(level + 1)
    if current_level_exp is None or next_level_exp is None:
        return {
            "next_level": level + 1,
            "needed": 0 if level >= max(LEVELS) else "N/A",
            "gained": 0,
            "span": 0,
            "percent": 100 if level >= max(LEVELS) else 0,
            "bar": "🟩" * 10 if level >= max(LEVELS) else "⬜" * 10,
        }
    span = max(1, next_level_exp - current_level_exp)
    gained = max(0, min(exp - current_level_exp, span))
    needed = max(0, next_level_exp - exp)
    percent = (gained / span) * 100
    filled = max(0, min(10, round(percent / 10)))
    return {
        "next_level": level + 1,
        "needed": needed,
        "gained": gained,
        "span": span,
        "percent": percent,
        "bar": ("🟩" * filled) + ("⬜" * (10 - filled)),
    }


def pick_any(dicts, *keys, default="N/A"):
    for data in dicts:
        value = pick(data, *keys, default=None)
        if value not in (None, ""):
            return value
    return default


LANGUAGE_NAMES = {
    "langen": "English",
    "langeng": "English",
    "en": "English",
    "english": "English",
    "langar": "Arabic",
    "ar": "Arabic",
    "langhi": "Hindi",
    "hi": "Hindi",
    "langid": "Indonesian",
    "id": "Indonesian",
    "langvi": "Vietnamese",
    "vi": "Vietnamese",
    "langth": "Thai",
    "th": "Thai",
    "langbn": "Bengali",
    "bn": "Bengali",
    "langur": "Urdu",
    "ur": "Urdu",
    "langzh": "Chinese",
    "zh": "Chinese",
    "langru": "Russian",
    "ru": "Russian",
    "langes": "Spanish",
    "es": "Spanish",
    "langpt": "Portuguese",
    "pt": "Portuguese",
}


def format_language(value):
    if value in (None, "", "N/A"):
        return "N/A"
    raw = str(value).strip()
    normalized = re.sub(r"[^a-z]", "", raw.lower())
    return LANGUAGE_NAMES.get(normalized, raw)


def template_help_text(user_name):
    return "\n".join([
        f"{user_name}, send now the message you want to set!",
        "",
        "You can use HTML and:",
        "• {ID} = user ID",
        "• {NAME} = user name",
        "• {SURNAME} = user surname",
        "• {NAMESURNAME} = name and surname",
        "• {LANG} = user language",
        "• {DATE} = current date",
        "• {TIME} = current time",
        "• {WEEKDAY} = week day",
        "• {MENTION} = link to the user profile",
        "• {USERNAME} = username",
        "• {GROUPNAME} = group name",
        "• {RULES} = group regulation",
    ])


def render_member_template(template, member, chat):
    now = datetime.now()
    first_name = getattr(member, "first_name", "") or ""
    last_name = getattr(member, "last_name", "") or ""
    username = getattr(member, "username", None)
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    language = format_language(getattr(member, "language_code", None))
    group_name = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(getattr(chat, "id", ""))
    rules = rules_db.get(getattr(chat, "id", None), "No rules set.")
    mention_name = escape(full_name or first_name or str(member.id))
    replacements = {
        "{ID}": str(member.id),
        "{NAME}": escape(first_name),
        "{SURNAME}": escape(last_name),
        "{NAMESURNAME}": escape(full_name or first_name),
        "{LANG}": escape(language),
        "{DATE}": now.strftime("%d %b %Y"),
        "{TIME}": now.strftime("%H:%M:%S"),
        "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": f'<a href="tg://user?id={member.id}">{mention_name}</a>',
        "{USERNAME}": f"@{escape(username)}" if username else "N/A",
        "{GROUPNAME}": escape(group_name),
        "{RULES}": escape(rules),
        "{first}": escape(first_name),
        "{id}": str(member.id),
    }
    text = template
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def find_nested_value(data, *keys, default="N/A"):
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for value in data.values():
            found = find_nested_value(value, *keys, default=None)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_nested_value(item, *keys, default=None)
            if found not in (None, ""):
                return found
    return default


def list_lines(items):
    if not items:
        return "• N/A"
    if not isinstance(items, list):
        items = [items]
    return "\n".join(f"• {item}" for item in items[:12])


def ban_status_text(basic):
    blacklist = pick(basic, "blacklist", default=None)
    if isinstance(blacklist, dict) and blacklist:
        reason = pick(blacklist, "ban_reason", "banReason", default="Banned")
        until = fmt_date(pick(blacklist, "ban_time", "banTime", "expire_duration", "expireDuration", default=None))
        return f"Banned ({reason}) until {until}"
    if pick(basic, "isBanned", "is_banned", default=False):
        return "Banned"
    return "Not Banned"


def format_ff_profile(data, requested_by):
    basic = data.get("basicInfo") or data.get("basic_info") or {}
    clan = data.get("clanBasicInfo") or data.get("clan_basic_info") or {}
    captain = data.get("captainBasicInfo") or data.get("captain_basic_info") or {}
    profile = data.get("profileInfo") or data.get("profile_info") or {}
    social = data.get("socialInfo") or data.get("social_info") or {}
    pet = data.get("petInfo") or data.get("pet_info") or {}
    credit = data.get("creditScoreInfo") or data.get("credit_score_info") or {}
    prime = data.get("primeInfo") or data.get("prime_info") or {}

    uid = pick(basic, "accountId", "account_id", "uid")
    nickname = pick(basic, "nickname", "name")
    level = pick(basic, "level")
    exp = pick(basic, "exp", "experience")
    progress, exp_needed = level_progress(level, exp)
    ranking_points = pick(basic, "rankingPoints", "ranking_points", default=0)
    cs_stars = pick(basic, "csRankingPoints", "cs_ranking_points", "csStars", "cs_stars", default="N/A")
    br_rank = pick(basic, "brRankName", "br_rank_name", default=None) or br_rank_name(ranking_points)
    cs_rank = pick(basic, "csRankName", "cs_rank_name", default=None) or cs_rank_name(pick(basic, "csRank", "cs_rank", default=None))
    captain_points = pick(captain, "rankingPoints", "ranking_points", default=0)
    captain_cs_stars = pick(captain, "csRankingPoints", "cs_ranking_points", "csStars", "cs_stars", default="N/A")
    captain_br_rank = pick(captain, "brRankName", "br_rank_name", default=None) or br_rank_name(captain_points)
    captain_cs_rank = pick(captain, "csRankName", "cs_rank_name", default=None) or cs_rank_name(pick(captain, "csRank", "cs_rank", default=None))
    prime_level = pick_any([prime, basic, profile], "primeLevel", "prime_level", default=None)
    if prime_level is None:
        prime_level = find_nested_value(data, "primeLevel", "prime_level")
    clan_members = pick(clan, "memberNum", "member_num", default="N/A")
    clan_capacity = pick(clan, "capacity", default="N/A")
    member_percent = "N/A"
    try:
        member_percent = f"{int(int(clan_members) * 100 / int(clan_capacity))}%"
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    outfit = pick(profile, "clothes", "clothesId", "clothes_id", default=[])
    skills = pick(profile, "equipedSkills", "equippedSkills", "equiped_skills", "equipped_skills", default=[])
    skins = pick(profile, "skinColor", "skin_color", "selectedSkin", "selected_skin", default=[])
    banner = pick_any(
        [profile, basic],
        "bannerName",
        "banner_name",
        "banner",
        "bannerId",
        "banner_id",
        "bannerItemId",
        "banner_item_id",
        "profileBanner",
        "profile_banner",
    )
    weapon = pick_any(
        [profile, basic],
        "weaponName",
        "weapon_name",
        "weaponSkinShows",
        "weapon_skin_shows",
        "weaponSkin",
        "weapon_skin",
        "weaponSkinId",
        "weapon_skin_id",
        "pvePrimaryWeapon",
        "pve_primary_weapon",
        "pinId",
        "pin_id",
    )
    animation = pick_any(
        [profile, basic],
        "animationName",
        "animation_name",
        "animation",
        "profileAnimation",
        "profile_animation",
        "profileAnimationId",
        "profile_animation_id",
        "personalShowAnimation",
        "personal_show_animation",
        "transformAnimation",
        "transform_animation",
    )

    lines = [
        "🎮 FREE FIRE PROFILE",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "👤 BASIC INFORMATION",
        "━━━━━━━━━━━━━━━━━━",
        f"🏷️ Nickname: {nickname}",
        f"🆔 UID: {uid}",
        f"🌐 Region: {pick(basic, 'region')}",
        f"📈 Level: {level}",
        f"📊 Level Progress: {progress}",
        f"✨ EXP: {fmt_num(exp)}",
        f"🎯 EXP Needed: {fmt_num(exp_needed)}",
        f"💙 Likes: {fmt_num(pick(basic, 'liked', 'likes'))}",
        f"🎖 Badges: {fmt_num(pick(basic, 'badgeCnt', 'badge_count', 'badges'))}",
        f"💎 Prime Level: {prime_level}",
        f"🏅 Title: {pick(basic, 'title')}",
        f"🛡 Ban Status: {ban_status_text(basic)}",
        f"📦 Version: {pick(basic, 'releaseVersion', 'release_version', 'version')}",
        f"📆 Created: {fmt_date(pick(basic, 'createAt', 'create_at', 'createdAt', 'created_at', default=None))}",
        f"⏱ Last Login: {fmt_date(pick(basic, 'lastLoginAt', 'last_login_at', 'lastLogin', 'last_login', default=None))}",
        "",
        "🏆 BATTLE ROYALE",
        "━━━━━━━━━━━━━━━━━━",
        f"🥇 Rank: {br_rank}",
        f"📊 Points: {fmt_num(ranking_points)}",
        "",
        "⚔️ CLASH SQUAD",
        "━━━━━━━━━━━━━━━━━━",
        f"🥈 Rank: {cs_rank}",
        f"⭐️Total Stars: {fmt_num(cs_stars)}",
        "",
        "🏰 CLAN INFORMATION",
        "━━━━━━━━━━━━━━━━━━",
        f"🏷️ Name: {pick(clan, 'clanName', 'clan_name')}",
        f"🆔 ID: {fmt_num(pick(clan, 'clanId', 'clan_id'))}",
        f"📈 Level: {pick(clan, 'clanLevel', 'clan_level', 'level')}",
        f"👥 Members: {fmt_num(clan_members)}/{fmt_num(clan_capacity)} ({member_percent})",
        f"👑 Captain: {pick(captain, 'nickname', 'name')}",
        f"🆔 Captain UID: {fmt_num(pick(clan, 'captainId', 'captain_id', default=pick(captain, 'accountId', 'account_id')))}",
        "",
        "👑 CAPTAIN INFORMATION",
        "━━━━━━━━━━━━━━━━━━",
        f"🏷️ Name: {pick(captain, 'nickname', 'name')}",
        f"🆔 UID: {fmt_num(pick(captain, 'accountId', 'account_id'))}",
        f"🌐 Region: {pick(captain, 'region')}",
        f"📈 Level: {pick(captain, 'level')}",
        f"💙 Likes: {fmt_num(pick(captain, 'liked', 'likes'))}",
        f"🏆 BR Rank: {captain_br_rank}",
        f"📊 Points: {fmt_num(captain_points)}",
        f"⚔️ CS Rank: {captain_cs_rank}",
        f"⭐️Total Stars: {fmt_num(captain_cs_stars)}",
        f"⏱ Last Login: {fmt_date(pick(captain, 'lastLoginAt', 'last_login_at', 'lastLogin', 'last_login', default=None))}",
        "",
        "🎨 PROFILE STYLE",
        "━━━━━━━━━━━━━━━━━━",
        f"🧍 Character: {pick(profile, 'characterId', 'character_id', 'avatarId', 'avatar_id')}",
        f"🖼 Avatar: {pick(profile, 'avatarId', 'avatar_id')}",
        f"🏳 Banner: {banner}",
        f"🔫 Weapon: {weapon}",
        f"🏇 Animation: {animation}",
        "🧩 Skins:",
        list_lines(skins),
        "👕 Outfit:",
        list_lines(outfit),
        f"⚡ Skill Slots: {fmt_num(len(skills) if isinstance(skills, list) else pick(profile, 'skillSlots', 'skill_slots'))}",
        "🧠 Skills:",
        list_lines(skills),
        "",
        "💬 SOCIAL",
        "━━━━━━━━━━━━━━━━━━",
        f"📝 Bio: {pick(social, 'signature', 'bio')}",
        f"🚻 Gender: {pick(social, 'gender')}",
        f"🌐 Language: {pick(social, 'language')}",
        f"🏆 Rank Show: {pick(social, 'rankShow', 'rank_show')}",
        "",
        "🐾 PET INFORMATION",
        "━━━━━━━━━━━━━━━━━━",
        f"🏷️ Name: {pick(pet, 'name')}",
        f"🆔 ID: {fmt_num(pick(pet, 'id', 'petId', 'pet_id'))}",
        f"📈 Level: {pick(pet, 'level')}",
        f"✨ EXP: {fmt_num(pick(pet, 'exp'))}",
        f"🎨 Pet Skin: {pick(pet, 'skinId', 'skin_id')}",
        f"🧠 Skill: {pick(pet, 'selectedSkillId', 'selected_skill_id', 'skillId', 'skill_id')}",
        "",
        "✅ CREDIT SCORE",
        "━━━━━━━━━━━━━━━━━━",
        f"💯 Score: {pick(credit, 'creditScore', 'credit_score', 'score')}/100",
        f"📌 Status: {pick(credit, 'rewardState', 'reward_state', 'status')}",
        f"⏳ Valid Until: {fmt_date(pick(credit, 'periodicSummaryEndTime', 'periodic_summary_end_time', 'validUntil', 'valid_until', default=None))}",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"🙋 Requested by: {requested_by}",
        f"🕒 Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ]
    return "\n".join(lines)


def format_ff_player_information(data, requested_by="N/A"):
    basic = data.get("basicInfo") or data.get("basic_info") or {}
    clan = data.get("clanBasicInfo") or data.get("clan_basic_info") or {}
    captain = data.get("captainBasicInfo") or data.get("captain_basic_info") or {}
    profile = data.get("profileInfo") or data.get("profile_info") or {}
    social = data.get("socialInfo") or data.get("social_info") or {}
    pet = data.get("petInfo") or data.get("pet_info") or {}
    credit = data.get("creditScoreInfo") or data.get("credit_score_info") or {}
    prime = data.get("primeInfo") or data.get("prime_info") or {}

    level = pick(basic, "level")
    exp = pick(basic, "exp", "experience")
    ranking_points = pick(basic, "rankingPoints", "ranking_points", default=0)
    cs_points = pick(basic, "csRankingPoints", "cs_ranking_points", "csStars", "cs_stars", default="N/A")
    br_rank = pick(basic, "brRankName", "br_rank_name", default=None) or br_rank_name(ranking_points)
    cs_rank = pick(basic, "csRankName", "cs_rank_name", default=None) or cs_rank_name(pick(basic, "csRank", "cs_rank", default=None))
    captain_points = pick(captain, "rankingPoints", "ranking_points", default=0)
    captain_cs_points = pick(captain, "csRankingPoints", "cs_ranking_points", "csStars", "cs_stars", default="N/A")
    captain_br_rank = pick(captain, "brRankName", "br_rank_name", default=None) or br_rank_name(captain_points)
    captain_cs_rank = pick(captain, "csRankName", "cs_rank_name", default=None) or cs_rank_name(pick(captain, "csRank", "cs_rank", default=None))
    prime_level = pick_any([prime, basic, profile], "primeLevel", "prime_level", default=None)
    if prime_level is None:
        prime_level = find_nested_value(data, "primeLevel", "prime_level")
    equipped_skills = pick(profile, "equipedSkills", "equippedSkills", "equiped_skills", "equipped_skills", default=[])
    if isinstance(equipped_skills, list):
        equipped_skills = len(equipped_skills)
    badges = pick(basic, "badgeCnt", "badge_count", "badges", default=None)
    badges_display = "0" if badges in (None, "", "N/A") else fmt_num(badges)
    prime_display = "0" if prime_level in (None, "", "N/A") else prime_level
    cs_points_display = "0" if cs_points in (None, "", "N/A") else fmt_num(cs_points)
    has_pet = any(
        pick(pet, key, default=None) not in (None, "", "N/A", 0)
        for key in ("id", "petId", "pet_id", "level", "exp", "skinId", "skin_id")
    )
    bio = pick(social, "signature", "bio", default=None)
    language = format_language(pick(social, "language", default=None))
    privacy = pick(social, "privacy", "accountPrivacy", "account_privacy", default=None)
    has_social = any(value not in (None, "", "N/A") for value in (bio, language, privacy))

    def b(text):
        return f"<b>{text}</b>"

    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    lines = [
        f"🎮 {b('PLAYER INFORMATION')} 🎮",
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"📋 {b('BASIC INFORMATION')}",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 {b('Nickname:')} {v(pick(basic, 'nickname', 'name'))}",
        f"🆔 {b('UID:')} {v(pick(basic, 'accountId', 'account_id', 'uid'))}",
        f"🌍 {b('Region:')} {v(pick(basic, 'region'))}",
        f"⭐ {b('Level:')} {v(level)}",
        f"📊 {b('EXP:')} {v(fmt_num(exp))}",
        f"❤️ {b('Likes:')} {v(fmt_num(pick(basic, 'liked', 'likes')))}",
    ]
    lines.append(f"🎖️ {b('Badges:')} {v(badges_display)}")
    lines.append(f"💎 {b('Prime Level:')} {v(prime_display)}")
    lines.extend([
        f"🏆 {b('Title ID:')} {v(fmt_num(pick(basic, 'title', 'titleId', 'title_id')))}",
        f"📅 {b('Created:')} {v(fmt_date(pick(basic, 'createAt', 'create_at', 'createdAt', 'created_at', default=None)))}",
        f"🕒 {b('Last Login:')} {v(fmt_date(pick(basic, 'lastLoginAt', 'last_login_at', 'lastLogin', 'last_login', default=None)))}",
        "",
        f"🏆 {b('BATTLE ROYALE RANK')}",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 {b('Current Rank:')} {v(br_rank)}",
        f"📈 {b('Ranking Points:')} {v(fmt_num(ranking_points))}",
        "",
        f"🔫 {b('CLASH SQUAD RANK')}",
        "━━━━━━━━━━━━━━━━━━",
        f"⚡ {b('Current Rank:')} {v(cs_rank)}",
    ])
    lines.append(f"📊 {b('CS Points:')} {v(cs_points_display)}")
    lines.append("")

    if clan:
        lines.extend([
            f"👥 {b('CLAN INFORMATION')}",
            "━━━━━━━━━━━━━━━━━━",
            f"🏰 {b('Clan Name:')} {v(pick(clan, 'clanName', 'clan_name'))}",
            f"🔢 {b('Clan ID:')} {v(fmt_num(pick(clan, 'clanId', 'clan_id')))}",
            f"⭐ {b('Clan Level:')} {v(pick(clan, 'clanLevel', 'clan_level', 'level'))}",
            f"👤 {b('Members:')} {v(fmt_num(pick(clan, 'memberNum', 'member_num')))}/{v(fmt_num(pick(clan, 'capacity')))}",
            f"👑 {b('Captain UID:')} {v(fmt_num(pick(clan, 'captainId', 'captain_id', default=pick(captain, 'accountId', 'account_id'))))}",
            "",
        ])

    if clan and captain:
        lines.extend([
            f"👑 {b('CAPTAIN INFORMATION')}",
            "━━━━━━━━━━━━━━━━━━",
            f"🏷️ {b('Name:')} {v(pick(captain, 'nickname', 'name'))}",
            f"🆔 {b('UID:')} {v(fmt_num(pick(captain, 'accountId', 'account_id')))}",
            f"🌐 {b('Region:')} {v(pick(captain, 'region'))}",
            f"📈 {b('Level:')} {v(pick(captain, 'level'))}",
            f"💙 {b('Likes:')} {v(fmt_num(pick(captain, 'liked', 'likes')))}",
            f"🏆 {b('BR Rank:')} {v(captain_br_rank)}",
            f"📊 {b('Points:')} {v(fmt_num(captain_points))}",
            f"⚔️ {b('CS Rank:')} {v(captain_cs_rank)}",
            f"⭐️{b('Total Stars:')} {v(fmt_num(captain_cs_points))}",
            f"⏱️ {b('Last Login:')} {v(fmt_date(pick(captain, 'lastLoginAt', 'last_login_at', 'lastLogin', 'last_login', default=None)))}",
            "",
        ])

    lines.extend([
        f"🎭 {b('PROFILE SETTINGS')}",
        "━━━━━━━━━━━━━━━━━━",
        f"🖼️ {b('Avatar ID:')} {v(fmt_num(pick(profile, 'avatarId', 'avatar_id', default=pick(basic, 'headPic', 'head_pic'))))}",
        f"⚡ {b('Equipped Skills:')} {v(fmt_num(equipped_skills))}",
        "",
    ])

    if has_social:
        lines.extend([
            f"💬 {b('SOCIAL INFORMATION')}",
            "━━━━━━━━━━━━━━━━━━",
        ])
        if bio not in (None, "", "N/A"):
            lines.append(f"📝 {b('Bio:')} {v(bio)}")
        if language not in (None, "", "N/A"):
            lines.append(f"🌐 {b('Language:')} {v(language)}")
        if privacy not in (None, "", "N/A"):
            lines.append(f"🔒 {b('Privacy:')} {v(privacy)}")
        lines.append("")

    if has_pet:
        lines.extend([
            f"🐾 {b('PET INFORMATION')}",
            "━━━━━━━━━━━━━━━━━━",
            f"🆔 {b('Pet ID:')} {v(fmt_num(pick(pet, 'id', 'petId', 'pet_id')))}",
            f"⭐ {b('Pet Level:')} {v(pick(pet, 'level'))}",
            f"📈 {b('Pet EXP:')} {v(fmt_num(pick(pet, 'exp')))}",
            f"🎭 {b('Skin ID:')} {v(fmt_num(pick(pet, 'skinId', 'skin_id')))}",
            "",
        ])

    lines.extend([
        f"💳 {b('CREDIT SCORE')}",
        "━━━━━━━━━━━━━━━━━━",
        f"⭐ {b('Score:')} {v(pick(credit, 'creditScore', 'credit_score', 'score'))}/100",
        f"⏰ {b('Valid Until:')} {v(fmt_date(pick(credit, 'periodicSummaryEndTime', 'periodic_summary_end_time', 'validUntil', 'valid_until', default=None)))}",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"🙋 Requested by: {v(requested_by)}",
        f"🕒 Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ])
    return "\n".join(lines)


def format_region_info(data, requested_by="N/A"):
    def b(text):
        return f"<b>{text}</b>"

    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    return "\n".join([
        f"🌍 {b('REGION INFORMATION')}",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 {b('Name:')} {v(data.get('Name'))}",
        f"🆔 {b('UID:')} {v(data.get('UID'))}",
        f"⭐ {b('Level:')} {v(data.get('Level'))}",
        f"🌐 {b('Region:')} {v(data.get('Region'))}",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"🙋 Requested by: {v(requested_by)}",
        f"🕒 Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ])


def format_level_tracker(data, requested_by="N/A"):
    basic = data.get("basicInfo") or data.get("basic_info") or {}
    level = pick(basic, "level")
    exp = pick(basic, "exp", "experience", default=0)
    details = level_progress_details(level, exp)

    def b(text):
        return f"<b>{text}</b>"

    def i(text):
        return f"<i>{text}</i>"

    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    next_level = details["next_level"]
    exp_next_label = f"EXP to Next Level ({next_level}):"

    return "\n".join([
        f"📊 {b('LEVEL TRACKER')} 📊",
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"👤 {b('Player Information:')}",
        f"🏷️ {b('Nickname:')} {v(pick(basic, 'nickname', 'name'))}",
        f"🆔 {b('UID:')} {v(pick(basic, 'accountId', 'account_id', 'uid'))}",
        f"🌍 {b('Region:')} {v(pick(basic, 'region'))}",
        f"📅 {b('Created:')} {v(fmt_date(pick(basic, 'createAt', 'create_at', 'createdAt', 'created_at', default=None)))}",
        f"❤️ {b('Total Likes:')} {v(fmt_num(pick(basic, 'liked', 'likes')))}",
        "",
        f"🎯 {b('Current Status:')}",
        f"⭐ {b('Level:')} {v(level)}",
        f"✨ {b('Current EXP:')} {v(fmt_num(exp))}",
        f"⏳ {b(exp_next_label)} {v(fmt_num(details['needed']))}",
        "",
        f"📈 {b('Progress')}",
        f"⭐ Level {v(level)} → {v(next_level)}",
        f"{details['bar']} {details['percent']:.1f}%",
        f"✨ EXP: {v(fmt_num(details['gained']))} / {v(fmt_num(details['span']))}",
        f"⏳ Need: {v(fmt_num(details['needed']))} EXP",
        "━━━━━━━━━━━━━━━━━━",
        f"🙋 Requested by: {v(requested_by)}",
        f"🕒 Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ])


def format_ban_info(data, requested_by="N/A"):
    def b(text):
        return f"<b>{text}</b>"

    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    lines = [
        f"🛡 {b('BAN INFORMATION')}",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 {b('Name:')} {v(data.get('nickname'))}",
        f"🆔 {b('UID:')} {v(data.get('player_id'))}",
        f"📊 {b('Status:')} {v(data.get('status'))}",
        f"⏳ {b('Period:')} {v(data.get('ban_period'))}",
        f"🌐 {b('Region:')} {v(data.get('region'))}",
    ]
    if data.get("level") not in (None, "", "N/A"):
        lines.append(f"⭐ {b('Level:')} {v(data.get('level'))}")
    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"🙋 Requested by: {v(requested_by)}",
        f"🕒 Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ])
    return "\n".join(lines)


def format_jwt_check(data):
    guest_auth = data.get("Guest_Auth") or {}
    guest_data = guest_auth.get("data") if isinstance(guest_auth, dict) else {}
    major = data.get("MajorLogin") or {}
    access_token = pick(guest_data, "access_token", default="N/A")
    jwt_token = pick(major, "jwt_token", "token", default="N/A")
    account_id = pick(major, "account_id", "accountId", default="N/A")
    name = pick(major, "nickname", "name", default="N/A")
    region = pick(major, "region", "lock_region", "noti_region", default="N/A")

    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    return "\n".join([
        "✅ <b>JWT CHECK SUCCESS</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Name:</b> {v(name)}",
        f"🆔 <b>Account ID:</b> {v(account_id)}",
        f"🌐 <b>Region:</b> {v(region)}",
        "",
        "🔑 <b>Access Token</b>",
        f"<code>{v(access_token)}</code>",
        "",
        "🎟 <b>JWT Token</b>",
        f"<code>{v(jwt_token)}</code>",
    ])


def format_guestgen(data):
    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    region = data.get("region") or data.get("requested_region")
    account_id = data.get("account_id")
    uid = data.get("uid")
    password = data.get("password")
    access_token = data.get("access_token")
    name = data.get("name")

    return "\n".join([
        "✅ <b>Guest account generated</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"🌐 <b>Region:</b> {v(region)}",
        f"👤 <b>Name:</b> {v(name)}",
        f"🆔 <b>Account ID:</b> {v(account_id)}",
        "",
        f"🎮 <b>UID:</b> <code>{v(uid)}</code>",
        f"🔐 <b>Password:</b> <code>{v(password)}</code>",
        "",
        "🔑 <b>Access Token</b>",
        f"<code>{v(access_token)}</code>",
    ])


def format_bio_update(data, bio):
    def v(value):
        return escape(str(value if value not in (None, "") else "N/A"))

    return "\n".join([
        "✅ <b>BIO UPDATE SUCCESS</b>" if data.get("success") else "❌ <b>BIO UPDATE FAILED</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Player Name:</b> {v(data.get('nickname') or data.get('name'))}",
        f"🆔 <b>UID:</b> {v(data.get('account_id') or data.get('uid'))}",
        f"📱 <b>Platform:</b> {v(data.get('platform'))}",
        f"🌍 <b>Region:</b> {v(data.get('region'))}",
        "",
        f"📝 <b>New Bio:</b> {v(data.get('bio') or bio)}",
        "",
        f"📌 <b>Status:</b> {v(data.get('message'))}",
    ])


def send_long_message(message, text, parse_mode=None):
    chunks = []
    while text:
        chunks.append(text[:3900])
        text = text[3900:]
    for chunk in chunks:
        bot.reply_to(message, chunk, parse_mode=parse_mode)


def owner_contact_text():
    if not OWNER_ID:
        return "Owner"
    try:
        owner = bot.get_chat(OWNER_ID)
        if getattr(owner, "username", None):
            return f"@{owner.username}"
        return getattr(owner, "first_name", None) or str(OWNER_ID)
    except Exception:
        return str(OWNER_ID)


def format_likeff_price_list():
    owner_contact = owner_contact_text()
    return "\n".join([
        "💎 PREMIUM LIKE PRICE",
        "━━━━━━━━━━━━━━━━━━",
        "› 1,000 ʟɪᴋᴇs : $0.50",
        "› 2,000 ʟɪᴋᴇs : $1.00",
        "› 3,000 ʟɪᴋᴇs : $1.50",
        "› 4,000 ʟɪᴋᴇs : $2.00",
        "› 5,000 ʟɪᴋᴇs : $2.50",
        "› 6,000 ʟɪᴋᴇs : $2.75",
        "› 7,000 ʟɪᴋᴇs : $3.25",
        "› 8,000 ʟɪᴋᴇs : $3.75",
        "› 9,000 ʟɪᴋᴇs : $4.25",
        "› 10,000 ʟɪᴋᴇs : $4.50",
        "",
        "⚡ Daily 220 likes available.",
        f"🚀 Contact {owner_contact} to purchase likes.",
    ])


@bot.message_handler(commands=["like"])
def like_command(message):
    handle_like_command(message, "like")


@bot.message_handler(commands=["likeff"])
def likeff_command(message):
    if not OWNER_ID or message.from_user.id != OWNER_ID:
        bot.reply_to(message, format_likeff_price_list(), parse_mode=None)
        return
    handle_like_command(message, "likeff")


@bot.message_handler(commands=["myautolike"])
def myautolike_command(message):
    with autolike_lock:
        orders = load_autolike_orders()
    text = format_my_autolike_orders(message.from_user, orders)
    send_long_message(message, text, parse_mode=None)


@bot.message_handler(commands=["autolikegroup"])
def autolikegroup_command(message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    usage = "⚠️ Invalid format.\n📌 Use: /autolikegroup <set|del|ls> [group_id]"
    if len(parts) < 2:
        bot.reply_to(message, usage, parse_mode=None)
        return

    action = parts[1].lower()
    with autolike_lock:
        groups = load_autolike_groups()
        if action == "ls":
            lines = ["🏷 AUTOLIKEFF ALLOWED GROUPS", "━━━━━━━━━━━━━━━━━━"]
            if not groups:
                lines.append("ℹ️ No groups allowed.")
            else:
                for group_id in groups:
                    lines.append(f"› {group_id} - {chat_title(group_id)}")
            bot.reply_to(message, "\n".join(lines), parse_mode=None)
            return

        if action not in {"set", "del"}:
            bot.reply_to(message, usage, parse_mode=None)
            return

        group_id = parts[2] if len(parts) >= 3 else str(message.chat.id)
        if action == "set":
            if group_id not in groups:
                groups.append(group_id)
            save_autolike_groups(groups)
            bot.reply_to(message, f"✅ AUTOLIKEFF GROUP ALLOWED\n━━━━━━━━━━━━━━━━━━\n💬 Group ID: {group_id}", parse_mode=None)
            return

        groups = [item for item in groups if item != group_id]
        save_autolike_groups(groups)
        bot.reply_to(message, f"✅ AUTOLIKEFF GROUP REMOVED\n━━━━━━━━━━━━━━━━━━\n💬 Group ID: {group_id}", parse_mode=None)


@bot.message_handler(commands=["autolikeff"])
def autolikeff_command(message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()

    if len(parts) == 2 and parts[1].lower() in {"ls", "list"}:
        with autolike_lock:
            orders = load_autolike_orders()
        send_long_message(message, format_autolike_list(orders), parse_mode=None)
        return

    if len(parts) == 2 and parts[1].lower() in {"summary", "data", "stats"}:
        with autolike_lock:
            orders = load_autolike_orders()
        bot.reply_to(message, format_autolike_summary(orders), parse_mode=None)
        return

    if len(parts) == 3 and parts[1].lower() in {"del", "delete", "remove"} and parts[2].isdigit():
        uid = parts[2]
        removed_order = None
        with autolike_lock:
            orders = load_autolike_orders()
            kept_orders = []
            for order in orders:
                if str(order.get("uid")) == uid and order.get("status") != "cancelled":
                    if not is_owner(message.from_user.id) and str(order.get("group_id")) != str(message.chat.id):
                        kept_orders.append(order)
                        continue
                    removed_order = order
                    continue
                kept_orders.append(order)
            save_autolike_orders(kept_orders)

        if not removed_order:
            reply_premium(message, "ℹ️ AutoLikeFF order not found for this UID.")
            return

        text = "\n".join([
            "✅ AUTOLIKEFF ORDER REMOVED",
            "━━━━━━━━━━━━━━━━━━",
            f"🧾 Order ID: {removed_order.get('order_id', 'N/A')}",
            f"🆔 UID: {uid}",
        ])
        bot.reply_to(message, text, parse_mode=None)
        try:
            bot.send_message(int(removed_order.get("telegram_user_id")), text, parse_mode=None)
        except Exception as exc:
            logger.warning("Autolike delete private notify failed: %s", exc)
        return

    if len(parts) != 4 or not parts[1].isdigit() or not parts[2].isdigit() or not parts[3].isdigit():
        reply_premium(message, "⚠️ Invalid format.\n📌 Use: /autolikeff <uid> <total_likes> <telegram_user_id>\n📋 List: /autolikeff ls\n📊 Summary: /autolikeff summary\n🗑 Delete: /autolikeff del <uid>")
        return

    uid = parts[1]
    total_likes = int(parts[2])
    telegram_user_id = parts[3]
    if total_likes <= 0:
        bot.reply_to(message, "⚠️ Invalid total.\n📌 Total likes must be a positive number.", parse_mode=None)
        return

    now_text = datetime.now(CAMBODIA_TZ).strftime("%d %b %Y %H:%M:%S")
    group_id = resolve_autolike_group_id(message)
    with autolike_lock:
        orders = load_autolike_orders()
        existing_order = find_existing_autolike_order(orders, uid)
        if existing_order:
            bot.reply_to(
                message,
                "\n".join([
                    "⚠️ AUTOLIKEFF ORDER EXISTS",
                    "━━━━━━━━━━━━━━━━━━",
                    f"🧾 Order ID: {existing_order.get('order_id', 'N/A')}",
                    f"🆔 UID: {uid}",
                    "📌 Use /extend <uid> <extra_likes> to add more likes.",
                ]),
                parse_mode=None,
            )
            return
        order = {
            "order_id": next_autolike_order_id(orders),
            "uid": uid,
            "total_likes": total_likes,
            "sent_likes": 0,
            "telegram_user_id": telegram_user_id,
            "group_id": group_id,
            "created_by": str(message.from_user.id),
            "created_at": now_text,
            "status": "active",
            "last_period": "",
            "next_run_date": next_autolike_run_date(),
            "last_error": "",
        }
        orders.append(order)
        save_autolike_orders(orders)

    text = "\n".join([
        "✅ AUTOLIKEFF ORDER CREATED",
        "━━━━━━━━━━━━━━━━━━",
        f"🧾 Order ID: {order.get('order_id', 'N/A')}",
        f"🆔 UID: {uid}",
        f"👤 Telegram User: {telegram_user_display(telegram_user_id, html=True)}",
        f"🎯 Total Likes: {total_likes:,}",
        "⏳ First delivery is processing now.",
    ])
    bot.reply_to(message, text, parse_mode="HTML")
    threading.Thread(target=deliver_autolikeff_order_now, args=(order["order_id"],), daemon=True).start()


@bot.message_handler(commands=["extend"])
def extend_autolikeff_command(message):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /extend <uid> <extra_likes>", parse_mode=None)
        return

    uid = parts[1]
    extra_likes = int(parts[2])
    if extra_likes <= 0:
        bot.reply_to(message, "⚠️ Invalid amount.\n📌 Extra likes must be a positive number.", parse_mode=None)
        return

    updated_order = None
    with autolike_lock:
        orders = load_autolike_orders()
        for order in orders:
            if str(order.get("uid")) == uid and order.get("status") != "cancelled":
                if not is_owner(message.from_user.id) and str(order.get("group_id")) != str(message.chat.id):
                    continue
                order["total_likes"] = int(order.get("total_likes", 0) or 0) + extra_likes
                if order.get("status") == "completed":
                    order["status"] = "active"
                    order["next_run_date"] = next_autolike_run_date()
                order["extended_at"] = datetime.now(CAMBODIA_TZ).strftime("%d %b %Y %H:%M:%S")
                updated_order = order
                break
        save_autolike_orders(orders)

    if not updated_order:
        bot.reply_to(message, "ℹ️ AutoLikeFF order not found for this UID.", parse_mode=None)
        return

    text = format_autolike_order(updated_order, title="✅ AUTOLIKEFF ORDER EXTENDED")
    bot.reply_to(message, text, parse_mode="HTML")
    try:
        bot.send_message(int(updated_order.get("telegram_user_id")), text, parse_mode="HTML")
    except Exception as exc:
        logger.warning("Autolike extend private notify failed: %s", exc)


@bot.message_handler(commands=["ffinfo"])
def ffinfo_command(message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /ffinfo <uid>", parse_mode=None)
        return
    threading.Thread(target=process_ffinfo, args=(message, args[1]), daemon=True).start()


def process_ffinfo(message, uid):
    status_msg = bot.reply_to(
        message,
        "⏳ Loading Free Fire profile...",
        parse_mode=None,
    )
    data = call_api("meanffinfo", {"uid": uid}, timeout=180)
    if "error" in data:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ FFINFO FAILED\n━━━━━━━━━━━━━━━━━━\n{data['error']}",
            parse_mode=None,
        )
        return
    requested_by = requester_name(message.from_user)
    text = format_ff_player_information(data, requested_by)
    bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text[:3900], parse_mode="HTML")
    extra = text[3900:]
    while extra:
        bot.send_message(status_msg.chat.id, extra[:3900], parse_mode="HTML")
        extra = extra[3900:]


@bot.message_handler(commands=["level"])
def level_command(message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /level <uid>", parse_mode=None)
        return
    threading.Thread(target=process_level_tracker, args=(message, args[1]), daemon=True).start()


def process_level_tracker(message, uid):
    status_msg = bot.reply_to(
        message,
        "⏳ Loading level tracker...",
        parse_mode=None,
    )
    data = call_api("meanffinfo", {"uid": uid}, timeout=180)
    if "error" in data:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ LEVEL TRACKER FAILED\n━━━━━━━━━━━━━━━━━━\n{data['error']}",
            parse_mode=None,
        )
        return
    requested_by = requester_name(message.from_user)
    text = format_level_tracker(data, requested_by)
    bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text[:3900], parse_mode="HTML")


def process_jwtcheck(message, uid, password):
    status_msg = bot.send_message(message.chat.id, "⏳ Checking JWT...\n━━━━━━━━━━━━━━━━━━\nPlease wait.", parse_mode=None)
    data = call_api("jwt", {"uid": uid, "pw": password})
    if data.get("status") != "success" or not data.get("MajorLogin"):
        error_text = data.get("message") or data.get("error") or "JWT check failed"
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ JWT CHECK FAILED\n━━━━━━━━━━━━━━━━━━\n{error_text}",
        )
        return
    text = format_jwt_check(data)
    bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text[:3900], parse_mode="HTML")
    extra = text[3900:]
    while extra:
        bot.send_message(status_msg.chat.id, extra[:3900], parse_mode="HTML")
        extra = extra[3900:]


@bot.message_handler(commands=["jwt"])
def jwt_command(message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split(maxsplit=2)
    if len(args) != 3 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /jwt <uid> <password>", parse_mode=None)
        return
    threading.Thread(target=process_jwtcheck, args=(message, args[1], args[2]), daemon=True).start()


def guest_account_record(data):
    return {
        "region": data.get("region") or data.get("requested_region"),
        "name": data.get("name"),
        "account_id": data.get("account_id"),
        "uid": data.get("uid"),
        "password": data.get("password"),
        "access_token": data.get("access_token"),
        "jwt_token": data.get("jwt_token"),
    }


def process_guestgen(message, region, name, total=None, file_mode=False):
    status_msg = bot.send_message(message.chat.id, "⏳ Generating guest account...\n━━━━━━━━━━━━━━━━━━\nPlease wait.", parse_mode=None)
    accounts = []
    failures = []
    total = total or 1

    for index in range(total):
        if total > 1:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=f"⏳ Generating guest accounts...\n━━━━━━━━━━━━━━━━━━\n📦 Progress: {index + 1}/{total}",
                parse_mode=None,
            )
        data = call_api("createaccount", {"region": region, "name": name})
        if data.get("success") and not data.get("error"):
            accounts.append(guest_account_record(data))
        else:
            failures.append(data.get("error") or data.get("warning") or "Guest account generation failed")

    if not accounts:
        error_text = failures[0] if failures else "Guest account generation failed"
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ <b>GUEST GENERATION FAILED</b>\n━━━━━━━━━━━━━━━━━━\n{escape(str(error_text))}",
            parse_mode="HTML",
        )
        return

    if not file_mode:
        text = format_guestgen(accounts[0])
        bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text[:3900], parse_mode="HTML")
        extra = text[3900:]
        while extra:
            bot.send_message(status_msg.chat.id, extra[:3900], parse_mode="HTML")
            extra = extra[3900:]
        return

    filename = f"Guest-{region}.json"
    generated_at = datetime.now().strftime("%d %b %Y %H:%M:%S")
    generated_by = message.from_user.first_name or message.from_user.username or str(message.from_user.id)
    file_payload = {
        "region": region,
        "accounts": len(accounts),
        "generated_by": generated_by,
        "generated_at": generated_at,
        "items": accounts,
    }
    with open(filename, "w", encoding="utf-8") as guest_file:
        json.dump(file_payload, guest_file, ensure_ascii=False, indent=2)

    caption = "\n".join([
        "📄 Temporary Accounts File",
        f"🌍 Region: {region}",
        f"🔢 Accounts: {len(accounts)}",
        f"👤 Generated by: {generated_by}",
        f"⏰ Generated at: {generated_at}",
    ])
    with open(filename, "rb") as guest_file:
        bot.send_document(message.chat.id, guest_file, caption=caption)
    safe_delete(status_msg.chat.id, status_msg.message_id)
    try:
        os.remove(filename)
    except OSError:
        logger.warning("Could not remove temporary file %s", filename)


@bot.message_handler(commands=["guestgen"])
def guestgen_command(message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) not in {3, 4} or not args[1].isalpha():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /guestgen <region> <name> [total]", parse_mode=None)
        return
    total = None
    file_mode = False
    if len(args) == 4:
        if not args[3].isdigit() or int(args[3]) <= 0:
            bot.reply_to(message, "⚠️ Invalid total.\n📌 Total must be a positive number.", parse_mode=None)
            return
        total = int(args[3])
        file_mode = True
    threading.Thread(target=process_guestgen, args=(message, args[1].upper(), args[2], total, file_mode), daemon=True).start()


def process_bio_update(message, params, bio):
    status_msg = bot.send_message(message.chat.id, "⏳ Updating bio...\n━━━━━━━━━━━━━━━━━━\nPlease wait.", parse_mode=None)
    data = call_api("bio", params)
    text = format_bio_update(data, bio)
    bot.edit_message_text(
        chat_id=status_msg.chat.id,
        message_id=status_msg.message_id,
        text=text[:3900],
        parse_mode="HTML",
    )


@bot.message_handler(commands=["bio"])
def bio_command(message):
    safe_delete(message.chat.id, message.message_id)
    if not check_access(message):
        return
    usage = "\n".join([
        "📝 BIO UPDATE",
        "━━━━━━━━━━━━━━━━━━",
        "📌 Use: /bio <access_token|jwt|uidpass> <new_bio>",
        "",
        "UID/password format:",
        "/bio <uid> <password>|<new_bio>",
    ])
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, usage, parse_mode=None)
        return

    token = parts[1].strip()
    bio = parts[2].strip()
    if not token or not bio:
        bot.reply_to(message, usage, parse_mode=None)
        return
    if token.isdigit() and "|" in bio:
        password, bio_text = bio.split("|", 1)
        password = password.strip()
        bio_text = bio_text.strip()
        if not password or not bio_text:
            bot.reply_to(message, usage, parse_mode=None)
            return
        params = {"uid": token, "password": password, "bio": bio_text}
        bio = bio_text
    else:
        params = {"token": token, "bio": bio}

    threading.Thread(target=process_bio_update, args=(message, params, bio), daemon=True).start()


@bot.message_handler(commands=["region"])
def region_command(message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /region <uid>", parse_mode=None)
        return
    threading.Thread(target=process_region_check, args=(message, args[1]), daemon=True).start()


def process_region_check(message, uid):
    status_msg = bot.reply_to(
        message,
        "⏳ Checking region...",
        parse_mode=None,
    )
    data = call_api("check-region", {"uid": uid}, timeout=180)
    if "error" in data:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ REGION CHECK FAILED\n━━━━━━━━━━━━━━━━━━\n{data['error']}",
            parse_mode=None,
        )
        return
    requested_by = requester_name(message.from_user)
    bot.edit_message_text(
        chat_id=status_msg.chat.id,
        message_id=status_msg.message_id,
        text=format_region_info(data, requested_by),
        parse_mode="HTML",
    )


@bot.message_handler(commands=["remain"])
def remain_command(message):
    if OWNER_ID and message.from_user.id != OWNER_ID:
        return
    lines = ["📊 DAILY USAGE", "━━━━━━━━━━━━━━━━━━"]
    if not usage_tracker:
        lines.append("ℹ️ No usage yet.")
    else:
        for user_id, usage in usage_tracker.items():
            limit = get_user_limit(user_id)
            lines.append(f"`{user_id}`: {usage.get('used', 0)}/{limit if limit < 999999 else 'Unlimited'}")
    bot.reply_to(message, "\n".join(lines), parse_mode=None)


def process_uidpass_update(message, set_name):
    status_msg = bot.send_message(message.chat.id, f"⏳ Updating {set_name} tokens...\n━━━━━━━━━━━━━━━━━━\nPlease wait.", parse_mode=None)
    try:
        code, output = run_token_update(set_name)
        token_file = UIDPASS_FILE_SETS[set_name][1]
        if code == 0:
            text = "\n".join([
                "✅ UIDPASS TOKEN UPDATE DONE",
                "━━━━━━━━━━━━━━━━━━",
                f"📦 Set: {set_name}",
                f"📄 Token File: {token_file}",
                "",
                (output[-3000:] if output else "ℹ️ No output."),
            ])
        else:
            text = "\n".join([
                "❌ UIDPASS TOKEN UPDATE FAILED",
                "━━━━━━━━━━━━━━━━━━",
                f"📦 Set: {set_name}",
                "",
                (output[-3000:] if output else f"Exit code {code}"),
            ])
        bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text, parse_mode=None)
    except Exception as exc:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ UIDPASS TOKEN UPDATE FAILED\n━━━━━━━━━━━━━━━━━━\n{exc}",
            parse_mode=None,
        )


def process_single_uidpass_token_update(message, set_name, uid, password, action_title):
    status_msg = bot.send_message(
        message.chat.id,
        f"⏳ {action_title}\n━━━━━━━━━━━━━━━━━━\n🆔 UID: {uid}\n📌 Token refreshing...",
        parse_mode=None,
    )
    try:
        code, output = run_single_token_update(set_name, uid, password)
        token_file = UIDPASS_FILE_SETS[set_name][1]
        if code == 0:
            text = "\n".join([
                f"✅ {action_title}",
                "━━━━━━━━━━━━━━━━━━",
                f"🆔 UID: {uid}",
                f"📄 UIDPASS File: {UIDPASS_FILE_SETS[set_name][0]}",
                f"🎟 Token File: {token_file}",
                "✅ Token Result: Success",
            ])
        else:
            text = "\n".join([
                f"⚠️ {action_title}",
                "━━━━━━━━━━━━━━━━━━",
                f"🆔 UID: {uid}",
                f"📄 UIDPASS File: {UIDPASS_FILE_SETS[set_name][0]}",
                "❌ Token Result: Failed",
                "",
                output[-2500:] if output else f"Exit code {code}",
            ])
        bot.edit_message_text(chat_id=status_msg.chat.id, message_id=status_msg.message_id, text=text, parse_mode=None)
    except Exception as exc:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ SINGLE TOKEN REFRESH FAILED\n━━━━━━━━━━━━━━━━━━\n🆔 UID: {uid}\n{exc}",
            parse_mode=None,
        )


@bot.message_handler(commands=["uidpass", "uidpassff"])
def uidpass_command(message):
    if not is_owner(message.from_user.id):
        return
    command = (message.text.split()[0] or "").split("@", 1)[0].lstrip("/").lower()
    set_name = "likeff" if command == "uidpassff" else "like"
    parts = message.text.split(maxsplit=3)
    usage = f"⚠️ Invalid format.\n📌 Use: /{command} <ls|add|set|del|up> [uid] [password]"
    if len(parts) < 2:
        bot.reply_to(message, usage, parse_mode=None)
        return

    action = parts[1].lower()
    action = {
        "list": "ls",
        "edit": "set",
        "update": "up",
        "delete": "del",
        "remove": "del",
    }.get(action, action)

    try:
        accounts = load_uidpass(set_name)
    except Exception as exc:
        bot.reply_to(message, f"❌ UIDPASS LOAD FAILED\n━━━━━━━━━━━━━━━━━━\n{exc}", parse_mode=None)
        return

    if action == "ls":
        tokens = load_token_list(set_name)
        counts = region_counts(tokens)
        lines = [
            "📊 UIDPASS SUMMARY",
            "━━━━━━━━━━━━━━━━━━",
            f"📦 Set: {set_name}",
            f"👥 UIDPASS Accounts: {len(accounts)}",
            f"🎟 Tokens: {len(tokens)}",
            "",
            "🌍 Regions:",
        ]
        if not counts:
            lines.append("ℹ️ No tokens found.")
        else:
            for region, count in sorted(counts.items()):
                lines.append(f"› {region}: {count}")
        bot.reply_to(message, "\n".join(lines), parse_mode=None)
        return

    if action == "add":
        if len(parts) < 4:
            bot.reply_to(message, f"⚠️ Invalid format.\n📌 Use: /{command} add <uid> <password>", parse_mode=None)
            return
        uid, password = parts[2], parts[3]
        if not uid.isdigit():
            bot.reply_to(message, "⚠️ Invalid UID.\n📌 UID must be a number.", parse_mode=None)
            return
        if find_uidpass_index(accounts, uid) != -1:
            bot.reply_to(message, "ℹ️ UID already exists.\n📌 Use set to change the password.", parse_mode=None)
            return
        accounts.append({"uid": uid, "password": password})
        save_uidpass(set_name, accounts)
        threading.Thread(
            target=process_single_uidpass_token_update,
            args=(message, set_name, uid, password, "UIDPASS ACCOUNT ADDED"),
            daemon=True,
        ).start()
        return

    if action == "set":
        if len(parts) < 4:
            bot.reply_to(message, f"⚠️ Invalid format.\n📌 Use: /{command} set <uid> <new_password>", parse_mode=None)
            return
        uid, password = parts[2], parts[3]
        if not uid.isdigit():
            bot.reply_to(message, "⚠️ Invalid UID.\n📌 UID must be a number.", parse_mode=None)
            return
        index = find_uidpass_index(accounts, uid)
        if index == -1:
            bot.reply_to(message, "ℹ️ UID not found.", parse_mode=None)
            return
        accounts[index]["password"] = password
        save_uidpass(set_name, accounts)
        threading.Thread(
            target=process_single_uidpass_token_update,
            args=(message, set_name, uid, password, "UIDPASS ACCOUNT UPDATED"),
            daemon=True,
        ).start()
        return

    if action == "del":
        if len(parts) < 3 or not parts[2].isdigit():
            bot.reply_to(message, f"⚠️ Invalid format.\n📌 Use: /{command} del <uid>", parse_mode=None)
            return
        uid = parts[2]
        index = find_uidpass_index(accounts, uid)
        if index == -1:
            bot.reply_to(message, "ℹ️ UID not found.", parse_mode=None)
            return
        accounts.pop(index)
        save_uidpass(set_name, accounts)
        bot.reply_to(message, f"✅ UIDPASS ACCOUNT DELETED\n━━━━━━━━━━━━━━━━━━\n🆔 UID: {uid}\n📄 File: {UIDPASS_FILE_SETS[set_name][0]}", parse_mode=None)
        return

    if action == "up":
        threading.Thread(target=process_uidpass_update, args=(message, set_name), daemon=True).start()
        return

    bot.reply_to(message, usage, parse_mode=None)


@bot.message_handler(commands=["ban"])
def ban_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /ban <user_id>.", parse_mode=None)
        return
    bot.ban_chat_member(message.chat.id, target.id)
    bot.reply_to(message, f"🚫 USER BANNED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["unban"])
def unban_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Use: /unban <user_id>", parse_mode=None)
        return
    bot.unban_chat_member(message.chat.id, target.id)
    bot.reply_to(message, f"✅ USER UNBANNED\n━━━━━━━━━━━━━━━━━━\n🆔 UID: {target.id}", parse_mode=None)


@bot.message_handler(commands=["kick"])
def kick_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /kick <user_id>.", parse_mode=None)
        return
    bot.ban_chat_member(message.chat.id, target.id, until_date=datetime.utcnow() + timedelta(seconds=45))
    bot.reply_to(message, f"👢 USER KICKED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["tban"])
def tban_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 2)
    target = get_target_user(message)
    duration_arg = parts[1] if message.reply_to_message and len(parts) > 1 else (parts[2].split()[0] if len(parts) > 2 else "")
    delta = parse_duration(duration_arg)
    if not target or not delta:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Reply with /tban 1h or use /tban <user_id> 1h.", parse_mode=None)
        return
    bot.ban_chat_member(message.chat.id, target.id, until_date=datetime.utcnow() + delta)
    bot.reply_to(message, f"🚫 TEMP BAN APPLIED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}\n⏳ Duration: {duration_arg}", parse_mode=None)


@bot.message_handler(commands=["mute"])
def mute_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /mute <user_id>.", parse_mode=None)
        return
    bot.restrict_chat_member(message.chat.id, target.id, permissions=muted_permissions())
    bot.reply_to(message, f"🔇 USER MUTED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["tmute"])
def tmute_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 2)
    target = get_target_user(message)
    duration_arg = parts[1] if message.reply_to_message and len(parts) > 1 else (parts[2].split()[0] if len(parts) > 2 else "")
    delta = parse_duration(duration_arg)
    if not target or not delta:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Reply with /tmute 10m or use /tmute <user_id> 10m.", parse_mode=None)
        return
    bot.restrict_chat_member(message.chat.id, target.id, permissions=muted_permissions(), until_date=datetime.utcnow() + delta)
    bot.reply_to(message, f"🔇 TEMP MUTE APPLIED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}\n⏳ Duration: {duration_arg}", parse_mode=None)


@bot.message_handler(commands=["unmute"])
def unmute_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /unmute <user_id>.", parse_mode=None)
        return
    bot.restrict_chat_member(message.chat.id, target.id, permissions=normal_permissions())
    bot.reply_to(message, f"✅ USER UNMUTED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["warn"])
def warn_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /warn <user_id> [reason].", parse_mode=None)
        return
    reason = "No reason"
    if message.reply_to_message:
        parts = split_command(message, 1)
        reason = parts[1] if len(parts) > 1 else reason
    else:
        parts = split_command(message, 2)
        reason = parts[2] if len(parts) > 2 else reason
    bot.reply_to(message, warn_user(message.chat.id, target, reason))


@bot.message_handler(commands=["unwarn"])
def unwarn_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /unwarn <user_id>.", parse_mode=None)
        return
    key = (message.chat.id, target.id)
    warns_db[key] = max(0, warns_db.get(key, 0) - 1)
    bot.reply_to(message, f"✅ WARN REMOVED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}\n⚠️ Warns: {warns_db[key]}/{MAX_WARNS}", parse_mode=None)


@bot.message_handler(commands=["resetwarns"])
def reset_warns_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /resetwarns <user_id>.", parse_mode=None)
        return
    warns_db[(message.chat.id, target.id)] = 0
    bot.reply_to(message, f"✅ WARNS RESET\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["warns"])
def warns_command(message):
    target = get_target_user(message) or message.from_user
    count = warns_db.get((message.chat.id, target.id), 0)
    bot.reply_to(message, f"⚠️ WARN STATUS\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}\n📊 Warns: {count}/{MAX_WARNS}", parse_mode=None)


@bot.message_handler(commands=["pin"])
def pin_command(message):
    if not require_admin(message) or not message.reply_to_message:
        bot.reply_to(message, "⚠️ Reply to a message with /pin.", parse_mode=None)
        return
    bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
    bot.reply_to(message, "📌 MESSAGE PINNED", parse_mode=None)


@bot.message_handler(commands=["unpin"])
def unpin_command(message):
    if not require_admin(message):
        return
    bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id if message.reply_to_message else None)
    bot.reply_to(message, "✅ MESSAGE UNPINNED", parse_mode=None)


@bot.message_handler(commands=["unpinall"])
def unpinall_command(message):
    if not require_admin(message):
        return
    bot.unpin_all_chat_messages(message.chat.id)
    bot.reply_to(message, "✅ ALL PINNED MESSAGES REMOVED", parse_mode=None)


@bot.message_handler(commands=["del"])
def delete_command(message):
    if not require_admin(message) or not message.reply_to_message:
        bot.reply_to(message, "⚠️ Reply to a message with /del.", parse_mode=None)
        return
    safe_delete(message.chat.id, message.reply_to_message.message_id)
    safe_delete(message.chat.id, message.message_id)


@bot.message_handler(commands=["purge"])
def purge_command(message):
    if not require_admin(message) or not message.reply_to_message:
        bot.reply_to(message, "⚠️ Reply to the first message and use /purge.", parse_mode=None)
        return
    deleted = 0
    for message_id in range(message.reply_to_message.message_id, message.message_id + 1):
        if safe_delete(message.chat.id, message_id):
            deleted += 1
    bot.send_message(message.chat.id, f"🧹 PURGE COMPLETE\n━━━━━━━━━━━━━━━━━━\n🗑 Deleted: {deleted} messages", parse_mode=None)


@bot.message_handler(commands=["promote"])
def promote_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /promote <user_id>.", parse_mode=None)
        return
    bot.promote_chat_member(
        message.chat.id,
        target.id,
        can_change_info=True,
        can_delete_messages=True,
        can_invite_users=True,
        can_restrict_members=True,
        can_pin_messages=True,
        can_promote_members=False,
    )
    bot.reply_to(message, f"✅ USER PROMOTED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["demote"])
def demote_command(message):
    if not require_admin(message):
        return
    target = get_target_user(message)
    if not target:
        bot.reply_to(message, "⚠️ Target required.\n📌 Reply to a user or use /demote <user_id>.", parse_mode=None)
        return
    bot.promote_chat_member(
        message.chat.id,
        target.id,
        can_change_info=False,
        can_delete_messages=False,
        can_invite_users=False,
        can_restrict_members=False,
        can_pin_messages=False,
        can_promote_members=False,
    )
    bot.reply_to(message, f"✅ USER DEMOTED\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(target)}", parse_mode=None)


@bot.message_handler(commands=["save"])
def save_note_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 2)
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /save <name> <text>", parse_mode=None)
        return
    notes_db.setdefault(message.chat.id, {})[parts[1].lower()] = parts[2]
    bot.reply_to(message, f"✅ NOTE SAVED\n━━━━━━━━━━━━━━━━━━\n📝 Name: {parts[1].lower()}", parse_mode=None)


@bot.message_handler(commands=["get"])
def get_note_command(message):
    parts = split_command(message, 1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /get <name>", parse_mode=None)
        return
    text = notes_db.get(message.chat.id, {}).get(parts[1].lower())
    bot.reply_to(message, text or "ℹ️ Note not found.", parse_mode=None)


@bot.message_handler(commands=["notes"])
def notes_command(message):
    notes = sorted(notes_db.get(message.chat.id, {}))
    bot.reply_to(message, "📝 NOTES\n━━━━━━━━━━━━━━━━━━\n" + ", ".join(notes) if notes else "ℹ️ No notes saved.", parse_mode=None)


@bot.message_handler(commands=["clear"])
def clear_note_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /clear <name>", parse_mode=None)
        return
    removed = notes_db.get(message.chat.id, {}).pop(parts[1].lower(), None)
    bot.reply_to(message, "✅ NOTE REMOVED" if removed else "ℹ️ Note not found.", parse_mode=None)


@bot.message_handler(commands=["clearall"])
def clearall_notes_command(message):
    if not require_admin(message):
        return
    notes_db[message.chat.id] = {}
    bot.reply_to(message, "✅ ALL NOTES REMOVED", parse_mode=None)


@bot.message_handler(commands=["filter"])
def filter_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 2)
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /filter <word> <reply>", parse_mode=None)
        return
    filters_db.setdefault(message.chat.id, {})[parts[1].lower()] = parts[2]
    bot.reply_to(message, f"✅ FILTER SAVED\n━━━━━━━━━━━━━━━━━━\n🔎 Trigger: {parts[1].lower()}", parse_mode=None)


@bot.message_handler(commands=["filters"])
def filters_command(message):
    filters = sorted(filters_db.get(message.chat.id, {}))
    bot.reply_to(message, "🔎 FILTERS\n━━━━━━━━━━━━━━━━━━\n" + ", ".join(filters) if filters else "ℹ️ No filters saved.", parse_mode=None)


@bot.message_handler(commands=["stop"])
def stop_filter_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /stop <word>", parse_mode=None)
        return
    removed = filters_db.get(message.chat.id, {}).pop(parts[1].lower(), None)
    bot.reply_to(message, "✅ FILTER REMOVED" if removed else "ℹ️ Filter not found.", parse_mode=None)


@bot.message_handler(commands=["stopall"])
def stopall_filters_command(message):
    if not require_admin(message):
        return
    filters_db[message.chat.id] = {}
    bot.reply_to(message, "✅ ALL FILTERS REMOVED", parse_mode=None)


@bot.message_handler(commands=["setrules"])
def setrules_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /setrules <rules text>", parse_mode=None)
        return
    rules_db[message.chat.id] = parts[1]
    bot.reply_to(message, "✅ RULES SAVED", parse_mode=None)


@bot.message_handler(commands=["rules"])
def rules_command(message):
    bot.reply_to(message, rules_db.get(message.chat.id, "ℹ️ No rules set."), parse_mode=None)


@bot.message_handler(commands=["clearrules"])
def clearrules_command(message):
    if not require_admin(message):
        return
    rules_db.pop(message.chat.id, None)
    bot.reply_to(message, "✅ RULES REMOVED", parse_mode=None)


@bot.message_handler(commands=["setwelcome"])
def setwelcome_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2:
        pending_template_db[(message.chat.id, message.from_user.id)] = "welcome"
        bot.reply_to(message, template_help_text(message.from_user.first_name), parse_mode=None)
        return
    welcome_db[message.chat.id] = parts[1]
    bot.reply_to(message, "✅ WELCOME MESSAGE SAVED", parse_mode=None)


@bot.message_handler(commands=["welcome"])
def welcome_command(message):
    bot.reply_to(message, welcome_db.get(message.chat.id, "ℹ️ No welcome message set."), parse_mode=None)


@bot.message_handler(commands=["clearwelcome"])
def clearwelcome_command(message):
    if not require_admin(message):
        return
    welcome_db.pop(message.chat.id, None)
    bot.reply_to(message, "✅ WELCOME MESSAGE REMOVED", parse_mode=None)


@bot.message_handler(commands=["setgoodbye"])
def setgoodbye_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2:
        pending_template_db[(message.chat.id, message.from_user.id)] = "goodbye"
        bot.reply_to(message, template_help_text(message.from_user.first_name), parse_mode=None)
        return
    goodbye_db[message.chat.id] = parts[1]
    bot.reply_to(message, "✅ GOODBYE MESSAGE SAVED", parse_mode=None)


@bot.message_handler(commands=["goodbye"])
def goodbye_command(message):
    bot.reply_to(message, goodbye_db.get(message.chat.id, "ℹ️ No goodbye message set."), parse_mode=None)


@bot.message_handler(commands=["cleargoodbye"])
def cleargoodbye_command(message):
    if not require_admin(message):
        return
    goodbye_db.pop(message.chat.id, None)
    bot.reply_to(message, "✅ GOODBYE MESSAGE REMOVED", parse_mode=None)


@bot.message_handler(commands=["lock"])
def lock_command(message):
    if not require_admin(message):
        return
    bot.set_chat_permissions(message.chat.id, muted_permissions())
    locked_db[message.chat.id] = True
    bot.reply_to(message, "🔒 CHAT LOCKED\n━━━━━━━━━━━━━━━━━━\nOnly allowed members can send messages.", parse_mode=None)


@bot.message_handler(commands=["unlock"])
def unlock_command(message):
    if not require_admin(message):
        return
    bot.set_chat_permissions(message.chat.id, normal_permissions())
    locked_db[message.chat.id] = False
    bot.reply_to(message, "🔓 CHAT UNLOCKED\n━━━━━━━━━━━━━━━━━━\nMembers can send messages again.", parse_mode=None)


@bot.message_handler(commands=["lockall"])
def lockall_command(message):
    lock_command(message)


@bot.message_handler(commands=["unlockall"])
def unlockall_command(message):
    unlock_command(message)


@bot.message_handler(commands=["locks"])
def locks_command(message):
    chat_id = message.chat.id
    bot.reply_to(
        message,
        "\n".join([
            "🔐 PROTECTION STATUS",
            "━━━━━━━━━━━━━━━━━━",
            f"🔒 Chat Lock: {'ON' if locked_db.get(chat_id) else 'OFF'}",
            f"🔗 Link Ban: {'ON' if linkban_db.get(chat_id) else 'OFF'}",
            f"🚫 Spam Ban: {'ON' if spamban_db.get(chat_id) else 'OFF'}",
        ]),
        parse_mode=None,
    )


@bot.message_handler(commands=["linkban"])
def linkban_command(message):
    parts = split_command(message, 1)
    if len(parts) < 2:
        state = "ON" if linkban_db.get(message.chat.id) else "OFF"
        bot.reply_to(message, f"🔗 LINK BAN STATUS\n━━━━━━━━━━━━━━━━━━\n📌 Status: {state}\n⚙️ Use: /linkban on or /linkban off", parse_mode=None)
        return
    if not require_admin(message):
        return
    if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /linkban on or /linkban off", parse_mode=None)
        return
    linkban_db[message.chat.id] = parts[1].lower() == "on"
    bot.reply_to(message, f"✅ LINK BAN UPDATED\n━━━━━━━━━━━━━━━━━━\n📌 Status: {parts[1].upper()}", parse_mode=None)


@bot.message_handler(commands=["spamban"])
def spamban_command(message):
    parts = split_command(message, 1)
    if len(parts) < 2:
        state = "ON" if spamban_db.get(message.chat.id) else "OFF"
        bot.reply_to(message, f"🚫 SPAM BAN STATUS\n━━━━━━━━━━━━━━━━━━\n📌 Status: {state}\n⚙️ Use: /spamban on or /spamban off", parse_mode=None)
        return
    if not require_admin(message):
        return
    if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /spamban on or /spamban off", parse_mode=None)
        return
    spamban_db[message.chat.id] = parts[1].lower() == "on"
    bot.reply_to(message, f"✅ SPAM BAN UPDATED\n━━━━━━━━━━━━━━━━━━\n📌 Status: {parts[1].upper()}", parse_mode=None)


@bot.message_handler(commands=["setflood"])
def setflood_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) < 2 or not parts[1].isdigit():
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /setflood <messages>", parse_mode=None)
        return
    flood_db[message.chat.id] = int(parts[1])
    bot.reply_to(message, f"✅ FLOOD LIMIT UPDATED\n━━━━━━━━━━━━━━━━━━\n📊 Limit: {parts[1]}", parse_mode=None)


@bot.message_handler(commands=["flood"])
def flood_command(message):
    bot.reply_to(message, f"📊 FLOOD LIMIT\n━━━━━━━━━━━━━━━━━━\nLimit: {flood_db.get(message.chat.id, FLOOD_LIMIT)}", parse_mode=None)


@bot.message_handler(commands=["noflood"])
def noflood_command(message):
    if not require_admin(message):
        return
    flood_db[message.chat.id] = 0
    bot.reply_to(message, "✅ FLOOD PROTECTION OFF", parse_mode=None)


@bot.message_handler(commands=["afk", "brb"])
def afk_command(message):
    parts = split_command(message, 1)
    afk_db[message.from_user.id] = {
        "since": datetime.utcnow(),
        "reason": parts[1] if len(parts) > 1 else "AFK",
    }
    bot.reply_to(message, f"🌙 AFK ENABLED\n━━━━━━━━━━━━━━━━━━\n👤 User: {message.from_user.first_name}", parse_mode=None)


@bot.message_handler(commands=["id"])
def id_command(message):
    if not is_owner(message.from_user.id):
        return
    raw = getattr(message, "json", {}) or {}
    raw_reply = raw.get("reply_to_message") if isinstance(raw, dict) else None
    raw_from = raw_reply.get("from") if isinstance(raw_reply, dict) else None
    raw_sender_chat = raw_reply.get("sender_chat") if isinstance(raw_reply, dict) else None
    replied_user = getattr(message.reply_to_message, "from_user", None) if message.reply_to_message else None
    sender_chat = getattr(message.reply_to_message, "sender_chat", None) if message.reply_to_message else None

    if replied_user:
        remember_user(replied_user)
        bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n👤 User ID: {replied_user.id}\n💬 Chat ID: {message.chat.id}", parse_mode=None)
        return

    if isinstance(raw_from, dict):
        bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n👤 User ID: {raw_from.get('id')}\n💬 Chat ID: {message.chat.id}", parse_mode=None)
        return

    if sender_chat:
        bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n📣 Sender Chat ID: {sender_chat.id}\n💬 Chat ID: {message.chat.id}", parse_mode=None)
        return

    if isinstance(raw_sender_chat, dict):
        bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n📣 Sender Chat ID: {raw_sender_chat.get('id')}\n💬 Chat ID: {message.chat.id}", parse_mode=None)
        return

    parts = split_command(message, 1)
    target = get_target_user(message) if len(parts) > 1 else None
    if target:
        if getattr(target, "id", None) is None:
            bot.reply_to(
                message,
                f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n👤 Username: @{target.username}\n🆔 User ID: not available\n💬 Chat ID: {message.chat.id}\n📌 Reply to the user or use numeric ID to get exact user ID.",
                parse_mode=None,
            )
            return
        bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n👤 User ID: {target.id}\n💬 Chat ID: {message.chat.id}", parse_mode=None)
        return

    logger.warning(
        "/id had no reply target. message_id=%s chat_id=%s raw_reply_present=%s telebot_reply_present=%s raw_keys=%s",
        getattr(message, "message_id", None),
        getattr(message.chat, "id", None),
        isinstance(raw_reply, dict),
        bool(getattr(message, "reply_to_message", None)),
        sorted(raw.keys()) if isinstance(raw, dict) else [],
    )
    bot.reply_to(message, f"🆔 TELEGRAM IDS\n━━━━━━━━━━━━━━━━━━\n👤 Your ID: {message.from_user.id}\n💬 Chat ID: {message.chat.id}", parse_mode=None)


@bot.message_handler(commands=["info", "tginfo"])
def tginfo_command(message):
    if not is_owner(message.from_user.id):
        return
    target = get_target_user(message) or message.from_user
    if getattr(target, "id", None) is None:
        bot.reply_to(
            message,
            f"👤 USER INFO\n━━━━━━━━━━━━━━━━━━\nUsername: @{target.username}\n🆔 User ID: not available\n📌 Reply to the user or use numeric ID to get exact info.",
            parse_mode=None,
        )
        return
    try:
        member = bot.get_chat_member(message.chat.id, target.id)
        remember_user(member.user)
        status = member.status
        is_bot_user = member.user.is_bot
        target = member.user
    except Exception:
        status = "unknown"
        is_bot_user = getattr(target, "is_bot", False)
    bot.reply_to(
        message,
        "\n".join([
            "👤 USER INFO",
            "━━━━━━━━━━━━━━━━━━",
            f"🏷 Name: {getattr(target, 'first_name', '')}",
            f"🆔 ID: {target.id}",
            f"🔗 Username: @{target.username}" if getattr(target, "username", None) else "🔗 Username: N/A",
            f"🤖 Bot: {'Yes' if is_bot_user else 'No'}",
            f"📌 Status: {status}",
        ]),
        parse_mode=None,
    )


@bot.message_handler(commands=["adminlist"])
def adminlist_command(message):
    if not is_owner(message.from_user.id):
        return
    admins = bot.get_chat_administrators(message.chat.id)
    lines = ["👮 ADMIN LIST", "━━━━━━━━━━━━━━━━━━"]
    for admin in admins:
        remember_user(admin.user)
        role = "Owner" if admin.status == "creator" else "Admin"
        lines.append(f"› {role}: {user_label(admin.user)}")
    bot.reply_to(message, "\n".join(lines), parse_mode=None)


@bot.message_handler(commands=["chatinfo"])
def chatinfo_command(message):
    if not is_owner(message.from_user.id):
        return
    chat = bot.get_chat(message.chat.id)
    try:
        members = bot.get_chat_member_count(message.chat.id)
    except Exception:
        members = "N/A"
    bot.reply_to(
        message,
        "\n".join([
            "💬 CHAT INFO",
            "━━━━━━━━━━━━━━━━━━",
            f"🏷 Title: {chat.title or chat.first_name}",
            f"🆔 ID: {chat.id}",
            f"👥 Members: {members}",
            f"🔗 Username: @{chat.username}" if getattr(chat, "username", None) else "🔗 Username: N/A",
            f"📌 Type: {chat.type}",
            f"🔒 Lock: {'ON' if locked_db.get(chat.id) else 'OFF'}",
            f"🔗 Link Ban: {'ON' if linkban_db.get(chat.id) else 'OFF'}",
            f"🚫 Spam Ban: {'ON' if spamban_db.get(chat.id) else 'OFF'}",
        ]),
        parse_mode=None,
    )


@bot.message_handler(commands=["stats"])
def stats_command(message):
    if not is_owner(message.from_user.id):
        return
    bot.reply_to(
        message,
        "\n".join([
            "📊 BOT STATS",
            "━━━━━━━━━━━━━━━━━━",
            f"📝 Notes: {sum(len(v) for v in notes_db.values())}",
            f"🔎 Filters: {sum(len(v) for v in filters_db.values())}",
            f"⚠️ Warns: {sum(warns_db.values())}",
            f"🎮 Tracked FF users: {len(usage_tracker)}",
            f"👑 Owner ID: {OWNER_ID or 'not set'}",
        ]),
        parse_mode=None,
    )


@bot.message_handler(commands=["report"])
def report_command(message):
    if not is_owner(message.from_user.id):
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Reply to a message with /report.", parse_mode=None)
        return
    reason = "No reason"
    parts = split_command(message, 1)
    if len(parts) > 1:
        reason = parts[1]
    admins = bot.get_chat_administrators(message.chat.id)
    mentions = [f"@{admin.user.username}" for admin in admins if not admin.user.is_bot and admin.user.username]
    if not mentions:
        mentions = [user_label(admin.user) for admin in admins if not admin.user.is_bot]
    bot.reply_to(
        message.reply_to_message,
        "\n".join([
            "🚨 REPORT",
            "━━━━━━━━━━━━━━━━━━",
            f"👤 Reporter: {user_label(message.from_user)}",
            f"🎯 Reported: {user_label(message.reply_to_message.from_user)}",
            f"📌 Reason: {reason}",
            "👮 Admins: " + " ".join(mentions),
        ]),
        parse_mode=None,
    )


@bot.message_handler(commands=["ping"])
def ping_command(message):
    if not is_owner(message.from_user.id):
        return
    started = time.time()
    sent = bot.reply_to(message, "🏓 Checking latency...", parse_mode=None)
    elapsed = int((time.time() - started) * 1000)
    bot.edit_message_text(f"🏓 PONG\n━━━━━━━━━━━━━━━━━━\n⏱ Latency: {elapsed}ms", sent.chat.id, sent.message_id)


@bot.message_handler(commands=["calc"])
def calc_command(message):
    if not is_owner(message.from_user.id):
        return
    parts = split_command(message, 1)
    if len(parts) < 2 or not re.fullmatch(r"[0-9+\-*/(). %]+", parts[1]):
        bot.reply_to(message, "⚠️ Invalid format.\n📌 Use: /calc 1+2*3", parse_mode=None)
        return
    try:
        result = eval(parts[1], {"__builtins__": {}}, {})
        bot.reply_to(message, f"🧮 CALC RESULT\n━━━━━━━━━━━━━━━━━━\n{parts[1]} = {result}", parse_mode=None)
    except Exception as exc:
        bot.reply_to(message, f"❌ CALC FAILED\n━━━━━━━━━━━━━━━━━━\n{exc}", parse_mode=None)


@bot.message_handler(commands=["echo"])
def echo_command(message):
    if not require_admin(message):
        return
    parts = split_command(message, 1)
    if len(parts) > 1:
        safe_delete(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, parts[1], parse_mode=None)


@bot.message_handler(commands=["time"])
def time_command(message):
    if not is_owner(message.from_user.id):
        return
    bot.reply_to(message, f"🕒 CURRENT TIME\n━━━━━━━━━━━━━━━━━━\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", parse_mode=None)


@bot.message_handler(commands=["owner"])
def owner_command(message):
    if not is_owner(message.from_user.id):
        return
    bot.reply_to(message, f"👑 OWNER INFO\n━━━━━━━━━━━━━━━━━━\n🆔 Owner ID: {OWNER_ID or 'not set'}", parse_mode=None)


@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_members(message):
    safe_delete(message.chat.id, message.message_id)
    template = welcome_db.get(message.chat.id)
    for member in message.new_chat_members:
        remember_user(member)
    if not template:
        return
    for member in message.new_chat_members:
        text = render_member_template(template, member, message.chat)
        bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(content_types=["left_chat_member"])
def goodbye_member(message):
    safe_delete(message.chat.id, message.message_id)
    template = goodbye_db.get(message.chat.id)
    if not template:
        return
    member = message.left_chat_member
    text = render_member_template(template, member, message.chat)
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(content_types=["text"], func=lambda message: not (message.text or "").startswith("/"))
def watch_text(message):
    text = message.text or ""
    chat_id = message.chat.id
    user_id = message.from_user.id
    lower_text = text.lower()
    remember_user(message.from_user)
    if message.reply_to_message and getattr(message.reply_to_message, "from_user", None):
        remember_user(message.reply_to_message.from_user)

    pending_kind = pending_template_db.pop((chat_id, user_id), None)
    if pending_kind:
        if not is_admin(chat_id, user_id):
            bot.reply_to(message, "⛔ Admin-only action.", parse_mode=None)
            return
        if pending_kind == "welcome":
            welcome_db[chat_id] = text
            bot.reply_to(message, "✅ WELCOME MESSAGE SAVED", parse_mode=None)
        else:
            goodbye_db[chat_id] = text
            bot.reply_to(message, "✅ GOODBYE MESSAGE SAVED", parse_mode=None)
        return

    if user_id in afk_db:
        afk_db.pop(user_id, None)
        bot.reply_to(message, "✅ WELCOME BACK", parse_mode=None)

    replied_user = getattr(message.reply_to_message, "from_user", None) if message.reply_to_message else None
    if replied_user and replied_user.id in afk_db:
        afk = afk_db[replied_user.id]
        since = datetime.utcnow() - afk["since"]
        bot.reply_to(message, f"🌙 USER IS AFK\n━━━━━━━━━━━━━━━━━━\n⏳ Away for: {str(since).split('.')[0]}\n📌 Reason: {afk['reason']}", parse_mode=None)

    if linkban_db.get(chat_id) and LINK_PATTERN.search(text) and not is_admin(chat_id, user_id):
        safe_delete(chat_id, message.message_id)
        bot.send_message(chat_id, warn_user(chat_id, message.from_user, "Links are not allowed."), parse_mode=None)
        return

    now = time.time()
    key = (chat_id, user_id)
    recent = [ts for ts in spam_track.get(key, []) if now - ts < 10]
    recent.append(now)
    spam_track[key] = recent
    flood_limit = flood_db.get(chat_id, FLOOD_LIMIT)
    if flood_limit <= 0:
        return
    if len(recent) > flood_limit and not is_admin(chat_id, user_id):
        bot.restrict_chat_member(chat_id, user_id, permissions=muted_permissions(), until_date=datetime.utcnow() + timedelta(minutes=5))
        bot.send_message(chat_id, f"🔇 FLOOD PROTECTION\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(message.from_user)}\n⏳ Muted for 5 minutes.", parse_mode=None)
        return
    if spamban_db.get(chat_id) and len(recent) > SPAM_LIMIT and not is_admin(chat_id, user_id):
        bot.ban_chat_member(chat_id, user_id)
        bot.send_message(chat_id, f"🚫 SPAM PROTECTION\n━━━━━━━━━━━━━━━━━━\n👤 User: {user_label(message.from_user)}\n📌 Action: banned", parse_mode=None)
        return

    for trigger, reply in filters_db.get(chat_id, {}).items():
        if trigger in lower_text:
            bot.reply_to(message, reply, parse_mode=None)
            return

    if text.startswith("#") and len(text) > 1:
        name = text[1:].split()[0].lower()
        note = notes_db.get(chat_id, {}).get(name)
        if note:
            bot.reply_to(message, note, parse_mode=None)


def process_autolikeff_orders():
    while True:
        try:
            now = datetime.now(CAMBODIA_TZ)
            run_time = autolike_run_datetime(now)
            if now < run_time:
                time.sleep(min(AUTOLIKEFF_CHECK_INTERVAL, max(1, (run_time - now).total_seconds())))
                continue

            period = current_autolike_period(now)
            with autolike_lock:
                orders = load_autolike_orders()

            changed = False
            for order in orders:
                if order.get("status") != "active":
                    continue
                sent, total, remaining = autolike_order_status(order)
                if remaining <= 0:
                    order["status"] = "completed"
                    changed = True
                    continue
                next_run_date = order.get("next_run_date") or period
                if next_run_date > period:
                    continue
                if order.get("last_attempt_period") == period or order.get("last_period") == period:
                    continue

                deliver_autolikeff_order(order, period=period, schedule_next=True)
                changed = True
                time.sleep(AUTOLIKEFF_ORDER_DELAY)

            if changed:
                with autolike_lock:
                    merge_save_autolike_orders(orders)
        except Exception:
            logger.exception("AutoLikeFF worker failed")
        time.sleep(AUTOLIKEFF_CHECK_INTERVAL)


def autolike_notice_datetime(value=None):
    value = value or datetime.now(CAMBODIA_TZ)
    return value.replace(hour=AUTOLIKEFF_NOTICE_HOUR, minute=AUTOLIKEFF_NOTICE_MINUTE, second=0, microsecond=0)


def format_autolike_near_end_notice(order):
    sent, total, remaining = autolike_order_status(order)
    progress = (sent / total * 100) if total > 0 else 0
    owner_contact = owner_contact_text()
    return "\n".join([
        "🔔 AutoLikeFF Renewal Reminder",
        "━━━━━━━━━━━━━━━━━━",
        f"🆔 UID: {order.get('uid', 'N/A')}",
        f"👤 Player: {order.get('player_name') or 'N/A'}",
        f"✅ Delivered: {sent:,}/{total:,}",
        f"📈 Progress: {progress:.2f}%",
        f"⏳ Remaining: {max(0, remaining):,}",
        "",
        "⚠️ Your AutoLikeFF is near to end.",
        f"🚀 Contact {owner_contact} to renew AutoLikeFF.",
    ])


def process_autolikeff_near_end_notices():
    while True:
        try:
            now = datetime.now(CAMBODIA_TZ)
            notice_time = autolike_notice_datetime(now)
            if now < notice_time:
                time.sleep(min(AUTOLIKEFF_CHECK_INTERVAL, max(1, (notice_time - now).total_seconds())))
                continue

            period = current_autolike_period(now)
            with autolike_lock:
                orders = load_autolike_orders()

            changed = False
            for order in orders:
                if order.get("status") != "active":
                    continue
                sent, total, remaining = autolike_order_status(order)
                if remaining <= 0 or remaining > AUTOLIKEFF_NEAR_END_THRESHOLD:
                    continue
                if order.get("last_near_end_notice_period") == period:
                    continue
                user_id = order.get("telegram_user_id")
                if not user_id:
                    continue
                try:
                    bot.send_message(int(user_id), format_autolike_near_end_notice(order), parse_mode=None)
                    order["last_near_end_notice_period"] = period
                    changed = True
                except Exception as exc:
                    logger.warning("AutoLikeFF near-end notice failed for %s: %s", user_id, exc)

            if changed:
                with autolike_lock:
                    merge_save_autolike_orders(orders)
        except Exception:
            logger.exception("AutoLikeFF near-end notice worker failed")
        time.sleep(AUTOLIKEFF_CHECK_INTERVAL)


def process_auto_token_refresh():
    while True:
        try:
            logger.info("Starting automatic token refresh for all token sets")
            for set_name in UIDPASS_FILE_SETS:
                try:
                    code, output = run_token_update(set_name)
                    if code == 0:
                        logger.info("Automatic token refresh completed for %s", set_name)
                    else:
                        logger.warning("Automatic token refresh failed for %s: %s", set_name, output[-1000:])
                        if OWNER_ID:
                            report = output
                            marker = "UID/PASS Token Refresh Report"
                            if marker in report:
                                line_start = report.rfind("\n", 0, report.find(marker))
                                report = report[(line_start + 1) if line_start >= 0 else report.find(marker):]
                            text = "\n".join([
                                f"⚠️ {set_name.upper()} TOKEN REFRESH FAILED",
                                "━━━━━━━━━━━━━━━━━━",
                                report[:3500],
                            ])
                            try:
                                bot.send_message(OWNER_ID, text, parse_mode=None)
                            except Exception as send_exc:
                                logger.warning("Could not send token refresh report to owner: %s", send_exc)
                except Exception as exc:
                    logger.warning("Automatic token refresh crashed for %s: %s", set_name, exc)
            logger.info("Next automatic token refresh in 7 hours")
        except Exception:
            logger.exception("Automatic token refresh worker failed")
        time.sleep(TOKEN_AUTO_REFRESH_INTERVAL)


if __name__ == "__main__":
    if not acquire_bot_instance_lock():
        raise SystemExit(1)
    threading.Thread(target=reset_limits, daemon=True).start()
    threading.Thread(target=process_autolikeff_orders, daemon=True).start()
    threading.Thread(target=process_autolikeff_near_end_notices, daemon=True).start()
    threading.Thread(target=process_auto_token_refresh, daemon=True).start()
    logger.info("Bot started. API_BASE_URL=%s FILE=%s", API_BASE_URL, os.path.abspath(__file__))
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30, none_stop=True)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception:
            logger.exception("Polling crashed; restarting in 5 seconds")
            time.sleep(5)
