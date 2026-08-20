#Owner : @vaibhavff570
#Join : @vaibhavapix, @vaibhavapisx
import asyncio
import time
import httpx
import json
import threading
import base64
import requests
import urllib3
import random
import string
import codecs
import os
import ipaddress
from urllib.parse import urlparse, parse_qs, quote
from collections import defaultdict
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
from typing import Tuple
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2, MajorLoginReq_pb2, MajorLoginRes_pb2, like_pb2, like_count_pb2
from google.protobuf import json_format, message
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
from Crypto.Cipher import AES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

G = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
F = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
REGNS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EU", "EUROPE"}

FAHHHH = Flask(__name__)
CORS(FAHHHH)
app = FAHHHH
if hasattr(FAHHHH, "json"):
    FAHHHH.json.sort_keys = False
else:
    FAHHHH.config["JSON_SORT_KEYS"] = False

http_session = requests.Session()
TOKENS = defaultdict(dict)
UID_MEMORY = {}
REGION_CACHE_LOCK = threading.Lock()
HTTP_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
CLIENT_ID = "100067"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
FF_NICKNAME_KEY = b"1e5898ccb8dfdd921f9bdea848768b64a201"
CAMBODIA_TZ = timezone(timedelta(hours=7), "ICT")
UIDPASS_FILE = "uidpass.json"
LIKE_TOKEN_FILE = "tokens.json"
LIKEFF_UIDPASS_FILE = "uidpass_likeff.json"
LIKEFF_TOKEN_FILE = "tokens_likeff.json"
REGION_CACHE_FILE = "regions.json"
LIKE_TOKEN_MAX_RETRIES = 10
LIKE_TOKEN_RETRY_DELAY = 0.7
BIO_MAJOR_LOGIN_URL = "https://loginbp.ggblueshark.com/MajorLogin"
BIO_OAUTH_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
BIO_INSPECT_URL = "https://100067.connect.garena.com/oauth/token/inspect"
BIO_FREEFIRE_VERSION = "OB54"
BIO_UPDATE_URLS = [
    "https://client.ind.freefiremobile.com/UpdateSocialBasicInfo",
    "https://clientbp.ggblueshark.com/UpdateSocialBasicInfo",
    "https://client.us.freefiremobile.com/UpdateSocialBasicInfo",
    "https://clientbp.common.ggbluefox.com/UpdateSocialBasicInfo",
]
BIO_HEADERS = {
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": BIO_FREEFIRE_VERSION,
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}
BIO_LOGIN_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/octet-stream",
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": BIO_FREEFIRE_VERSION,
}
BAN_REASON_MAP = {
    0: "Unknown",
    1: "In-game automatic ban",
    2: "Refund-related ban",
    3: "Other reason",
    4: "Skin/modification ban",
    1014: "New in-game automatic ban",
}
REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn","PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt","SG":"en"}
REGION_IP_CIDRS = {
    "BD": ["27.147.128.0/17", "37.111.192.0/19", "49.0.32.0/20", "59.152.96.0/20", "114.130.0.0/17"],
    "IND": ["1.6.0.0/15", "1.38.0.0/15", "14.96.0.0/15", "27.4.0.0/14", "27.56.0.0/13"],
    "ID": ["36.64.0.0/11", "101.255.0.0/16", "103.10.60.0/22", "114.120.0.0/13"],
    "TH": ["1.46.0.0/15", "27.55.0.0/16", "49.228.0.0/15", "101.108.0.0/15"],
    "VN": ["1.52.0.0/14", "14.160.0.0/11", "27.64.0.0/12", "113.160.0.0/12"],
    "PK": ["39.32.0.0/11", "111.68.96.0/19", "182.176.0.0/12"],
    "ME": ["2.88.0.0/13", "5.100.0.0/14", "31.166.0.0/15", "37.104.0.0/13"],
    "BR": ["177.0.0.0/13", "186.192.0.0/12", "189.0.0.0/11", "200.96.0.0/12"],
    "EU": ["2.16.0.0/12", "5.144.0.0/14", "31.40.0.0/14", "46.16.0.0/14"],
    "EUROPE": ["2.16.0.0/12", "5.144.0.0/14", "31.40.0.0/14", "46.16.0.0/14"],
    "CIS": ["2.92.0.0/14", "5.136.0.0/13", "31.128.0.0/12", "46.0.0.0/12"],
    "NA": ["3.0.0.0/9", "8.0.0.0/12", "12.0.0.0/10", "24.0.0.0/10"],
    "US": ["3.0.0.0/9", "8.0.0.0/12", "12.0.0.0/10", "24.0.0.0/10"],
    "SAC": ["186.0.0.0/10", "190.0.0.0/11", "200.0.0.0/11"],
    "TW": ["1.160.0.0/12", "36.224.0.0/12", "114.24.0.0/12", "118.160.0.0/12"],
    "SG": ["103.1.0.0/16", "116.12.0.0/16", "165.21.0.0/16", "202.156.0.0/14", "203.116.0.0/15"],
}
BR_RANK_SCORES = [
    {"min": 1000, "max": 1099, "rank": "Bronze I"},
    {"min": 1100, "max": 1199, "rank": "Bronze II"},
    {"min": 1200, "max": 1299, "rank": "Bronze III"},
    {"min": 1300, "max": 1399, "rank": "Silver I"},
    {"min": 1400, "max": 1499, "rank": "Silver II"},
    {"min": 1500, "max": 1599, "rank": "Silver III"},
    {"min": 1600, "max": 1724, "rank": "Gold I"},
    {"min": 1725, "max": 1849, "rank": "Gold II"},
    {"min": 1850, "max": 1974, "rank": "Gold III"},
    {"min": 1975, "max": 2099, "rank": "Gold IV"},
    {"min": 2100, "max": 2224, "rank": "Platinum I"},
    {"min": 2225, "max": 2349, "rank": "Platinum II"},
    {"min": 2350, "max": 2474, "rank": "Platinum III"},
    {"min": 2475, "max": 2599, "rank": "Platinum IV"},
    {"min": 2600, "max": 2749, "rank": "Platinum V"},
    {"min": 2750, "max": 2899, "rank": "Diamond I"},
    {"min": 2900, "max": 3049, "rank": "Diamond II"},
    {"min": 3050, "max": 3199, "rank": "Diamond III"},
    {"min": 3200, "max": 3349, "rank": "Diamond IV"},
    {"min": 3350, "max": 3499, "rank": "Diamond V"},
    {"min": 3500, "max": 3799, "rank": "Heroic ★"},
    {"min": 3800, "max": 4299, "rank": "Heroic ★★"},
    {"min": 4300, "max": 4899, "rank": "Elite Heroic [ Heroic ★★★]"},
    {"min": 4900, "max": 5499, "rank": "Elite Heroic [ Heroic ★★★★]"},
    {"min": 5500, "max": 6299, "rank": "Elite Heroic [ Heroic ★★★★★]"},
    {"min": 6300, "max": 7099, "rank": "Master"},
    {"min": 7100, "max": 7999, "rank": "Master ★★"},
    {"min": 8000, "max": 8999, "rank": "Elite Master [ Master ★★★]"},
    {"min": 9000, "max": 9999, "rank": "Elite Master [ Master ★★★★]"},
    {"min": 10000, "max": 19999, "rank": "Elite Master [ Master ★★★★★]"},
    {"min": 20000, "max": 999999, "rank": "Grand Master"},
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
def BmwNoNoBmvYas(d):
    l = AES.block_size - (len(d) % AES.block_size)
    return d + bytes([l] * l)

def BmwNoiNoiBmvYasYas(k, i, d):
    a = AES.new(k, AES.MODE_CBC, i)
    return a.encrypt(BmwNoNoBmvYas(d))

_sym_db = _symbol_database.Default()

def register_embedded_proto(filename, serialized, module_name):
    pool = _descriptor_pool.Default()
    try:
        descriptor = pool.AddSerializedFile(serialized)
    except Exception:
        descriptor = pool.FindFileByName(filename)
    _builder.BuildMessageAndEnumDescriptors(descriptor, globals())
    _builder.BuildTopDescriptorsAndMessages(descriptor, module_name, globals())

register_embedded_proto(
    "my.proto",
    b'\n\x08my.proto\"\xae\t\n\x08GameData\x12\x11\n\ttimestamp\x18\x03 \x01(\t\x12\x11\n\tgame_name\x18\x04 \x01(\t\x12\x14\n\x0cgame_version\x18\x05 \x01(\x05\x12\x14\n\x0cversion_code\x18\x07 \x01(\t\x12\x0f\n\x07os_info\x18\x08 \x01(\t\x12\x13\n\x0b\x64\x65vice_type\x18\t \x01(\t\x12\x18\n\x10network_provider\x18\n \x01(\t\x12\x17\n\x0f\x63onnection_type\x18\x0b \x01(\t\x12\x14\n\x0cscreen_width\x18\x0c \x01(\x05\x12\x15\n\rscreen_height\x18\r \x01(\x05\x12\x0b\n\x03\x64pi\x18\x0e \x01(\t\x12\x10\n\x08\x63pu_info\x18\x0f \x01(\t\x12\x11\n\ttotal_ram\x18\x10 \x01(\x05\x12\x10\n\x08gpu_name\x18\x11 \x01(\t\x12\x13\n\x0bgpu_version\x18\x12 \x01(\t\x12\x0f\n\x07user_id\x18\x13 \x01(\t\x12\x12\n\nip_address\x18\x14 \x01(\t\x12\x10\n\x08language\x18\x15 \x01(\t\x12\x0f\n\x07open_id\x18\x16 \x01(\t\x12\x15\n\rplatform_type\x18\x17 \x01(\x05\x12\x1a\n\x12\x64\x65vice_form_factor\x18\x18 \x01(\t\x12\x14\n\x0c\x64\x65vice_model\x18\x19 \x01(\t\x12\x14\n\x0c\x61\x63\x63\x65ss_token\x18\x1d \x01(\t\x12\x18\n\x10unknown_field_30\x18\x1e \x01(\x05\x12\"\n\x1asecondary_network_provider\x18) \x01(\t\x12!\n\x19secondary_connection_type\x18* \x01(\t\x12\x11\n\tunique_id\x18\x39 \x01(\t\x12\x10\n\x08\x66ield_60\x18< \x01(\x05\x12\x10\n\x08\x66ield_61\x18= \x01(\x05\x12\x10\n\x08\x66ield_62\x18> \x01(\x05\x12\x10\n\x08\x66ield_63\x18? \x01(\x05\x12\x10\n\x08\x66ield_64\x18@ \x01(\x05\x12\x10\n\x08\x66ield_65\x18\x41 \x01(\x05\x12\x10\n\x08\x66ield_66\x18\x42 \x01(\x05\x12\x10\n\x08\x66ield_67\x18\x43 \x01(\x05\x12\x10\n\x08\x66ield_70\x18\x46 \x01(\x05\x12\x10\n\x08\x66ield_73\x18I \x01(\x05\x12\x14\n\x0clibrary_path\x18J \x01(\t\x12\x10\n\x08\x66ield_76\x18L \x01(\x05\x12\x10\n\x08\x61pk_info\x18M \x01(\t\x12\x10\n\x08\x66ield_78\x18N \x01(\x05\x12\x10\n\x08\x66ield_79\x18O \x01(\x05\x12\x17\n\x0fos_architecture\x18Q \x01(\t\x12\x14\n\x0c\x62uild_number\x18S \x01(\t\x12\x10\n\x08\x66ield_85\x18U \x01(\x05\x12\x18\n\x10graphics_backend\x18V \x01(\t\x12\x19\n\x11max_texture_units\x18W \x01(\x05\x12\x15\n\rrendering_api\x18X \x01(\x05\x12\x18\n\x10\x65ncoded_field_89\x18Y \x01(\t\x12\x10\n\x08\x66ield_92\x18\\ \x01(\x05\x12\x13\n\x0bmarketplace\x18] \x01(\t\x12\x16\n\x0e\x65ncryption_key\x18^ \x01(\t\x12\x15\n\rtotal_storage\x18_ \x01(\x05\x12\x10\n\x08\x66ield_97\x18\x61 \x01(\x05\x12\x10\n\x08\x66ield_98\x18\x62 \x01(\x05\x12\x10\n\x08\x66ield_99\x18\x63 \x01(\t\x12\x11\n\tfield_100\x18\x64 \x01(\tb\x06proto3',
    "my_pb2",
)
register_embedded_proto(
    "jwt_generator.proto",
    b'\n\x13jwt_generator.proto\"\xd2\x02\n\nGarena_420\x12\x12\n\naccount_id\x18\x01 \x01(\x03\x12\x0e\n\x06region\x18\x02 \x01(\t\x12\r\n\x05place\x18\x03 \x01(\t\x12\x10\n\x08location\x18\x04 \x01(\t\x12\x0e\n\x06status\x18\x05 \x01(\t\x12\r\n\x05token\x18\x08 \x01(\t\x12\n\n\x02id\x18\t \x01(\x05\x12\x0b\n\x03\x61pi\x18\n \x01(\t\x12\x0e\n\x06number\x18\x0c \x01(\x05\x12\x1e\n\tGarena420\x18\x0f \x01(\x0b\x32\x0b.Garena_420\x12\x0c\n\x04\x61rea\x18\x10 \x01(\t\x12\x11\n\tmain_area\x18\x12 \x01(\t\x12\x0c\n\x04\x63ity\x18\x13 \x01(\t\x12\x0c\n\x04name\x18\x14 \x01(\t\x12\x11\n\ttimestamp\x18\x15 \x01(\x03\x12\x0e\n\x06\x62inary\x18\x16 \x01(\x0c\x12\x13\n\x0b\x62inary_data\x18\x17 \x01(\x0c\x1a\"\n\x12\x44\x65\x63rypted_Payloads\x12\x0c\n\x04type\x18\x01 \x01(\x05b\x06proto3',
    "output_pb2",
)
register_embedded_proto(
    "data.proto",
    b'\n\ndata.proto\"\xbb\x01\n\x04\x44\x61ta\x12\x0f\n\x07\x66ield_2\x18\x02 \x01(\x05\x12\x1e\n\x07\x66ield_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage\x12\x1e\n\x07\x66ield_6\x18\x06 \x01(\x0b\x32\r.EmptyMessage\x12\x0f\n\x07\x66ield_8\x18\x08 \x01(\t\x12\x0f\n\x07\x66ield_9\x18\t \x01(\x05\x12\x1f\n\x08\x66ield_11\x18\x0b \x01(\x0b\x32\r.EmptyMessage\x12\x1f\n\x08\x66ield_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage\"\x0e\n\x0c\x45mptyMessageb\x06proto3',
    "data_pb2",
)
GameData = _sym_db.GetSymbol("GameData")
Garena_420 = _sym_db.GetSymbol("Garena_420")
BioData = _sym_db.GetSymbol("Data")
EmptyMessage = _sym_db.GetSymbol("EmptyMessage")

def format_ttl(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours} hours, {minutes} mins, {secs} secs"

def decode_ff_nickname(encoded):
    try:
        raw = base64.b64decode(encoded)
        dec = bytearray()
        for i, b in enumerate(raw):
            dec.append(b ^ FF_NICKNAME_KEY[i % len(FF_NICKNAME_KEY)])
        return dec.decode('utf-8', errors='replace')
    except Exception:
        return "Unknown"

def maybe_decode_ff_nickname(value):
    if not isinstance(value, str) or not value:
        return value
    if len(value) < 8 or any(ch.isspace() for ch in value):
        return value
    if not all(ch.isalnum() or ch in "+/=_-" for ch in value):
        return value
    decoded = decode_ff_nickname(value)
    if decoded and decoded != "Unknown" and decoded.count("�") <= 1:
        return decoded
    return value

def decode_profile_names(data):
    if isinstance(data, dict):
        for key in ("nickname", "name", "PlayerNickname", "playerNickname", "captainName", "clanName"):
            if key in data:
                data[key] = maybe_decode_ff_nickname(data[key])
        for value in data.values():
            if isinstance(value, (dict, list)):
                decode_profile_names(value)
    elif isinstance(data, list):
        for item in data:
            decode_profile_names(item)
    return data

def decode_bio_jwt(token):
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode("utf-8", errors="replace"))
        name = maybe_decode_ff_nickname(decoded.get("nickname"))
        return {
            "uid": decoded.get("external_uid") or decoded.get("account_id"),
            "account_id": decoded.get("account_id"),
            "name": name,
            "nickname": name,
            "region": decoded.get("lock_region") or decoded.get("noti_region"),
        }
    except Exception:
        return None

