"""Guest activation using the supplied token / MajorLogin / GetLoginData flow."""

import json
from datetime import datetime
from urllib.parse import urlparse
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def decode_protobuf(data):
    offset, fields = 0, {}
    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise ValueError("Truncated protobuf")
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError("Invalid protobuf varint")
    while offset < len(data):
        tag = varint()
        field, wire = tag >> 3, tag & 7
        if field == 0:
            raise ValueError("Invalid protobuf field")
        if wire == 0:
            fields[field] = varint()
        elif wire in (1, 2, 5):
            length = varint() if wire == 2 else (8 if wire == 1 else 4)
            if offset + length > len(data):
                raise ValueError("Truncated protobuf field")
            fields[field] = data[offset:offset + length]
            offset += length
        else:
            raise ValueError("Unsupported protobuf wire type")
    return fields


def parse_accounts(raw):
    data = json.loads(raw)
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            data = data["items"]
        else:
            data = data.get("accounts", [data] if "uid" in data else list(data.values()))
    if not isinstance(data, list) or not data or len(data) > 10000:
        raise ValueError("Provide a JSON list containing 1–10,000 accounts.")
    accounts, seen = [], set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each account needs uid and password fields.")
        uid, password = str(item.get("uid") or "").strip(), item.get("password")
        if not uid.isascii() or not uid.isdigit() or int(uid) <= 0 or not isinstance(password, str) or not password:
            raise ValueError("Each account needs a positive numeric UID and a nonempty password.")
        uid = str(int(uid))
        if uid in seen:
            raise ValueError(f"Duplicate UID in file: {uid}")
        seen.add(uid)
        accounts.append({"uid": uid, "password": password})
    return accounts


def activate_guest(uid, password):
    stage = "Token grant"
    try:
        with requests.Session() as session:
            response = session.post("https://100067.connect.garena.com/oauth/guest/token/grant",
                data={"uid": str(uid), "password": password, "response_type": "token", "client_type": "2", "client_secret": HEX_KEY, "client_id": "100067"},
                headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G960F Build/PIE)", "Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                data = data["data"]
            access, open_id = data.get("access_token"), data.get("open_id")
            if not access or not open_id:
                return {"success": False, "uid": str(uid), "error": "Token grant did not return access_token/open_id"}
            payload = major_login_payload(access, open_id, int(data.get("platform") or 4))
            headers = {"X-Unity-Version": "2018.4.11f1", "ReleaseVersion": "OB54", "Content-Type": "application/x-www-form-urlencoded", "X-GA": "v1 1", "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)", "Connection": "Keep-Alive", "Accept-Encoding": "gzip"}
            stage = "MajorLogin"
            response = session.post("https://loginbp.ggpolarbear.com/MajorLogin", data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            login = decode_protobuf(response.content)
            jwt = login.get(8, b"").decode("utf-8")
            server = login.get(10, b"").decode("utf-8")
            if not jwt or not server:
                raise ValueError("Missing JWT or server URL")
            parsed = urlparse(server)
            domains = ("freefiremobile.com", "garenanow.com", "ggpolarbear.com", "ggblueshark.com", "ggbluefox.com")
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or not any(host == domain or host.endswith("." + domain) for domain in domains):
                raise ValueError("Unexpected login server URL")
            stage = "GetLoginData"
            response = session.post(server.rstrip("/") + "/GetLoginData", data=payload,
                headers={**headers, "Authorization": "Bearer " + jwt}, timeout=30, allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200 or not decode_protobuf(response.content):
                raise ValueError("No login data returned")
            return {"success": True, "uid": str(uid)}
    except Exception as exc:
        response = getattr(exc, "response", None)
        reason = f"HTTP {response.status_code}" if response is not None else type(exc).__name__
        return {"success": False, "uid": str(uid), "error": f"{stage} failed ({reason})"}

aes_key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])

aes_iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

def create_vr(N):
    if N < 0:
        return b''
    H = []
    while True:
        S = N & 0x7F
        N >>= 7
        if N:
            S |= 0x80
        H.append(S)
        if not N:
            break
    return bytes(H)

def create_variant(field_number, value):
    field_header = (field_number << 3) | 0
    return create_vr(field_header) + create_vr(value)

def create_length(field_number, value):
    field_header = (field_number << 3) | 2
    encoded = value.encode() if isinstance(value, str) else value
    return create_vr(field_header) + create_vr(len(encoded)) + encoded

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = create_proto(value)
            packet.extend(create_length(field, nested))
        elif isinstance(value, int):
            packet.extend(create_variant(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(create_length(field, value))
    return packet

def encrypt_aes(hex_data):
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    return cipher.encrypt(pad(bytes.fromhex(hex_data), AES.block_size)).hex()

def major_login_payload(access_token, open_id, platform_type):
    """Build the major login payload"""
    fields = {
        3: str(datetime.now())[:-7],
        4: "free fire",
        5: 1,
        7: "1.129.16",
        8: "Android OS 14 / API-34 (UKQ1.230917.001/V816.0.1.0.UMWJPSB)",
        9: "Handheld",
        11: "WIFI",
        12: 1708,
        13: 750,
        14: "440",
        15: "ARM64 FP ASIMD AES | 2208 | 8",
        16: 3479,
        17: "Adreno (TM) 613",
        18: "OpenGL ES 3.2 V@0615.74 (GIT@dad4038ba6, If56d4a5bb8, 1690544947) (Date:07/28/23)",
        19: "Google|27ed2fb9-7ace-4842-9ebf-0d42c7140201",
        20: "103.13.194.48",
        21: "en",

        # Keep open_id dynamic
        22: open_id,

        # Keep platform_type dynamic
        23: platform_type,

        24: "Handheld",

        # Updated nested value
        25: {
            11: 77,
            12: 3544390361061879151
        },

        26: "IND",

        # Keep access_token dynamic
        29: access_token,

        30: 1,
        42: "WIFI",
        57: "7428b253defc164018c604a1ebbfebdf",
        60: 110509,
        61: 21773,
        62: 697,
        64: 21900,
        65: 110509,
        66: 21901,
        67: 110509,
        73: 2,

        74: "/data/app/~~EpSlHHqFKGJfMTVJpAvb5w==/"
            "com.dts.freefireth-Shl9-60UzaOsFQ7x6PHgSg==/lib/arm64",

        76: 1,

        77: "1f74b435e72dfb267bce75a21d10074a|"
            "/data/app/~~EpSlHHqFKGJfMTVJpAvb5w==/"
            "com.dts.freefireth-Shl9-60UzaOsFQ7x6PHgSg==/base.apk",

        78: 3,
        79: 2,
        81: "64",
        83: "2019120913",
        85: 3,
        86: "OpenGLES2",
        87: 4095,

        # Keep platform_type dynamic
        88: platform_type,

        92: 10285,
        93: "android",

        94: "KqsHTyuSJ78t/H8E+JqM6PNc3n7w15pJi/"
            "lyZ+7Y2kBYk3AJRBifvyrHKx40dPQZ+wMPwEsYJfRl/"
            "joQS/k+WLPgL+E=",

        95: 111207,
        96: '{"cur_rate":[60,48,30,90],"support_etc2":false}',
        97: 1,

        # Keep platform_type dynamic
        99: platform_type,
        100: platform_type,

        102: "40014546075a080937"
    }

    pyl = create_proto(fields).hex()
    payload = bytes.fromhex(encrypt_aes(pyl))
    return payload
