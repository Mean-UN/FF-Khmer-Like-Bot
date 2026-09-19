#Owner : @vaibhavff570
#Join : @vaibhavapix, @vaibhavapisx
import asyncio
import time
import httpx
import json
import hashlib
import hmac
import guest_protocol
import jwt_protocol
from Crypto.Util.Padding import unpad
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
from request_usage import install_request_usage
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
install_request_usage(FAHHHH)
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
LIKEFF_SLOT_STATE_FILE = "likeff_slot_usage.json"
LIKEFF_SLOT_COUNT = 30
LIKEFF_UIDS_PER_SLOT = 30
REGION_CACHE_FILE = "regions.json"
LIKE_TOKEN_MAX_RETRIES = 10
LIKE_TOKEN_RETRY_DELAY = 0.7
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
    auth, open_id, access_token = jwt_protocol.generate_access_token(
        http_session, uid, password, CLIENT_SECRET)
    return access_token, open_id, auth


def get_bio_openid_from_inspect(access_token):
    info = jwt_protocol.inspect_token(http_session, access_token)
    return info["open_id"], info


def bio_major_login(access_token, open_id):
    result = jwt_protocol.major_login(http_session, open_id, access_token)
    return result.get("token"), 4


def update_social_bio(jwt_token, bio_text):
    account = decode_bio_jwt(jwt_token) or {}
    region = str(account.get("region") or "").upper()
    if region in {"IND", "IN"}:
        host = "client.ind.freefiremobile.com"
    elif region in {"US", "NA", "BR", "SAC"}:
        host = "client.us.freefiremobile.com"
    elif region in {"SG", "BP", "BD", "PK", "TH", "VN", "ID", "TW", "ME", "RU", "EU"}:
        host = "clientbp.ggblueshark.com"
    else:
        raise ValueError(f"Unsupported or missing JWT region: {region or 'missing'}")
    url = f"https://{host}/UpdateSocialBasicInfo"
    data = BioData()
    data.field_2 = 17
    data.field_5.CopyFrom(EmptyMessage())
    data.field_6.CopyFrom(EmptyMessage())
    data.field_8 = bio_text
    data.field_9 = 1
    data.field_11.CopyFrom(EmptyMessage())
    data.field_12.CopyFrom(EmptyMessage())
    # Empty length-delimited field 16, present in the supplied OB55 payload.
    plain = data.SerializeToString() + b"\x82\x01\x00"
    encrypted = BmwNoiNoiBmvYasYas(G, F, plain)
    headers = {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
        "X-GA": "v1 1", "ReleaseVersion": jwt_protocol.RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "X-GA-SV": str(int(time.time())),
        "Authorization": f"Bearer {jwt_token}",
    }
    response = http_session.post(url, headers=headers, data=encrypted, timeout=20)
    response.raise_for_status()
    return response, url


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
    return jwt_protocol.build_major_login_request(open_id, access_token)

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
    return f"https://{guest_protocol.region_host(region, is_ghost)}/MajorRegister"

def major_login_url(region, is_ghost=False):
    return "https://loginbp.ppmainecoonghj.com/MajorLogin"

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

def token_items_to_bearers(items, region=None):
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

def get_slot_items(data, slot):
    slot_key = str(slot)
    if isinstance(data, dict):
        slots = data.get("slots")
        if isinstance(slots, dict):
            return slots.get(slot_key) or slots.get(int(slot)) or []
        if isinstance(slots, list):
            for item in slots:
                if not isinstance(item, dict):
                    continue
                if str(item.get("slot") or item.get("id") or "") == slot_key:
                    return item.get("tokens") or item.get("items") or []
        direct = data.get(slot_key) or data.get(f"slot_{slot_key}")
        if isinstance(direct, list):
            return direct
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and str(item.get("slot") or item.get("id") or "") == slot_key:
                return item.get("tokens") or item.get("items") or []
    return []