def bio_guest_login(uid, password):
    payload = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": CLIENT_SECRET,
        "client_id": CLIENT_ID,
    }
    headers = {"User-Agent": "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)"}
    response = http_session.post(BIO_OAUTH_URL, data=payload, headers=headers, timeout=15, verify=False)
    data = response_json_or_text(response)
    if response.status_code != 200 or not isinstance(data, dict):
        return None, None, data
    return data.get("access_token"), data.get("open_id"), data

def get_bio_openid_from_inspect(access_token):
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Accept": "application/json"}
    response = http_session.get(f"{BIO_INSPECT_URL}?token={access_token}", headers=headers, timeout=15, verify=False)
    data = response_json_or_text(response)
    if response.status_code != 200 or not isinstance(data, dict):
        return None, data
    return data.get("open_id"), data

def bio_major_login(access_token, open_id):
    for platform_type in (8, 3, 4, 6):
        try:
            game = GameData()
            game.timestamp = "2024-12-05 18:15:32"
            game.game_name = "free fire"
            game.game_version = 1
            game.version_code = "2.124.1"
            game.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
            game.device_type = "Handheld"
            game.network_provider = "Verizon Wireless"
            game.connection_type = "WIFI"
            game.screen_width = 1280
            game.screen_height = 960
            game.dpi = "240"
            game.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
            game.total_ram = 5951
            game.gpu_name = "Adreno (TM) 640"
            game.gpu_version = "OpenGL ES 3.0"
            game.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
            game.ip_address = "172.190.111.97"
            game.language = "en"
            game.open_id = open_id
            game.access_token = access_token
            game.platform_type = platform_type
            game.field_99 = str(platform_type)
            game.field_100 = str(platform_type)

            encrypted = BmwNoiNoiBmvYasYas(G, F, game.SerializeToString())
            response = http_session.post(BIO_MAJOR_LOGIN_URL, data=encrypted, headers=BIO_LOGIN_HEADERS, verify=False, timeout=15)
            if response.status_code == 200:
                msg = Garena_420()
                msg.ParseFromString(response.content)
                if msg.token:
                    return msg.token, platform_type
        except Exception:
            continue
    return None, None

