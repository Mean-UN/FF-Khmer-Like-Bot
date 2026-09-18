"""Shared JWT login protocol adapted from the supplied OB55 reference."""
import base64
import gzip
import json
import re
import zlib
from datetime import datetime

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from proto import MajorLoginReq_pb2, MajorLoginRes_pb2

CLIENT_VERSION = "1.132.3"
CLIENT_VERSION_CODE = "2024010012"
RELEASE_VERSION = "OB55"
OAUTH_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
INSPECT_URL = "https://100067.connect.garena.com/oauth/token/inspect"
MAJOR_LOGIN_URL = "https://loginbp.ggblueshark.com/MajorLogin"
PROTO_KEY = b'Yg&tc%DEuh6%Zc^8'
PROTO_IV = b'6oyZDr22E3ychjM%'


def generate_access_token(session, uid, password, client_secret):
    response = session.post(OAUTH_URL, data={
        "uid": str(uid), "password": password, "response_type": "token",
        "client_type": "2", "client_id": "100067", "client_secret": client_secret,
    }, headers={"User-Agent": "GarenaMSDK/5.5.2P3(SM-A515F;Android 12;en-US;IND;)"}, timeout=30)
    response.raise_for_status()
    auth = response.json()
    inner = auth.get("data", auth) if isinstance(auth, dict) else {}
    if not isinstance(inner, dict) or not inner.get("open_id") or not inner.get("access_token"):
        raise ValueError("Guest authentication did not return access_token/open_id")
    return auth, str(inner["open_id"]), inner["access_token"]


def inspect_token(session, token):
    response = session.get(INSPECT_URL, params={"token": token}, timeout=15)
    response.raise_for_status()
    info = response.json()
    if not isinstance(info, dict) or info.get("error") or not info.get("open_id"):
        raise ValueError("Access token inspection did not return open_id")
    return info


def decompress_body(data):
    for decompress in (gzip.decompress, zlib.decompress,
                       lambda value: zlib.decompress(value, -zlib.MAX_WBITS)):
        try:
            return decompress(data)
        except (OSError, EOFError, zlib.error):
            pass
    return data


def parse_login_response(data):
    data = decompress_body(data)
    candidates = [data]
    if data and len(data) % AES.block_size == 0:
        try:
            candidates.append(decompress_body(unpad(
                AES.new(PROTO_KEY, AES.MODE_CBC, PROTO_IV).decrypt(data), AES.block_size)))
        except ValueError:
            pass
    for candidate in candidates:
        for offset in range(min(64, len(candidate))):
            response = MajorLoginRes_pb2.MajorLoginRes()
            try:
                response.ParseFromString(candidate[offset:])
            except DecodeError:
                continue
            if response.token:
                return MessageToDict(response, preserving_proto_field_name=True)
    # Field 8 is a length-delimited JWT. Preserve its exact bytes even if
    # unrelated trailing fields are malformed. Regex over the response can
    # consume an adjacent protobuf tag as part of the JWT signature.
    for candidate in candidates:
        for position, tag in enumerate(candidate):
            if tag != 0x42:
                continue
            cursor = position + 1
            length = 0
            for shift in range(0, 35, 7):
                if cursor >= len(candidate):
                    break
                value = candidate[cursor]
                cursor += 1
                length |= (value & 0x7f) << shift
                if value < 0x80:
                    if length <= 0 or cursor + length > len(candidate):
                        break
                    raw_token = candidate[cursor:cursor + length]
                    if not re.fullmatch(rb'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', raw_token):
                        break
                    try:
                        token = raw_token.decode('ascii')
                        payload = token.split('.')[1]
                        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
                        if not isinstance(claims, dict):
                            break
                    except (ValueError, UnicodeError):
                        break
                    result = {"token": token}
                    if claims.get("account_id") is not None:
                        result["account_id"] = str(claims["account_id"])
                    if claims.get("lock_region"):
                        result["lock_region"] = claims["lock_region"]
                    return result
    raise ValueError("MajorLogin did not return a JWT token")


def major_login(session, open_id, access_token):
    payload = build_major_login_request(open_id, access_token).SerializeToString()
    encrypted = AES.new(PROTO_KEY, AES.MODE_CBC, PROTO_IV).encrypt(pad(payload, AES.block_size))
    response = session.post(MAJOR_LOGIN_URL, data=encrypted, headers={
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
        "X-Ga-Sv": str(int(datetime.now().timestamp())), "Authorization": "Bearer",
        "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded", "X-Unity-Version": "2018.4.12f1",
    }, timeout=30)
    response.raise_for_status()
    return parse_login_response(response.content)


def build_major_login_request(open_id, access_token):
    major_login = MajorLoginReq_pb2.MajorLogin()
    major_login.event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    major_login.game_name = "free fire"
    major_login.platform_id = 1
    major_login.client_version = CLIENT_VERSION
    major_login.system_software = "Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)"
    major_login.system_hardware = "Handheld"
    major_login.telecom_operator = "Verizon"
    major_login.network_type = "WIFI"
    major_login.screen_width = 1920
    major_login.screen_height = 1080
    major_login.screen_dpi = "280"
    major_login.processor_details = "ARM64 FP ASIMD AES VMH | 2865 | 4"
    major_login.memory = 3003
    major_login.gpu_renderer = "Adreno (TM) 640"
    major_login.gpu_version = "OpenGL ES 3.1 v1.46"
    major_login.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    major_login.client_ip = "0.0.0.0"
    major_login.language = "en"
    major_login.open_id = open_id
    major_login.open_id_type = "4"
    major_login.device_type = "Handheld"
    major_login.memory_available.version = 55
    major_login.memory_available.hidden_value = 81
    major_login.access_token = access_token
    major_login.platform_sdk_id = 1
    major_login.network_operator_a = "Verizon"
    major_login.network_type_a = "WIFI"
    major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    major_login.external_storage_total = 36235
    major_login.external_storage_available = 31335
    major_login.internal_storage_total = 2519
    major_login.internal_storage_available = 703
    major_login.game_disk_storage_available = 25010
    major_login.game_disk_storage_total = 26628
    major_login.external_sdcard_avail_storage = 32992
    major_login.external_sdcard_total_storage = 36235
    major_login.login_by = 3
    major_login.library_path = "/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/lib/arm64"
    major_login.reg_avatar = 1
    major_login.library_token = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/base.apk"
    major_login.channel_type = 3
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.client_version_code = CLIENT_VERSION_CODE
    major_login.graphics_api = "OpenGLES2"
    major_login.supported_astc_bitset = 16383
    major_login.login_open_id_type = 4
    major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWA0FUgsvA1snWlBaO1kFYg=="
    major_login.loading_time = 13564
    major_login.release_channel = "android"
    major_login.extra_info = "KqsHTymw5/5GB23YGniUYN2/q47GATrq7eFeRatf0NkwLKEMQ0PK5BKEk72dPflAxUlEBir6Vtey83XqF593qsl8hwY="
    major_login.android_engine_init_flag = 110009
    major_login.if_push = 1
    major_login.is_vpn = 0
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"
    return major_login
