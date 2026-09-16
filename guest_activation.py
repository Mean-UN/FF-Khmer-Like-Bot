"""Guest activation using the supplied token / MajorLogin / GetLoginData flow."""

import json
import time
from datetime import datetime
from urllib.parse import urlparse
import requests
import guest_protocol
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


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


def activate_guest(uid, password, region="IND"):
    for attempt in range(5):
        result = _activate_guest_once(uid, password, region)
        if result.get("success") or not result.get("retryable") or attempt == 4:
            return result
        time.sleep(min(2 ** attempt, 8))


def _activate_guest_once(uid, password, region="IND"):
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
            payload = major_login_payload(access, open_id, int(data.get("platform") or 4), region)
            headers = {"X-Unity-Version": "2022.3.47f1", "ReleaseVersion": "OB54", "Content-Type": "application/x-www-form-urlencoded", "X-GA": "v1 1", "User-Agent": guest_protocol.random_ua(), "Connection": "Keep-Alive", "Accept-Encoding": "gzip"}
            stage = "MajorLogin"
            response = session.post(f"https://{guest_protocol.region_host(region, region == 'GHOST')}/MajorLogin", data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            candidates = []
            try:
                candidates.append(unpad(AES.new(aes_key, AES.MODE_CBC, aes_iv).decrypt(response.content), AES.block_size))
            except ValueError:
                pass
            candidates.append(response.content)
            login = {}
            for content in candidates:
                try:
                    candidate = decode_protobuf(content)
                    if isinstance(candidate.get(8), bytes) and isinstance(candidate.get(10), bytes):
                        login = candidate
                        break
                except ValueError:
                    continue
            jwt = login.get(8, b"").decode("utf-8")
            server = login.get(10, b"").decode("utf-8")
            if not jwt or not server:
                raise ValueError("Missing JWT or server URL")
            stage = "Login server validation"
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
        return {"success": False, "uid": str(uid), "error": f"{stage} failed ({reason})",
                "retryable": stage == "MajorLogin" and isinstance(exc, ValueError)}

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

def major_login_payload(access_token, open_id, platform_type=4, region="IND"):
    fields = guest_protocol.login_fields(region, open_id, access_token, region == "GHOST")
    fields[23] = str(platform_type)
    fields[88] = int(platform_type)
    fields[99] = str(platform_type)
    fields[100] = str(platform_type)
    plain = bytes(create_proto(fields))
    return AES.new(aes_key, AES.MODE_CBC, aes_iv).encrypt(pad(plain, AES.block_size))