def update_social_bio(jwt_token, bio_text):
    data = BioData()
    data.field_2 = 17
    data.field_5.CopyFrom(EmptyMessage())
    data.field_6.CopyFrom(EmptyMessage())
    data.field_8 = bio_text
    data.field_9 = 1
    data.field_11.CopyFrom(EmptyMessage())
    data.field_12.CopyFrom(EmptyMessage())
    encrypted = BmwNoiNoiBmvYasYas(G, F, data.SerializeToString())

    headers = BIO_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    last_error = None
    for url in BIO_UPDATE_URLS:
        try:
            response = http_session.post(url, headers=headers, data=encrypted, timeout=20, verify=False)
            if response.status_code == 200:
                return response, url
            last_error = f"{url} returned HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = f"{url}: {exc}"
    raise RuntimeError(last_error or "All update endpoints failed")

def extract_nickname_from_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload_b64 = parts[1]
            payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
            if 'nickname' in payload and isinstance(payload['nickname'], str):
                return decode_ff_nickname(payload['nickname'])
    except Exception:
        pass
    return "Unknown"

def convert_timestamps_to_human(data):
    if isinstance(data, dict):
        if "ban_reason" in data:
            reason_code = to_int(data.get("ban_reason"))
            data["ban_reason"] = BAN_REASON_MAP.get(reason_code, f"Unknown reason ({reason_code})")
        if "ban_time" in data:
            ban_time = to_int(data.get("ban_time"))
            if ban_time and 1000000000 < ban_time < 3000000000:
                human_time = datetime.fromtimestamp(ban_time, CAMBODIA_TZ).strftime('%Y-%m-%d %H:%M:%S ICT')
                data["ban_time"] = f"{ban_time} ({human_time})"
        if "expire_duration" in data:
            expire_duration = to_int(data.get("expire_duration"))
            if expire_duration and 1000000000 < expire_duration < 3000000000:
                human_time = datetime.fromtimestamp(expire_duration, CAMBODIA_TZ).strftime('%Y-%m-%d %H:%M:%S ICT')
                data["expire_duration"] = f"{expire_duration} ({human_time})"
        for k, v in data.items():
            if isinstance(v, (int, float)) and 1000000000 < v < 3000000000:
                try:
                    human_time = datetime.fromtimestamp(v, CAMBODIA_TZ).strftime('%Y-%m-%d %H:%M:%S ICT')
                    data[k] = f"{v} ({human_time})"
                except Exception:
                    pass
            elif isinstance(v, (dict, list)):
                convert_timestamps_to_human(v)
    elif isinstance(data, list):
        for i in range(len(data)):
            if isinstance(data[i], (int, float)) and 1000000000 < data[i] < 3000000000:
                try:
                    human_time = datetime.fromtimestamp(data[i], CAMBODIA_TZ).strftime('%Y-%m-%d %H:%M:%S ICT')
                    data[i] = f"{data[i]} ({human_time})"
                except Exception:
                    pass
            elif isinstance(data[i], (dict, list)):
                convert_timestamps_to_human(data[i])
    return data

def build_major_login_request(open_id, access_token):
    req_msg = MajorLoginReq_pb2.MajorLogin()
    req_msg.event_time = str(int(time.time()))
    req_msg.game_name = "free fire"
    req_msg.platform_id = 1
    req_msg.client_version = "1.111.1"
    req_msg.system_software = "Android OS 13 / API-33"
    req_msg.system_hardware = "CPH2095"
    req_msg.telecom_operator = "N/A"
    req_msg.network_type = "WIFI"
    req_msg.screen_width = 1080
    req_msg.screen_height = 2400
    req_msg.screen_dpi = "480"
    req_msg.processor_details = "ARMv8"
    req_msg.memory = 4096
    req_msg.gpu_renderer = "Adreno (TM) 610"
    req_msg.gpu_version = "OpenGL ES 3.2"
    req_msg.unique_device_id = "2f6f0d08-3c2b-4f9f-9d2f-1f2c4a5b6c7d"
    req_msg.client_ip = "0.0.0.0"
    req_msg.language = "en"
    req_msg.open_id = open_id
    req_msg.open_id_type = "4"
    req_msg.device_type = "android"
    req_msg.memory_available.version = 1
    req_msg.memory_available.hidden_value = 0
    req_msg.access_token = access_token
    req_msg.platform_sdk_id = 1
    req_msg.network_operator_a = "N/A"
    req_msg.network_type_a = "WIFI"
    req_msg.client_using_version = "1.111.1"
    req_msg.external_storage_total = 64000
    req_msg.external_storage_available = 32000
    req_msg.internal_storage_total = 64000
    req_msg.internal_storage_available = 32000
    req_msg.game_disk_storage_available = 32000
    req_msg.game_disk_storage_total = 64000
    req_msg.external_sdcard_avail_storage = 0
    req_msg.external_sdcard_total_storage = 0
    req_msg.login_by = 3
    req_msg.library_path = "/data/app/com.dts.freefireth/lib/arm64"
    req_msg.reg_avatar = 1
    req_msg.library_token = ""
    req_msg.channel_type = 3
    req_msg.cpu_type = 2
    req_msg.cpu_architecture = "arm64-v8a"
    req_msg.client_version_code = "OB54"
    req_msg.graphics_api = "OpenGLES2"
    req_msg.supported_astc_bitset = 0
    req_msg.login_open_id_type = 4
    req_msg.analytics_detail = b""
    req_msg.loading_time = 0
    req_msg.release_channel = "android"
    req_msg.extra_info = ""
    req_msg.android_engine_init_flag = 1
    req_msg.if_push = 1
    req_msg.is_vpn = 0
    req_msg.origin_platform_type = "4"
    req_msg.primary_platform_type = "4"
    return req_msg