def load_like_tokens(region=None, token_file=LIKE_TOKEN_FILE, slot=None):
    items = []
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    if slot is not None:
        slot_items = get_slot_items(items, slot)
        if slot_items:
            return token_items_to_bearers(slot_items, region)

        base, ext = os.path.splitext(token_file)
        for candidate in (f"{base}_{slot}{ext}", f"{base}_slot{slot}{ext}", f"{base}_slot_{slot}{ext}"):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    candidate_items = json.load(f)
                tokens = token_items_to_bearers(candidate_items, region)
                if tokens:
                    return tokens
            except Exception:
                continue

        # A shared flat token list is the legacy first slot only. Reusing it
        # for every missing slot would multiply the same accounts' quota.
        if int(slot) != 1:
            return []

    return token_items_to_bearers(items, region)

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

def current_likeff_slot_date():
    return datetime.now(CAMBODIA_TZ).date().isoformat()

def load_likeff_slot_usage():
    try:
        with open(LIKEFF_SLOT_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_likeff_slot_usage(data):
    with open(LIKEFF_SLOT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def current_likeff_slot_usage():
    today = current_likeff_slot_date()
    data = load_likeff_slot_usage()
    if data.get("date") != today:
        data = {"date": today, "assignments": {}}
    data.setdefault("assignments", {})
    changed = data.pop("exhausted_slots", None) is not None

    assignments = data.get("assignments", {})
    if isinstance(assignments, dict) and len(assignments) > 1:
        slot_counts = {}
        for assigned_slot in assignments.values():
            if str(assigned_slot).isdigit():
                assigned_slot = int(assigned_slot)
                slot_counts[assigned_slot] = slot_counts.get(assigned_slot, 0) + 1

        if slot_counts and max(slot_counts.values()) <= 1:
            data["assignments"] = {
                str(uid): (index // LIKEFF_UIDS_PER_SLOT) + 1
                for index, uid in enumerate(assignments.keys())
            }
            changed = True

    if changed:
        save_likeff_slot_usage(data)
    return data

def assign_likeff_slot(uid):
    uid = str(uid)
    data = current_likeff_slot_usage()
    assignments = data["assignments"]
    existing = assignments.get(uid)
    if existing:
        return int(existing), False

    slot_counts = {}
    for assigned_slot in assignments.values():
        if str(assigned_slot).isdigit():
            assigned_slot = int(assigned_slot)
            slot_counts[assigned_slot] = slot_counts.get(assigned_slot, 0) + 1
    for slot in range(1, LIKEFF_SLOT_COUNT + 1):
        if slot_counts.get(slot, 0) < LIKEFF_UIDS_PER_SLOT:
            assignments[uid] = slot
            save_likeff_slot_usage(data)
            return slot, True

    raise RuntimeError(f"All {LIKEFF_SLOT_COUNT} LikeFF slots are already full today")

def validate_like_jwt(session, token, account_id, region):
    """Check JWT metadata and authenticate a read of the sender's own profile."""
    raw_token = str(token or "")
    if len(raw_token.split(".")) != 3 or any(not part for part in raw_token.split(".")):
        raise ValueError("Malformed JWT returned by MajorLogin")
    try:
        header_part, _, signature_part = raw_token.split(".")
        header = json.loads(base64.urlsafe_b64decode(header_part + '=' * (-len(header_part) % 4)))
        signature = base64.b64decode(signature_part + '=' * (-len(signature_part) % 4), altchars=b'-_', validate=True)
    except (ValueError, UnicodeError):
        raise ValueError("Malformed JWT header or signature") from None
    if not isinstance(header, dict) or not header.get('alg') or header.get('alg') == 'none':
        raise ValueError("JWT signing algorithm missing or invalid")
    if header.get('alg') == 'HS256' and len(signature) != 32:
        raise ValueError("Malformed HS256 signature length")
    claims = decode_jwt_payload(raw_token)
    if not isinstance(claims, dict):
        raise ValueError("Malformed JWT claims")
    expires = claims.get("exp")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not (expires > time.time() + 60):
        raise ValueError("JWT expiry missing, expired or too close to expiry")
    account_id = str(account_id or "")
    if not account_id.isdigit() or int(account_id) <= 0:
        raise ValueError("JWT account ID missing")
    if claims.get("account_id") is not None and str(claims["account_id"]) != account_id:
        raise ValueError("JWT account ID does not match login response")
    region = normalize_region(region)
    if region not in REGNS:
        raise ValueError("JWT region missing or unsupported")
    if claims.get("lock_region") and not is_region_match(region, claims["lock_region"]):
        raise ValueError("JWT region does not match login response")
    response = session.post(
        like_server_url(region) + "/GetPlayerPersonalShow",
        data=create_like_count_payload(account_id), headers=like_headers(raw_token), timeout=15)
    response.raise_for_status()
    profile = like_count_pb2.Info()
    try:
        profile.ParseFromString(response.content)
    except message.DecodeError:
        raise ValueError("JWT profile validation returned invalid protobuf") from None
    info = get_like_account_info(json_format.MessageToDict(profile))
    if str(info.get("UID")) != account_id:
        raise ValueError("JWT profile validation did not return the expected account")
    return {"profile_http_status": response.status_code,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "like_profile_verified": False}


def fetch_guest_jwt_for_like(uid, password, session=None):
    session = session if session is not None else http_session
    _, open_id, access_token = jwt_protocol.generate_access_token(session, uid, password, CLIENT_SECRET)
    major_login = jwt_protocol.major_login(session, open_id, access_token)
    jwt_token = major_login.get("token")
    if not jwt_token:
        raise ValueError("MajorLogin did not return jwt token")
    jwt_payload = decode_jwt_payload(jwt_token)
    account_id = major_login.get("account_id") or jwt_payload.get("account_id")
    region = major_login.get("lock_region") or major_login.get("noti_region") or jwt_payload.get("lock_region")
    validation = validate_like_jwt(session, jwt_token, account_id, region)
    return {
        "uid": str(uid),
        "account_id": account_id,
        "name": extract_nickname_from_jwt(jwt_token),
        "region": region,
        "token": jwt_token,
        "validation": validation,
    }

def fetch_guest_jwt_for_like_with_retry(uid, password, max_retries=LIKE_TOKEN_MAX_RETRIES, retry_delay=LIKE_TOKEN_RETRY_DELAY, session=None):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_guest_jwt_for_like(uid, password, session=session) if session is not None else fetch_guest_jwt_for_like(uid, password)
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
    # Preserve the existing naming/password generators, including GHOST mode.
    password = generate_custom_password(password_prefix)
    region = normalize_region(region)
    requested_region = "GHOST" if is_ghost else region
    result = {
        "success": False, "guest_created": False, "uid": None,
        "password": password, "name": None, "requested_region": requested_region,
        "region": requested_region, "access_token": None, "account_id": None,
        "jwt_token": None, "major_login_success": False,
    }
    stage = "Guest register"

    def headers(url, content_type, game=False):
        values = {
            "Accept-Encoding": "gzip", "Connection": "Keep-Alive",
            "Content-Type": content_type, "Host": urlparse(url).netloc,
            "User-Agent": guest_protocol.random_ua(),
        }
        if game:
            values.update({"ReleaseVersion": "OB55", "X-GA": "v1 1",
                           "X-Unity-Version": "2022.3.47f1", "Expect": "100-continue"})
        else:
            values["Accept"] = "application/json"
        if url.endswith("/MajorLogin"):
            values["Host"] = "loginbp.ggpolarbear.com"
        return with_region_ip_headers(values, region)

    with requests.Session() as session:
        if proxy_url:
            session.proxies.update({"http": proxy_url, "https": proxy_url})

        def post(url, request_headers, retry=False, **kwargs):
            # Registration may create an account even when its response is lost.
            # Only token/login requests are retried automatically here.
            for attempt in range(3 if retry else 1):
                try:
                    response = session.post(url, headers=request_headers, timeout=30,
                                            verify=False, **kwargs)
                    response.raise_for_status()
                    return response
                except requests.RequestException as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    if not retry or attempt == 2 or (status is not None and status != 429 and status < 500):
                        raise
                    time.sleep(2 ** attempt)

        try:
            register_url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
            register_payload = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
            register_body = json.dumps(register_payload, separators=(',', ':')).encode("utf-8")
            signature = hmac.new(CLIENT_SECRET.encode("utf-8"), register_body, hashlib.sha256).hexdigest()
            register_headers = headers(register_url, "application/json; charset=utf-8")
            register_headers["Authorization"] = f"Signature {signature}"
            response = post(register_url, register_headers, data=register_body)
            registration = response_json_or_text(response)
            data = registration.get("data") if isinstance(registration, dict) else None
            uid = data.get("uid") if isinstance(data, dict) else None
            if not uid or registration.get("code", 0) != 0:
                raise ValueError("Guest register did not return a successful UID")
            result.update(success=True, guest_created=True, uid=uid)

            stage = "Token grant"
            form_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
            json_url = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
            form = {"uid": uid, "password": password, "response_type": "token",
                    "client_type": "2", "client_secret": CLIENT_SECRET, "client_id": CLIENT_ID}
            attempts = [
                (form_url, "application/x-www-form-urlencoded", {"data": form}),
                (json_url, "application/json; charset=utf-8", {"json": {
                    **form, "uid": int(uid), "client_type": 2, "client_id": 100067}}),
            ]
            access_token = open_id = None
            last_error = None
            for url, content_type, payload in attempts:
                try:
                    response = post(url, headers(url, content_type), retry=True, **payload)
                    data = response_json_or_text(response)
                    if isinstance(data, dict) and isinstance(data.get("data"), dict):
                        data = data["data"]
                    if not isinstance(data, dict) or not data.get("access_token") or not data.get("open_id"):
                        raise ValueError("Token grant did not return access_token/open_id")
                    access_token, open_id = data["access_token"], data["open_id"]
                    break
                except (requests.RequestException, ValueError) as exc:
                    last_error = exc
            if not access_token or not open_id:
                raise last_error or ValueError("Token grant failed")
            result["access_token"] = access_token

            stage = "MajorRegister"
            name = generate_random_name(account_name)
            result["name"] = name
            keystream = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30])
            field = bytes(ord(char) ^ keystream[index % len(keystream)] for index, char in enumerate(open_id))
            lang_code = "pt" if is_ghost else guest_protocol.REGION_LANG.get(region, "en")
            payload = build_proto({1: name, 2: access_token, 3: open_id, 5: 102000007,
                                   6: 4, 7: 1, 13: 1, 14: field, 15: lang_code,
                                   16: 2, 20: "1.132.1", 21: 1})
            url = major_register_url(region, is_ghost)
            register_headers = headers(url, "application/x-www-form-urlencoded", game=True)
            register_headers["Authorization"] = "Bearer"
            response = post(url, register_headers, data=BmwNoiNoiBmvYasYas(G, F, payload))
            result["major_register_status"] = response.status_code

            stage = "MajorLogin"
            login_payload = build_proto(guest_protocol.login_fields(region, open_id, access_token, is_ghost))
            url = major_login_url(region, is_ghost)
            response = post(url, headers(url, "application/x-www-form-urlencoded", game=True), retry=True,
                            data=BmwNoiNoiBmvYasYas(G, F, login_payload))
            candidates = []
            try:
                candidates.append(unpad(AES.new(G, AES.MODE_CBC, F).decrypt(response.content), AES.block_size))
            except ValueError:
                pass
            candidates.append(response.content)
            login = {}
            for content in candidates:
                try:
                    res_msg = MajorLoginRes_pb2.MajorLoginRes()
                    res_msg.ParseFromString(content)
                    candidate = MessageToDict(res_msg, preserving_proto_field_name=True)
                    if candidate.get("token"):
                        login = candidate
                        break
                except message.DecodeError:
                    continue
            jwt_token = login.get("token")
            if not jwt_token:
                raise ValueError("MajorLogin did not return a JWT")
            jwt_data = decode_jwt_payload(jwt_token)
            account_id = login.get("account_id") or jwt_data.get("account_id") or jwt_data.get("external_id")
            if not account_id:
                raise ValueError("MajorLogin did not return an account ID")
            actual_region = login.get("lock_region") or login.get("noti_region")
            result.update(account_id=account_id, jwt_token=jwt_token, major_login=login,
                          major_login_success=True,
                          region=normalize_region(actual_region) if actual_region else requested_region)
            return result
        except Exception as exc:
            # Keep created credentials if a later stage fails; callers can recover them.
            response = getattr(exc, "response", None)
            reason = f"HTTP {response.status_code}" if response is not None else type(exc).__name__
            if response is not None:
                result["http_status"] = response.status_code
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        # Expose only diagnostic fields, never raw credential-bearing responses.
                        for field_name in ("code", "error", "message", "msg"):
                            value = error_data.get(field_name)
                            if isinstance(value, (str, int)):
                                safe_value = str(value)[:300]
                                for secret in (password, result.get("access_token"), result.get("jwt_token")):
                                    if secret:
                                        safe_value = safe_value.replace(str(secret), "[redacted]")
                                result.setdefault("upstream_error", {})[field_name] = safe_value
                except (ValueError, TypeError):
                    pass
            message = f"{stage} failed ({reason})"
            if result["guest_created"]:
                result["warning"] = "Guest created, but " + message
            else:
                result["error"] = message
            result["failed_stage"] = stage
            return result

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
    credentials = parse_qs(AsD(reg))

    def login():
        with requests.Session() as session:
            _, open_id, access_token = jwt_protocol.generate_access_token(
                session, credentials["uid"][0], credentials["password"][0], CLIENT_SECRET)
            return jwt_protocol.major_login(session, open_id, access_token)

    msg = await asyncio.to_thread(login)
    if not msg.get("token") or not msg.get("server_url"):
        raise ValueError("Regional login did not return token/server_url")
    TOKENS[reg] = {
        "token": normalize_bearer_token(msg["token"]),
        "region": msg.get("lock_region") or reg,
        "server": msg["server_url"].rstrip("/"),
        "expires": time.time() + min(int(msg.get("ttl") or 25200), 25200),
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
        res = await cl.post(server+ep, data=data_enc, headers={'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)", 'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Content-Type': "application/octet-stream", 'Expect': "100-continue", 'Authorization': token, 'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': jwt_protocol.RELEASE_VERSION})
        res.raise_for_status()
        return json.loads(json_format.MessageToJson(PoI(res.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))

def like_headers(token):
    return {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "X-GA-SV": str(int(time.time())),
        "Authorization": normalize_bearer_token(token),
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.12f1",
        "X-GA": "v1 1",
        "ReleaseVersion": jwt_protocol.RELEASE_VERSION,
    }


def like_server_url(region):
    region = region.upper()
    if region == "IND":
        return "https://client.ind.freefiremobile.com"
    if region in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com"
    return "https://clientbp.ppmainecoonghj.com"


def create_like_payload(uid, region):
    msg = like_pb2.like()
    msg.uid = int(uid)
    msg.region = region
    return BmwNoiNoiBmvYasYas(G, F, msg.SerializeToString())

def create_like_count_payload(uid):
    return BmwNoiNoiBmvYasYas(G, F, build_proto({1: int(uid), 2: 1}))

async def fetch_like_info(uid, region, token=None):
    server = like_server_url(region)
    if not token:
        token, _, _ = await RtY(region)
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

async def send_like_request(payload, token, url, client=None):
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as cl:
                res = await cl.post(url, data=payload, headers=like_headers(token))
        else:
            res = await client.post(url, data=payload, headers=like_headers(token))
        return res.status_code
    except Exception as exc:
        return type(exc).__name__


async def send_like_requests(uid, region, count=None, tokens=None):
    server = like_server_url(region)
    if not tokens:
        region_token, _, _ = await RtY(region)
        tokens = [region_token]
    count = count or len(tokens)
    payload = create_like_payload(uid, region)
    url = server + "/LikeProfile"
    semaphore = asyncio.Semaphore(25)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False,
                                 limits=httpx.Limits(max_connections=25, max_keepalive_connections=25)) as client:
        async def send(token):
            async with semaphore:
                return await send_like_request(payload, token, url, client=client)
        tasks = [send(tokens[i % len(tokens)]) for i in range(count)]
        return await asyncio.gather(*tasks, return_exceptions=True)


def summarize_like_results(results, tokens=None):
    statuses = defaultdict(int)
    errors = defaultdict(int)
    for result in results:
        if isinstance(result, int):
            statuses[str(result)] += 1
        else:
            # Only expose exception categories, never request URLs or credentials.
            category = type(result).__name__ if isinstance(result, BaseException) else str(result)
            errors[category if category.isidentifier() else "RequestError"] += 1
    summary = {
        "attempted": len(results),
        "http_200": statuses.get("200", 0),
        "http_non_200": sum(count for status, count in statuses.items() if status != "200"),
        "network_errors": sum(errors.values()),
        "http_status_counts": dict(statuses),
        "error_counts": dict(errors),
    }

    if tokens is not None:
        failed_tokens = []
        for index, (token, result) in enumerate(zip(tokens, results), start=1):
            if result == 200:
                continue
            normalized = normalize_bearer_token(token) or ""
            raw_token = normalized.split(" ", 1)[-1]
            failed_tokens.append({
                "token_index": index,
                "token_fingerprint": hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:16],
                "http_status": result if isinstance(result, int) else None,
            })
        summary["failed_tokens"] = failed_tokens
    return summary


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
            "usage": "/usage",
            "jwt": "/jwt?uid=xxx&pw=xxx",
            "access_token": "/access-token?uid=xxx&password=xxx",
            "like": "/like?uid=xxx",
            "likeff": "/likeff?uid=xxx",
            "meanffinfo": "/meanffinfo?uid=xxx",
            "region_check": "/check-region?uid=xxx",
            "checkbanned": "/checkbanned?id=xxx",
            "bio": "/bio?token=xxx&bio=hello",
            "createaccount": "/createaccount?region=ME&name=MEAN",
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
            "/usage",
            "/jwt",
            "/access-token",
            "/like",
            "/likeff",
            "/meanffinfo",
            "/check-region",
            "/checkbanned",
            "/bio",
            "/createaccount",
            "/refresh"
        ]
    }), 404

