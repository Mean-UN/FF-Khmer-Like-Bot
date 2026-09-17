"""Guest creation protocol fields from the supplied reference implementation."""

import random

import time

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn","PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt"}

REGION_HOSTS = {
    "ME": "loginbp.common.ggbluefox.com",
    "TH": "loginbp.common.ggbluefox.com",
    "IND": "loginbp.ggpolarbear.com",
    "ID": "loginbp.ggpolarbear.com",
    "VN": "loginbp.ggpolarbear.com",
    "BD": "loginbp.ggpolarbear.com",
    "PK": "loginbp.ggpolarbear.com",
    "TW": "loginbp.ggpolarbear.com",
    "CIS": "loginbp.ggpolarbear.com",
    "SAC": "loginbp.ggpolarbear.com",
    "BR": "loginbp.ggblueshark.com",
    "GHOST": "loginbp.ggblueshark.com"
}

USER_AGENTS = [
    "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2022.3.45f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
    "Dalvik/2.1.0 (Linux; U; Android 11; Redmi Note 9 Pro Build/RP1A.200720.011)",
    "GarenaMSDK/4.0.42(KB2003 ;Android 13;en;HK;app 2.130.1 2019118332;)",
    "okhttp/4.9.2",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
]

def random_ua():
    return random.choice(USER_AGENTS)

def random_ip():
    return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"

def random_user_id():
    return f"Google|{''.join(random.choices('0123456789abcdef', k=8))}-{''.join(random.choices('0123456789abcdef', k=4))}-{''.join(random.choices('0123456789abcdef', k=4))}-{''.join(random.choices('0123456789abcdef', k=4))}-{''.join(random.choices('0123456789abcdef', k=12))}"

def login_fields(region, open_id, access_token, is_ghost=False):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
            3: now,
            4: "free fire",
            5: 1,
            7: "1.132.3",
            8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
            9: "Handheld",
            10: "Vi India",
            11: "WIFI",
            12: 1600,
            13: 720,
            14: "320",
            15: "ARM64 FP ASIMD AES | 2301 | 8",
            16: 2799,
            17: "PowerVR Rogue GE8320",
            18: "OpenGL ES 3.2 build 1.11@5425693",
            19: random_user_id(),
            20: random_ip(),
            21: REGION_LANG.get(region.upper(), "en") if not is_ghost else "pt",
            22: open_id,
            23: "4",
            24: "Handheld",
            25: "realme RMX2189",
            26: region.upper() if not is_ghost else "BR",
            29: access_token,
            30: 1,
            41: "Vi India",
            42: "WIFI",
            57: "1ac4b80ecf0478a44203bf8fac6120f5",
            60: 19799,
            61: 201,
            62: 5056,
            64: 433,
            65: 19999,
            66: 201,
            67: 19799,
            70: 4,
            73: 2,
            74: "/data/app/com.dts.freefireth-DhhtHV35iyaox_nT1wACyw==/lib/arm64",
            76: 1,
            77: "4c322aeb56444feaa151d1ea91a8f7f2|/data/app/com.dts.freefireth-DhhtHV35iyaox_nT1wACyw==/base.apk",
            78: 6,
            79: 2,
            81: "64",
            83: "2019120816",
            86: "OpenGLES2",
            87: 3071,
            88: 8,
            92: 13891,
            93: "3rd_party",
            94: "KqsHTxzwonOaDxctr7lcZMg1KjER292xcCs41IFIq3w5DlNu2vZmQLdt3EWcqNRj1EO4tC0auQM50Y5L+TU5LYVnqIY=",
            95: 111207,
            96: '{"cur_rate":null,"support_etc2":false}',
            97: 1,
            99: "4",
            100: "4",
            102: b'C\x04AD\x07\r^Uf'
        }

def refresh_login_fields(region, open_id, access_token):
    """OB55 / 1.132.1 refresh layout from the supplied working capture.

    Credentials, timestamp, language and generated device identifiers remain
    dynamic; the captured account's credentials are never stored here.
    """
    fields = login_fields(region, open_id, access_token)
    fields.pop(26, None)
    fields.pop(96, None)
    fields.update({
        7: "1.132.1",
        8: "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)",
        10: "MTN/Spacetel",
        12: 1280,
        14: "240",
        15: "x86-64 SSE3 SSE4.1 SSE4.2 AVX AVX2 | 2400 | 4",
        16: 3942,
        17: "Adreno (TM) 640",
        18: "OpenGL ES 3.2",
        25: "OnePlus A5010",
        41: "MTN/Spacetel",
        60: 46901,
        61: 32794,
        62: 2479,
        63: 900,
        64: 34727,
        65: 46901,
        66: 34727,
        67: 46901,
        73: 1,
        74: "/data/app/com.dts.freefireth-fpXCSphIV6dKC7jL-WOyRA==/lib/arm",
        77: "e62ab9354d8fb5fb081db338acb33491|/data/app/com.dts.freefireth-fpXCSphIV6dKC7jL-WOyRA==/base.apk",
        79: 1,
        81: "32",
        83: "2019119026",
        85: 3,
        87: 255,
        88: 4,
        92: 16190,
        94: "KqsHT8W93GdcG3ZozENfFwVHtm7qq1eRUNaIDNgRobozIBtLOiYCc4Y6zvvpcICxzQF2sOE4cbytwLs4xZbRnpRMpmWRQKmeO5vcs8nQYBhwqH7K",
        98: 1,
        102: bytes.fromhex("13521146500e590349510e460900115843395f005b510f685b560a6107576d0f0366"),
    })
    return fields


def region_host(region, is_ghost=False):
    return REGION_HOSTS["GHOST"] if is_ghost else REGION_HOSTS.get(region.upper(), REGION_HOSTS["IND"])