def encode_varint(value):
    result = b''
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            result += bytes([to_write | 0x80])
        else:
            result += bytes([to_write])
            break
    return result

def create_proto_field(field_num, value):
    if isinstance(value, int):
        return encode_varint(field_num << 3) + encode_varint(value)
    if isinstance(value, (str, bytes)):
        encoded_val = value.encode() if isinstance(value, str) else value
        return encode_varint((field_num << 3) | 2) + encode_varint(len(encoded_val)) + encoded_val
    return b''

def build_proto(fields):
    return b''.join(create_proto_field(k, v) for k, v in fields.items())

def generate_exponent():
    exp_digits = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}
    num = random.randint(1, 9999)
    return ''.join(exp_digits[d] for d in f"{num:04d}")

def generate_random_name(base):
    return f"{base}{generate_exponent()}"

def generate_custom_password(user_prefix):
    return "MEAN" + ''.join(random.choice('0123456789ABCDEF') for _ in range(60))

def major_register_url(region, is_ghost=False):
    if is_ghost:
        return "https://loginbp.ggblueshark.com/MajorRegister"
    return "https://loginbp.ggblueshark.com/MajorRegister"

def major_login_url(region, is_ghost=False):
    if is_ghost:
        return "https://loginbp.ggblueshark.com/MajorLogin"
    return "https://loginbp.ggblueshark.com/MajorLogin"

def get_region_proxies(region):
    candidates = get_region_proxy_candidates(region)
    proxy_url = candidates[0] if candidates else None
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}

def get_region_proxy_candidates(region):
    return [None]

def is_valid_proxy_url(proxy_url):
    try:
        parsed = urlparse(proxy_url)
        if parsed.scheme not in {"http", "https", "socks4", "socks5", "socks5h"}:
            return False
        if not parsed.hostname or parsed.hostname.endswith("-proxy-host"):
            return False
        return parsed.port is not None
    except ValueError:
        return False

def random_ip_from_cidr(cidr):
    try:
        network = ipaddress.IPv4Network(cidr, strict=False)
        if network.num_addresses > 2:
            offset = random.randint(1, network.num_addresses - 2)
        else:
            offset = 0
        return str(ipaddress.IPv4Address(int(network.network_address) + offset))
    except Exception:
        return "103.220.220.10"

def get_region_ip(region):
    region = (region or "BD").upper()
    cidrs = REGION_IP_CIDRS.get(region)
    if not cidrs:
        cidrs = random.choice(list(REGION_IP_CIDRS.values()))
    return random_ip_from_cidr(random.choice(cidrs))

def with_region_ip_headers(headers, region):
    client_ip = get_region_ip(region)
    updated = headers.copy()
    updated["X-Forwarded-For"] = client_ip
    updated["X-Real-IP"] = client_ip
    updated["Client-IP"] = client_ip
    updated["CF-Connecting-IP"] = client_ip
    updated["True-Client-IP"] = client_ip
    return updated

def response_json_or_text(response):
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}

def extract_bio_access_token(raw):
    raw = str(raw or "").strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://")):
        try:
            params = parse_qs(urlparse(raw).query)
            if params.get("access_token"):
                return params["access_token"][0]
        except Exception:
            return None
        return None
    if all(ch in "abcdefghijklmnopqrstuvwxyz0123456789" for ch in raw):
        return raw
    return None

def looks_like_jwt(raw):
    raw = str(raw or "").strip()
    return raw.count(".") == 2 and raw.startswith("eyJ")

def parse_bio_api_response(response):
    data = response_json_or_text(response)
    if response.status_code >= 400:
        message = None
        if isinstance(data, dict):
            message = data.get("message") or data.get("status") or data.get("error")
        message = message or response.text[:300] or f"HTTP {response.status_code}"
        raise ValueError(message)
    return data

def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def get_br_rank_name(points):
    points = to_int(points)
    if points is None:
        return None
    for rank_info in BR_RANK_SCORES:
        if rank_info["min"] <= points <= rank_info["max"]:
            return rank_info["rank"]
    return None

def get_cs_rank_name(rank_id):
    rank_id = to_int(rank_id)
    if rank_id is None:
        return None
    return CS_RANK_MAPPING.get(rank_id)

def normalize_bearer_token(token):
    token = str(token or "").strip()
    if not token:
        return None
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"

def decode_jwt_payload(token):
    try:
        raw_token = str(token or "").replace("Bearer ", "", 1).strip()
        parts = raw_token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception:
        return {}

def load_like_tokens(region=None, token_file=LIKE_TOKEN_FILE):
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    region = normalize_region(region) if region else None
    tokens = []
    for item in items if isinstance(items, list) else []:
        token = item.get("token") if isinstance(item, dict) else None
        if not token:
            continue
        item_region = normalize_region(item.get("region")) if isinstance(item, dict) else ""
        if not item_region:
            item_region = normalize_region(decode_jwt_payload(token).get("lock_region"))
        if region and item_region and item_region != region:
            continue
        normalized = normalize_bearer_token(token)
        if normalized:
            tokens.append(normalized)
    return tokens

def load_region_cache():
    try:
        with REGION_CACHE_LOCK:
            with open(REGION_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_region_cache(cache):
    with REGION_CACHE_LOCK:
        with open(REGION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)

def get_cached_region(uid):
    item = load_region_cache().get(str(uid))
    if isinstance(item, dict):
        return normalize_region(item.get("region")) or None
    if isinstance(item, str):
        return normalize_region(item) or None
    return None

def set_cached_region(uid, region):
    region = normalize_region(region)
    if not region:
        return
    cache = load_region_cache()
    cache[str(uid)] = {
        "uid": str(uid),
        "region": region,
        "updated_at": datetime.now(CAMBODIA_TZ).isoformat(),
    }
    save_region_cache(cache)

def fetch_guest_jwt_for_like(uid, password):
    uid_int = int(uid)
    auth_response = http_session.post(
        "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant",
        json={
            "client_id": 100067,
            "client_secret": CLIENT_SECRET,
            "client_type": 2,
            "password": password,
            "response_type": "token",
            "uid": uid_int,
        },
        timeout=15,
    )
    auth_data = response_json_or_text(auth_response)
    inner = auth_data.get("data", {}) if isinstance(auth_data, dict) else {}
    access_token = inner.get("access_token")
    open_id = inner.get("open_id")
    if not access_token or not open_id:
        raise ValueError("guest token grant did not return access_token/open_id")

    req_msg = build_major_login_request(open_id, access_token)
    login_response = http_session.post(
        "https://loginbp.ggpolarbear.com/MajorLogin",
        data=BmwNoiNoiBmvYasYas(G, F, req_msg.SerializeToString()),
        headers={
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "User-Agent": USERAGENT,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
        },
        verify=False,
        timeout=15,
    )
    login_response.raise_for_status()
    res_msg = MajorLoginRes_pb2.MajorLoginRes()
    res_msg.ParseFromString(login_response.content)
    major_login = MessageToDict(res_msg, preserving_proto_field_name=True)
    jwt_token = major_login.get("token")
    if not jwt_token:
        raise ValueError("MajorLogin did not return jwt token")
    jwt_payload = decode_jwt_payload(jwt_token)
    account_id = major_login.get("account_id") or jwt_payload.get("account_id")
    region = major_login.get("lock_region") or major_login.get("noti_region")
    return {
        "uid": str(uid),
        "account_id": account_id,
        "name": extract_nickname_from_jwt(jwt_token),
        "region": region,
        "token": jwt_token,
    }

def fetch_guest_jwt_for_like_with_retry(uid, password, max_retries=LIKE_TOKEN_MAX_RETRIES, retry_delay=LIKE_TOKEN_RETRY_DELAY):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_guest_jwt_for_like(uid, password)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise last_error

def update_tokens_from_uidpass(uidpass_file, token_file):
    try:
        with open(uidpass_file, "r", encoding="utf-8") as f:
            accounts = json.load(f)
    except FileNotFoundError:
        print(f"{uidpass_file} not found; skipping token update.")
        return
    except Exception as e:
        print(f"Failed to read {uidpass_file}: {e}")
        return

    if not isinstance(accounts, list):
        print(f"{uidpass_file} must contain a list; skipping token update.")
        return

    tokens = []
    failures = []
    for account in accounts:
        uid = account.get("uid") if isinstance(account, dict) else None
        password = account.get("password") if isinstance(account, dict) else None
        if not uid or not password:
            failures.append({"uid": uid, "error": "missing uid or password"})
            continue
        try:
            tokens.append(fetch_guest_jwt_for_like_with_retry(uid, password))
        except Exception as e:
            failures.append({"uid": uid, "error": str(e)})

    try:
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=4)
        print(f"{token_file} updated with {len(tokens)} token(s).")
    except Exception as e:
        print(f"Failed to write {token_file}: {e}")

    if failures:
        print(f"Like token update failures: {failures}")