@FAHHHH.route('/jwt', methods=['GET', 'POST'])
def jwt_login():
    body = request.get_json(silent=True)
    params = body if isinstance(body, dict) else request.form
    uid = params.get('uid') or request.args.get('uid')
    pw = params.get('pw') or params.get('password') or request.args.get('pw') or request.args.get('password')
    access_token = params.get('access_token') or request.args.get('access_token')
    if not access_token and (not uid or not pw):
        return jsonify({"status": "error", "message": "Provide uid and pw, or access_token"}), 400
    if not access_token and not str(uid).isdigit():
        return jsonify({"status": "error", "message": "uid must be a number"}), 400
    response_payload = {"creator": "MEAN²", "status": "success", "Guest_Auth": None, "MajorLogin": None}
    try:
        if access_token:
            auth_data = jwt_protocol.inspect_token(http_session, access_token)
            open_id = str(auth_data['open_id'])
        else:
            auth_data, open_id, access_token = jwt_protocol.generate_access_token(http_session, uid, pw, CLIENT_SECRET)
        response_payload['Guest_Auth'] = convert_timestamps_to_human(auth_data)
    except (requests.RequestException, ValueError):
        return jsonify({"status": "error", "message": "Guest authentication or token inspection failed"}), 401
    try:
        major_dict = dict(jwt_protocol.major_login(http_session, open_id, access_token))
        claims = decode_jwt_payload(major_dict.get('token'))
        response_payload['TokenValidation'] = validate_like_jwt(
            http_session, major_dict.get('token'),
            major_dict.get('account_id') or claims.get('account_id'),
            major_dict.get('lock_region') or claims.get('lock_region'))
        for field in ('account_id', 'lock_region', 'noti_region'):
            if not major_dict.get(field) and claims.get(field) is not None:
                major_dict[field] = claims[field]
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

    except (requests.RequestException, ValueError):
        return jsonify({"status": "error", "message": "MajorLogin or JWT profile validation failed"}), 502

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