def update_like_tokens_from_uidpass():
    update_tokens_from_uidpass(UIDPASS_FILE, LIKE_TOKEN_FILE)

def update_likeff_tokens_from_uidpass():
    update_tokens_from_uidpass(LIKEFF_UIDPASS_FILE, LIKEFF_TOKEN_FILE)

def normalize_region(region):
    region = str(region or "").strip().upper()
    if region == "EUROPE":
        return "EU"
    return region

def is_region_match(requested_region, actual_region):
    requested_region = normalize_region(requested_region)
    actual_region = normalize_region(actual_region)
    if {requested_region, actual_region} == {"CIS", "RU"}:
        return True
    if {requested_region, actual_region} == {"US", "NA"}:
        return True
    return not actual_region or requested_region == actual_region

def create_guest_account(region, account_name, password_prefix, is_ghost=False):
    region = normalize_region(region)
    errors = []
    max_attempts = 5 if not is_ghost else 1
    for _ in range(max_attempts):
        for proxy_url in get_region_proxy_candidates(region):
            try:
                result = create_guest_account_with_proxy(region, account_name, password_prefix, is_ghost, proxy_url)
                actual_region = result.get("region")
                if result.get("success") and not is_region_match(region, actual_region):
                    errors.append({
                        "uid": result.get("uid"),
                        "requested_region": region,
                        "actual_region": actual_region,
                        "error": "Created account region did not match requested region.",
                    })
                    continue
                return result
            except Exception as e:
                errors.append({
                    "error": str(e),
                })
                continue
    return {
        "success": False,
        "guest_created": False,
        "uid": None,
        "password": None,
        "requested_region": region,
        "error": "Could not create account in requested region",
        "attempts": errors,
    }

def create_guest_account_with_proxy(region, account_name, password_prefix, is_ghost=False, proxy_url=None):
    password = generate_custom_password(password_prefix)
    region = normalize_region(region)
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    register_headers = with_region_ip_headers({
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.39(SM-A325M;Android 13;en;HK;)",
    }, region)
    register_response = http_session.post(
        "https://100067.connect.garena.com/api/v2/oauth/guest:register",
        headers=register_headers,
        json={"app_id": 100067, "client_type": 2, "password": password, "source": 2},
        timeout=15,
        verify=False,
        proxies=proxies,
    )
    if register_response.status_code != 200:
        return {
            "success": False,
            "guest_created": False,
            "uid": None,
            "password": password,
            "requested_region": region,
            "error": f"Guest register failed with status {register_response.status_code}",
            "details": register_response.text[:500],
        }
    register_data = response_json_or_text(register_response)
    uid = register_data.get("data", {}).get("uid")
    if not uid:
        return {
            "success": False,
            "guest_created": False,
            "uid": None,
            "password": password,
            "requested_region": region,
            "error": "Guest register did not return uid",
            "register_response": register_data,
        }

    token_form_headers = with_region_ip_headers({
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
    }, region)
    token_form_payload = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": CLIENT_SECRET,
        "client_id": CLIENT_ID,
    }
    token_response = None
    token_attempts = [
        {
            "url": "https://100067.connect.garena.com/oauth/guest/token/grant",
            "headers": token_form_headers,
            "kwargs": {"data": token_form_payload},
        },
        {
            "url": "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant",
            "headers": with_region_ip_headers({
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "Accept-Encoding": "gzip",
                "Connection": "Keep-Alive",
                "Host": "100067.connect.garena.com",
                "User-Agent": "GarenaMSDK/4.0.39(SM-A325M;Android 13;en;HK;)",
            }, region),
            "kwargs": {
                "json": {
                    "client_id": 100067,
                    "client_secret": CLIENT_SECRET,
                    "client_type": 2,
                    "password": password,
                    "response_type": "token",
                    "uid": int(uid),
                }
            },
        },
    ]
    token_errors = []
    for attempt in token_attempts:
        token_response = http_session.post(
            attempt["url"],
            headers=attempt["headers"],
            timeout=15,
            verify=False,
            proxies=proxies,
            **attempt["kwargs"],
        )
        if token_response.status_code == 200:
            break
        token_errors.append({
            "url": attempt["url"],
            "status_code": token_response.status_code,
            "details": token_response.text[:300],
        })
    if token_response.status_code != 200:
        return {
            "success": True,
            "guest_created": True,
            "uid": uid,
            "password": password,
            "name": None,
            "requested_region": "GHOST" if is_ghost else region,
            "region": "GHOST" if is_ghost else region,
            "access_token": None,
            "account_id": None,
            "jwt_token": None,
            "warning": f"Guest created, but token grant failed with status {token_response.status_code}",
            "details": token_response.text[:500],
            "token_attempts": token_errors,
        }
    token_data = response_json_or_text(token_response)
    if "data" in token_data and isinstance(token_data["data"], dict):
        token_data = token_data["data"]
    access_token = token_data.get("access_token")
    open_id = token_data.get("open_id")
    if not access_token or not open_id:
        return {
            "success": True,
            "guest_created": True,
            "uid": uid,
            "password": password,
            "name": None,
            "requested_region": "GHOST" if is_ghost else region,
            "region": "GHOST" if is_ghost else region,
            "access_token": None,
            "account_id": None,
            "jwt_token": None,
            "warning": "Guest created, but token grant did not return access_token/open_id",
            "token_response": token_data,
        }

    keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = ''.join(chr(ord(open_id[i]) ^ keystream[i % len(keystream)]) for i in range(len(open_id)))
    field = codecs.decode(''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded), 'unicode_escape').encode('latin1')
    name = generate_random_name(account_name)
    lang_code = "pt" if is_ghost else REGION_LANG.get(region, "en")
    payload = build_proto({1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1, 14: field, 15: lang_code, 16: 1, 17: 1})
    reg_url = major_register_url(region, is_ghost)
    major_register_headers = with_region_ip_headers({
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": reg_url.split('/')[2],
        "ReleaseVersion": "OB54",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
    }, region)
    major_register_response = http_session.post(
        reg_url,
        headers=major_register_headers,
        data=BmwNoiNoiBmvYasYas(G, F, payload),
        timeout=15,
        verify=False,
        proxies=proxies,
    )

    req_msg = build_major_login_request(open_id, access_token)
    login_url = major_login_url(region, is_ghost)
    major_login_headers = with_region_ip_headers({
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54",
        "Content-Type": "application/octet-stream",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "Host": login_url.split('/')[2],
    }, region)
    login_response = http_session.post(
        login_url,
        headers=major_login_headers,
        data=BmwNoiNoiBmvYasYas(G, F, req_msg.SerializeToString()),
        timeout=15,
        verify=False,
        proxies=proxies,
    )

    account_id = None
    jwt_token = None
    actual_region = None
    major_login = {"status_code": login_response.status_code}
    if login_response.status_code == 200 and login_response.content:
        res_msg = MajorLoginRes_pb2.MajorLoginRes()
        res_msg.ParseFromString(login_response.content)
        major_login = MessageToDict(res_msg, preserving_proto_field_name=True)
        account_id = major_login.get("account_id")
        jwt_token = major_login.get("token")
        actual_region = major_login.get("lock_region") or major_login.get("noti_region")

    requested_region = "GHOST" if is_ghost else region
    response_region = normalize_region(actual_region) if actual_region else requested_region
    return {
        "success": True,
        "guest_created": True,
        "uid": uid,
        "password": password,
        "name": name,
        "requested_region": requested_region,
        "region": response_region,
        "access_token": access_token,
        "account_id": account_id,
        "jwt_token": jwt_token,
        "major_register_status": major_register_response.status_code,
        "major_login_success": bool(account_id),
        "major_login": major_login,
    }

def PoI(b, mt):
    m = mt()
    m.ParseFromString(b)
    return m

async def QwE(jt, pt):
    json_format.ParseDict(json.loads(jt), pt)
    return pt.SerializeToString()

def AsD(reg):
    reg = reg.upper()
    if reg == "IND":
        return "uid=5486728629&password=XXX756144823_XXX"
    elif reg in {"BR", "US", "SAC", "NA"}:
        return "uid=5068803739&password=B1D6B8A26D0CE09FB67D1FDBE77B8CE9C033F456A83F45B1BC3891A9B0AF3F33"
    else:
        return "uid=5481375839&password=0202277F5E6E750512E9F776702F46DC7CEDA3449EBF9395F47D427E6055DEA9"

async def ZxV(acc):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    data = acc + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as cl:
        res = await cl.post(url, data=data, headers={'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)", 'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Content-Type': "application/x-www-form-urlencoded"})
        res.raise_for_status()
        d = res.json()
        return d.get("access_token", "0"), d.get("open_id", "0")

async def guest_to_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 10;en;EN;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    data = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": CLIENT_SECRET,
        "client_id": CLIENT_ID,
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as cl:
            res = await cl.post(url, headers=headers, data=data)
        if res.status_code != 200:
            return {"success": False, "uid": uid, "error": f"Status: {res.status_code}"}
        result = res.json()
        return {
            "success": True,
            "uid": uid,
            "access_token": result.get("access_token"),
            "open_id": result.get("open_id"),
            "refresh_token": result.get("refresh_token"),
            "expires_in": result.get("expires_in"),
        }
    except Exception as e:
        return {"success": False, "uid": uid, "error": str(e)}

async def Bmw(reg):
    acc = AsD(reg)
    token, oid = await ZxV(acc)
    body = json.dumps({"open_id": oid, "open_id_type": "4", "login_token": token, "orign_platform_type": "4"})
    pb = await QwE(body, FreeFire_pb2.LoginReq())
    enc = BmwNoiNoiBmvYasYas(G, F, pb)
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as cl:
        res = await cl.post(url, data=enc, headers={'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)", 'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Content-Type': "application/octet-stream", 'Expect': "100-continue", 'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"})
        res.raise_for_status()
        msg = json.loads(json_format.MessageToJson(PoI(res.content, FreeFire_pb2.LoginRes)))
        TOKENS[reg] = {
            'token': f"Bearer {msg.get('token','0')}",
            'region': msg.get('lockRegion','0'),
            'server': msg.get('serverUrl','0'),
            'expires': time.time() + 25200
        }

async def GaY():
    tasks = [Bmw(reg) for reg in REGNS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failed = []
    for reg, result in zip(REGNS, results):
        if isinstance(result, Exception):
            failed.append(f"{reg}: {type(result).__name__}")
    if failed:
        print("Token refresh failed for " + ", ".join(failed))

def Gsu():
    while True:
        try:
            asyncio.run(GaY())
        except Exception as e:
            print(f"Token refresh loop failed: {e}")
        time.sleep(25200)

async def RtY(reg):
    info = TOKENS.get(reg)
    if info and time.time() < info['expires']:
        return info['token'], info['region'], info['server']
    await Bmw(reg)
    info = TOKENS[reg]
    return info['token'], info['region'], info['server']

async def LoL(uid, unk, reg, ep):
    payload = await QwE(json.dumps({'a': uid, 'b': unk}), main_pb2.GetPlayerPersonalShow())
    data_enc = BmwNoiNoiBmvYasYas(G, F, payload)
    token, lock, server = await RtY(reg)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as cl:
        res = await cl.post(server+ep, data=data_enc, headers={'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)", 'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Content-Type': "application/octet-stream", 'Expect': "100-continue", 'Authorization': token, 'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"})
        res.raise_for_status()
        return json.loads(json_format.MessageToJson(PoI(res.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))

def like_headers(token):
    return {
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": token,
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "X-Unity-Version": "2022.3.47f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54",
    }

def create_like_payload(uid, region):
    msg = like_pb2.like()
    msg.uid = int(uid)
    msg.region = region
    return BmwNoiNoiBmvYasYas(G, F, msg.SerializeToString())

def create_like_count_payload(uid):
    return BmwNoiNoiBmvYasYas(G, F, build_proto({1: int(uid), 2: 1}))

async def fetch_like_info(uid, region, token=None):
    region_token, lock, server = await RtY(region)
    token = token or region_token
    payload = create_like_count_payload(uid)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as cl:
        res = await cl.post(server + "/GetPlayerPersonalShow", data=payload, headers=like_headers(token))
        res.raise_for_status()
    info = PoI(res.content, like_count_pb2.Info)
    return json.loads(json_format.MessageToJson(info))

async def fetch_like_info_with_tokens(uid, region, tokens=None):
    candidates = []
    seen = set()
    for token in tokens or []:
        if token and token not in seen:
            seen.add(token)
            candidates.append(token)
    candidates.append(None)

    last_error = None
    for token in candidates:
        try:
            return await fetch_like_info(uid, region, token)
        except Exception as exc:
            last_error = exc
            continue
    raise last_error or RuntimeError("Could not fetch like info")

async def send_like_request(payload, token, url):
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as cl:
            res = await cl.post(url, data=payload, headers=like_headers(token))
        return res.status_code
    except Exception as e:
        return str(e)

async def send_like_requests(uid, region, count=None, tokens=None):
    region_token, lock, server = await RtY(region)
    tokens = tokens or [region_token]
    count = count or len(tokens)
    payload = create_like_payload(uid, region)
    url = server + "/LikeProfile"
    tasks = [send_like_request(payload, tokens[i % len(tokens)], url) for i in range(count)]
    return await asyncio.gather(*tasks, return_exceptions=True)

def get_like_account_info(data):
    return data.get("AccountInfo") or data.get("accountInfo") or {}

def HeHe(d):
    decode_profile_names(d)
    basic_info = d.get("basicInfo") or d.get("basic_info")
    if isinstance(basic_info, dict):
        br_rank_name = get_br_rank_name(basic_info.get("rankingPoints") or basic_info.get("ranking_points"))
        cs_rank_name = get_cs_rank_name(basic_info.get("csRank") or basic_info.get("cs_rank"))
        if br_rank_name:
            basic_info["brRankName"] = br_rank_name
        if cs_rank_name:
            basic_info["csRankName"] = cs_rank_name
    captain_info = d.get("captainBasicInfo") or d.get("captain_basic_info")
    if isinstance(captain_info, dict):
        br_rank_name = get_br_rank_name(captain_info.get("rankingPoints") or captain_info.get("ranking_points"))
        cs_rank_name = get_cs_rank_name(captain_info.get("csRank") or captain_info.get("cs_rank"))
        if br_rank_name:
            captain_info["brRankName"] = br_rank_name
        if cs_rank_name:
            captain_info["csRankName"] = cs_rank_name
    return d

@FAHHHH.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "ok",
        "message": "Info API is running.",
        "endpoints": {
            "jwt": "/jwt?uid=xxx&pw=xxx",
            "access_token": "/access-token?uid=xxx&password=xxx",
            "like": "/like?uid=xxx",
            "likeff": "/likeff?uid=xxx",
            "meanffinfo": "/meanffinfo?uid=xxx",
            "region_check": "/check-region?uid=xxx",
            "checkbanned": "/checkbanned?id=xxx",
            "bio": "/bio?token=xxx&bio=hello",
            "createaccount": "/createaccount?region=ME&name=MEAN",
            "atvguest": "/atvguest?uid=xxx&pw=xxx or /atvguest?token=xxx",
            "refresh": "/refresh"
        }
    }), 200

@FAHHHH.errorhandler(404)
def not_found(_):
    return jsonify({
        "status": "error",
        "message": "Route not found.",
        "available_endpoints": [
            "/",
            "/jwt",
            "/access-token",
            "/like",
            "/likeff",
            "/meanffinfo",
            "/check-region",
            "/checkbanned",
            "/bio",
            "/createaccount",
            "/atvguest",
            "/refresh"
        ]
    }), 404

@FAHHHH.route('/jwt', methods=['GET'])
def jwt_login():
    uid = request.args.get('uid')
    pw = request.args.get('pw')

    if not uid or not pw:
        return jsonify({
            "status": "error",
            "message": "Missing parameters. Use /jwt?uid=xxx&pw=xxx"
        }), 400

    try:
        uid_int = int(uid)
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "uid must be a number"
        }), 400

    oauth_url = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
    payload = {
        "client_id": 100067,
        "client_secret": CLIENT_SECRET,
        "client_type": 2,
        "password": pw,
        "response_type": "token",
        "uid": uid_int
    }

    response_payload = {
        "creator": "MEAN²",
        "status": "success",
        "Guest_Auth": None,
        "MajorLogin": None
    }

    try:
        r = http_session.post(oauth_url, json=payload, timeout=8)
        auth_data = response_json_or_text(r)
        response_payload["Guest_Auth"] = convert_timestamps_to_human(auth_data)

        inner = auth_data.get("data", {})
        acc_token = inner.get("access_token")
        open_id = inner.get("open_id")

        if not acc_token or not open_id:
            return jsonify({
                "status": "error",
                "message": "Auth tokens not found in Step 1",
                "Guest_Auth": response_payload["Guest_Auth"]
            }), 401

        req_msg = build_major_login_request(open_id, acc_token)
        enc_data = BmwNoiNoiBmvYasYas(G, F, req_msg.SerializeToString())
        headers = {
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "User-Agent": USERAGENT,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1"
        }

        resp = http_session.post(
            "https://loginbp.ggpolarbear.com/MajorLogin",
            data=enc_data,
            headers=headers,
            verify=False,
            timeout=8
        )

        if resp.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"MajorLogin failed with status {resp.status_code}",
                "Guest_Auth": response_payload["Guest_Auth"]
            }), 502

        res_msg = MajorLoginRes_pb2.MajorLoginRes()
        res_msg.ParseFromString(resp.content)
        major_dict = MessageToDict(res_msg, preserving_proto_field_name=True)

        if 'ttl' in major_dict:
            major_dict['ttl'] = format_ttl(int(major_dict['ttl']))

        nickname = "Unknown"
        if 'token' in major_dict:
            major_dict['jwt_token'] = major_dict.pop('token')
            nickname = extract_nickname_from_jwt(major_dict['jwt_token'])

        ordered_major_dict = {}
        if 'account_id' in major_dict:
            ordered_major_dict['account_id'] = major_dict['account_id']
        ordered_major_dict['nickname'] = nickname

        for k, v in major_dict.items():
            if k != 'account_id':
                ordered_major_dict[k] = v

        response_payload["MajorLogin"] = convert_timestamps_to_human(ordered_major_dict)
        return jsonify(response_payload), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@FAHHHH.route('/atvguest', methods=['GET'])
def activate_guest_api():
    payload = request.get_json(silent=True) or {}
    uid = payload.get('uid') or request.args.get('uid')
    pw = payload.get('pw') or payload.get('password') or request.args.get('pw') or request.args.get('password')
    raw_token = (
        payload.get('token')
        or payload.get('access_token')
        or request.args.get('token')
        or request.args.get('access_token')
    )

    if not ((uid and pw) or raw_token):
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Missing parameters. Use /atvguest?uid=xxx&pw=xxx or /atvguest?token=xxx"
        }), 400

    try:
        access_token = extract_bio_access_token(raw_token) if raw_token else None
        if access_token:
            open_id, inspect_data = get_bio_openid_from_inspect(access_token)
            if not open_id:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "activated": False,
                    "message": "Invalid access token or could not fetch open_id",
                    "details": inspect_data,
                }), 401
            jwt_token, platform_type = bio_major_login(access_token, open_id)
            if not jwt_token:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "activated": False,
                    "message": "MajorLogin failed for access token"
                }), 502
            account_info = decode_bio_jwt(jwt_token) or {}
            uid = account_info.get("uid") or uid
            result = {
                "uid": str(uid) if uid else None,
                "account_id": account_info.get("account_id"),
                "name": account_info.get("name") or account_info.get("nickname"),
                "region": account_info.get("region"),
                "token": jwt_token,
                "platform_type": platform_type,
            }
        else:
            result = fetch_guest_jwt_for_like_with_retry(uid, pw, max_retries=3, retry_delay=0.7)

        region = normalize_region(result.get("region"))
        if region and result.get("uid"):
            set_cached_region(result.get("uid"), region)
        return jsonify({
            "success": True,
            "status": "success",
            "activated": True,
            "uid": result.get("uid"),
            "account_id": result.get("account_id"),
            "name": result.get("name"),
            "region": region or result.get("region"),
            "access_token": access_token,
            "jwt_token": result.get("token"),
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "activated": False,
            "uid": uid,
            "message": str(e)
        }), 502