def run_like_api(token_file, endpoint_name, auto_slot=False):
    uid = request.args.get("uid")
    requested_region = request.args.get("region") or request.args.get("server_name")

    if not uid:
        return jsonify({"success": False, "error": f"UID is required. Use /{endpoint_name}?uid=xxx"}), 400
    try:
        int(uid)
    except ValueError:
        return jsonify({"success": False, "error": "uid must be a number"}), 400

    region = normalize_region(requested_region)
    detected_region = None
    if region and region not in REGNS:
        return jsonify({"success": False, "error": f"Unsupported region: {region}"}), 400
    if not region:
        detected_region = normalize_region(get_cached_region(uid))
        if detected_region not in REGNS:
            player_data, lookup_region = fetch_player_personal_show(uid)
            basic_info = (player_data or {}).get("basicInfo") or (player_data or {}).get("basic_info") or {}
            detected_region = normalize_region(basic_info.get("region") or lookup_region)
            if detected_region in REGNS:
                set_cached_region(uid, detected_region)
        region = detected_region
        if region not in REGNS:
            return jsonify({
                "success": False,
                "error": "Automatic region lookup failed. Check the UID or retry when the profile service is available.",
                "code": "REGION_LOOKUP_FAILED",
                "profile_check": f"/meanffinfo?uid={uid}",
            }), 502

    reservation = None
    tracker = FAHHHH.extensions["slot_usage"]
    try:
        slot = None
        slot_new = False
        if auto_slot:
            configured_tokens = {
                candidate: load_like_tokens(token_file=token_file, slot=candidate)
                for candidate in range(1, LIKEFF_SLOT_COUNT + 1)
            }
            reservation = tracker.reserve([candidate for candidate, tokens in configured_tokens.items() if tokens])
            slot = reservation[2]
            slot_new = True

        like_tokens = configured_tokens[slot] if auto_slot else load_like_tokens(token_file=token_file, slot=slot)
        if not like_tokens:
            slot_msg = f" for slot {slot}" if slot else ""
            return jsonify({"success": False, "error": f"No {endpoint_name} tokens configured{slot_msg}"}), 503

        before = asyncio.run(fetch_like_info_with_tokens(uid, region, like_tokens))
        before_info = get_like_account_info(before)
        before_likes = int(before_info.get("Likes", 0) or 0)

        results = asyncio.run(send_like_requests(uid, region, tokens=like_tokens))

        after = asyncio.run(fetch_like_info_with_tokens(uid, region, like_tokens))
        after_info = get_like_account_info(after)
        after_likes = int(after_info.get("Likes", 0) or 0)
        likes_given = after_likes - before_likes

        payload = {
            "success": True,
            "LikesGivenByAPI": likes_given,
            "LikesafterCommand": after_likes,
            "LikesbeforeCommand": before_likes,
            "PlayerNickname": after_info.get("PlayerNickname", ""),
            "Region": detected_region or region,
            "UID": int(after_info.get("UID", uid) or uid),
            "status": 1 if likes_given > 0 else 2,
            "slot": slot,
            "slot_new": slot_new,
            "tokens_used": len(like_tokens),
            "send_results": summarize_like_results(results, like_tokens),
        }

        if auto_slot and slot:
            usage = tracker.finish(reservation, likes_given)
            reservation = None
            payload["usage"] = usage
            payload["slot_usage"] = f"{usage['used']}/{usage['max_limit']}"

        return jsonify(payload), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "slot": slot}), 500

    finally:
        if reservation is not None:
            tracker.finish(reservation, 0)

@FAHHHH.route('/like', methods=['GET'])
def like_api():
    return run_like_api(LIKE_TOKEN_FILE, "like")

@FAHHHH.route('/likeff', methods=['GET'])
def likeff_api():
    return run_like_api(LIKEFF_TOKEN_FILE, "likeff", auto_slot=True)

@FAHHHH.route('/meanffinfo')
def OMG():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Please provide UID."}), 400
    data, _ = fetch_player_personal_show(uid)
    if data is None:
        return jsonify({"error": "UID not found or profile lookup unavailable."}), 404
    return json.dumps(data, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}


def fetch_player_personal_show(uid):
    uid = str(uid)
    candidates = [get_cached_region(uid), UID_MEMORY.get(uid), *sorted(REGNS)]
    tried = set()
    for candidate in candidates:
        reg = normalize_region(candidate)
        if reg not in REGNS or reg in tried:
            continue
        tried.add(reg)
        try:
            data = asyncio.run(LoL(uid, "7", reg, "/GetPlayerPersonalShow"))
            basic = data.get("basicInfo") or data.get("basic_info") or {}
            account_id = basic.get("accountId") or basic.get("account_id")
            region = normalize_region(basic.get("region"))
            if str(account_id) != uid or region not in REGNS:
                continue
            data = HeHe(data)
        except Exception as exc:
            FAHHHH.logger.warning("Profile lookup failed for region %s (%s)", reg, type(exc).__name__)
            continue
        UID_MEMORY[uid] = region
        set_cached_region(uid, region)
        return data, region
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
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()
    jwt_token = raw_token if looks_like_jwt(raw_token) else None
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
        "message": "Bio update accepted by server",
        "stored": None,
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
    port = int(os.environ.get("PORT", 5000))
    FAHHHH.run(host="0.0.0.0", port=port)