@FAHHHH.route('/access-token', methods=['GET', 'POST'])
def access_token_api():
    payload = request.get_json(silent=True) or {}
    uid = payload.get('uid') or request.args.get('uid')
    password = payload.get('password') or request.args.get('password')
    if not uid or not password:
        return jsonify({"success": False, "error": "Please provide uid and password."}), 400

    result = asyncio.run(guest_to_access_token(uid, password))
    status = 200 if result.get("success") else 502
    return jsonify(result), status

def run_like_api(token_file, endpoint_name):
    uid = request.args.get("uid")
    requested_region = request.args.get("server_name") or request.args.get("region")

    if not uid:
        return jsonify({"success": False, "error": f"UID is required. Use /{endpoint_name}?uid=xxx"}), 400
    try:
        int(uid)
    except ValueError:
        return jsonify({"success": False, "error": "uid must be a number"}), 400

    detected_region = get_cached_region(uid)
    if not detected_region:
        player_data, detected_region = fetch_player_personal_show(uid)
        if player_data:
            basic_info = player_data.get("basicInfo") or player_data.get("basic_info") or {}
            detected_region = basic_info.get("region") or detected_region
        if detected_region:
            set_cached_region(uid, detected_region)
    if requested_region:
        region = requested_region.upper()
    else:
        region = detected_region

    if region not in REGNS:
        return jsonify({"success": False, "error": f"Unsupported region: {region}"}), 400

    try:
        like_tokens = load_like_tokens(token_file=token_file)
        before = asyncio.run(fetch_like_info_with_tokens(uid, region, like_tokens))
        before_info = get_like_account_info(before)
        before_likes = int(before_info.get("Likes", 0) or 0)

        results = asyncio.run(send_like_requests(uid, region, tokens=like_tokens))

        after = asyncio.run(fetch_like_info_with_tokens(uid, region, like_tokens))
        after_info = get_like_account_info(after)
        after_likes = int(after_info.get("Likes", 0) or 0)
        likes_given = after_likes - before_likes

        return jsonify({
            "success": True,
            "LikesGivenByAPI": likes_given,
            "LikesafterCommand": after_likes,
            "LikesbeforeCommand": before_likes,
            "PlayerNickname": after_info.get("PlayerNickname", ""),
            "Region": detected_region or region,
            "UID": int(after_info.get("UID", uid) or uid),
            "status": 1 if likes_given > 0 else 2,
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@FAHHHH.route('/like', methods=['GET'])
def like_api():
    return run_like_api(LIKE_TOKEN_FILE, "like")

@FAHHHH.route('/likeff', methods=['GET'])
def likeff_api():
    return run_like_api(LIKEFF_TOKEN_FILE, "likeff")

@FAHHHH.route('/meanffinfo')
def OMG():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Please provide UID."}), 400
    
    if uid in UID_MEMORY:
        try:
            data = asyncio.run(LoL(uid, "7", UID_MEMORY[uid], "/GetPlayerPersonalShow"))
            data = HeHe(data)
            return json.dumps(data, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except:
            pass
    
    for reg in REGNS:
        try:
            data = asyncio.run(LoL(uid, "7", reg, "/GetPlayerPersonalShow"))
            UID_MEMORY[uid] = reg
            data = HeHe(data)
            return json.dumps(data, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except:
            continue
    
    return jsonify({"error": "UID not found in any region."}), 404

def fetch_player_personal_show(uid):
    if uid in UID_MEMORY:
        try:
            data = asyncio.run(LoL(uid, "7", UID_MEMORY[uid], "/GetPlayerPersonalShow"))
            return HeHe(data), UID_MEMORY[uid]
        except Exception:
            pass

    for reg in REGNS:
        try:
            data = asyncio.run(LoL(uid, "7", reg, "/GetPlayerPersonalShow"))
            UID_MEMORY[uid] = reg
            return HeHe(data), reg
        except Exception:
            continue

    return None, None

@FAHHHH.route('/check-region', methods=['GET'])
def region_check():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Please provide UID. Use /check-region?uid=xxx"}), 400

    data, detected_region = fetch_player_personal_show(uid)
    if not data:
        return jsonify({"error": "UID not found in any region."}), 404

    basic_info = data.get("basicInfo") or data.get("basic_info") or {}
    return jsonify({
        "Name": basic_info.get("nickname"),
        "UID": basic_info.get("accountId") or basic_info.get("account_id") or uid,
        "Level": basic_info.get("level"),
        "Region": basic_info.get("region") or detected_region
    }), 200

@FAHHHH.route('/checkbanned', methods=['GET'])
def check_banned():
    try:
        player_id = request.args.get('id')
        if not player_id:
            return jsonify({"error": "Player ID is required"}), 400
        try:
            int(player_id)
        except ValueError:
            return jsonify({"error": "Player ID must be a number"}), 400

        garena_url = f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={player_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "authority": "ff.garena.com",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "referer": "https://ff.garena.com/en/support/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "B6FksShzIgjfrYImLpTsadjS86sddhFH",
            "Cookie": "_ga_8RFDT0P8N9=GS1.1.1706295767.2.0.1706295767.0.0.0; apple_state_key=8236785ac31b11ee960a621594e13693; datadome=bbC6XTzUAS0pXgvEs7u",
        }

        ban_data = {}
        garena_error = None
        try:
            garena_response = http_session.get(garena_url, headers=headers, timeout=10)
            garena_response.raise_for_status()
            ban_data = garena_response.json()
        except Exception as exc:
            garena_error = str(exc)

        region_data = {}
        region_error = None
        try:
            region_api_url = f"https://nr-codex-apis.onrender.com/REGION-API/check?uid={player_id}"
            region_response = http_session.get(region_api_url, timeout=15)
            region_response.raise_for_status()
            region_data = region_response.json()
        except Exception as exc:
            region_error = str(exc)

        if not ban_data and not region_data:
            return jsonify({
                "error": "Failed to fetch ban and region data",
                "garena_error": garena_error,
                "region_error": region_error,
            }), 502

        is_banned = ban_data.get('data', {}).get('is_banned', 0)
        period = ban_data.get('data', {}).get('period', 0)
        nickname = region_data.get('formatted_response', {}).get('nickname')
        region = region_data.get('formatted_response', {}).get('region')
        level = region_data.get('raw_api_response', {}).get('basicInfo', {}).get('level')

        response = {
            "player_id": player_id,
            "is_banned": bool(is_banned),
            "ban_period": period if is_banned else 0,
            "status": "BANNED" if is_banned else "NOT BANNED",
            "nickname": nickname,
            "region": region,
            "level": level,
            "garena_error": garena_error,
            "region_error": region_error,
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@FAHHHH.route('/bio', methods=['GET', 'POST'])
def update_bio_api():
    start_time = time.time()
    payload = request.get_json(silent=True) or {}
    form = request.form or {}

    def read_param(*names):
        for name in names:
            value = payload.get(name)
            if value is None:
                value = request.args.get(name)
            if value is None:
                value = form.get(name)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    bio = read_param("bio")
    raw_token = (
        read_param("access_token")
        or read_param("token")
        or read_param("access")
        or read_param("jwt")
    )
    uid = read_param("uid")
    password = read_param("password", "pass")

    if not bio:
        return jsonify({"status": "error", "message": "Bio is required"}), 400
    if len(bio) > 250:
        return jsonify({"status": "error", "message": "Bio must be 250 characters or less"}), 400
    jwt_token = str(raw_token or "").strip() if looks_like_jwt(raw_token) else None
    access_token = None if jwt_token else extract_bio_access_token(raw_token)
    if not access_token and not jwt_token and not (uid and password):
        return jsonify({
            "status": "error",
            "message": "Provide either uid/password, access_token, token, Garena ?access_token= link, or jwt."
        }), 400

    try:
        if jwt_token:
            used_method = "jwt"
            final_jwt = jwt_token
            account_info = decode_bio_jwt(jwt_token)
            if not account_info or not account_info.get("uid"):
                return jsonify({"status": "error", "message": "Invalid JWT token (cannot decode)"}), 400
        elif uid and password:
            used_method = "uid_password"
            access_token, open_id, auth_data = bio_guest_login(uid, password)
            if not access_token or not open_id:
                return jsonify({
                    "status": "error",
                    "message": "Guest login failed (invalid UID/password)",
                    "details": auth_data,
                }), 401
            final_jwt, platform_type = bio_major_login(access_token, open_id)
            if not final_jwt:
                return jsonify({"status": "error", "message": "MajorLogin failed for guest"}), 502
            account_info = decode_bio_jwt(final_jwt) or {"uid": uid}
        else:
            used_method = "access_token"
            open_id, inspect_data = get_bio_openid_from_inspect(access_token)
            if not open_id:
                return jsonify({
                    "status": "error",
                    "message": "Invalid access token or could not fetch open_id",
                    "details": inspect_data,
                }), 400
            final_jwt, platform_type = bio_major_login(access_token, open_id)
            if not final_jwt:
                return jsonify({"status": "error", "message": "MajorLogin failed for access token"}), 502
            account_info = decode_bio_jwt(final_jwt) or {}

        update_response, used_url = update_social_bio(final_jwt, bio)
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Bio API request failed: {exc}"}), 502

    account_info = account_info or {}
    response_time = f"{time.time() - start_time:.2f}s"
    result = {
        "status": "success",
        "message": "Bio updated",
        "success": True,
        "response_time": response_time,
        "bio": bio,
        "account": account_info,
        "uid": account_info.get("account_id") or account_info.get("uid"),
        "external_uid": account_info.get("uid"),
        "account_id": account_info.get("account_id"),
        "name": account_info.get("name") or account_info.get("nickname"),
        "nickname": account_info.get("nickname") or account_info.get("name"),
        "region": account_info.get("region"),
        "used_method": used_method,
        "http_code": update_response.status_code,
        "update_url": used_url,
    }
    if used_method == "jwt":
        result["jwt"] = f"{final_jwt[:len(final_jwt)//2]}..."
    elif used_method == "access_token":
        result["access_token"] = access_token
    else:
        result["password"] = password
    return jsonify(result), 200

@FAHHHH.route('/createaccount', methods=['GET', 'POST'])
def create_account_api():
    payload = request.get_json(silent=True) or {}
    region = payload.get('region') or request.args.get('region')
    account_name = payload.get('name') or request.args.get('name')

    if not region or not account_name:
        return jsonify({
            "success": False,
            "error": "Missing parameters. Use /createaccount?region=ME&name=MEAN"
        }), 400

    try:
        is_ghost = region.upper() == "GHOST"
        password_prefix = f"{account_name}_{region}".upper()
        result = create_guest_account(region, account_name, password_prefix, is_ghost)
        return jsonify(result), 200 if result.get("guest_created") else 502
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        body = e.response.text[:500] if e.response is not None else str(e)
        return jsonify({
            "success": False,
            "error": f"HTTP error: {status_code}",
            "details": body
        }), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@FAHHHH.route('/refresh', methods=['GET','POST'])
def WTF():
    try:
        asyncio.run(GaY())
        return jsonify({'message':'Tokens refreshed for all regions.'}), 200
    except Exception as e:
        return jsonify({'error': f'Refresh failed: {e}'}), 500

if __name__ == "__main__":
    threading.Thread(target=update_like_tokens_from_uidpass, daemon=True).start()
    threading.Thread(target=update_likeff_tokens_from_uidpass, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    FAHHHH.run(host="0.0.0.0", port=port)
