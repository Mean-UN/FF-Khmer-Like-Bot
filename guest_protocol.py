"""Guest creation protocol fields from the supplied reference implementation."""

import random

import time

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn","PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt"}

CREATION_HOST = "loginbp.ppmainecoonghj.com"
REGION_HOSTS = dict.fromkeys((*REGION_LANG, "SG", "EU", "US", "LK", "GHOST"), CREATION_HOST)

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

def region_host(region, is_ghost=False):
    return REGION_HOSTS["GHOST"] if is_ghost else REGION_HOSTS.get(region.upper(), REGION_HOSTS["IND"])


def creation_login_fields(region, open_id, access_token, is_ghost=False):
    """SIAM reference login fields, rebuilt with proper protobuf lengths."""
    fields = {3: b'2025-08-30 05:19:21',
     4: b'free fire',
     5: 1,
     7: b'1.114.13',
     8: b'Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)',
     9: b'Handheld',
     10: b'ATM Mobils',
     11: b'WIFI',
     12: 1334,
     13: 750,
     14: b'300',
     15: b'ARMv7 VFPv3 NEON VMH | 2400 | 2',
     16: 1993,
     17: b'Adreno (TM) 640',
     18: b'OpenGL ES 3.2',
     19: b'Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f',
     20: b'105.235.139.91',
     21: b'en',
     22: b'1d8ec0240ede109973f3321b9354b44d',
     23: b'4',
     24: b'Handheld',
     25: b'Asus ASUS_I005DA',
     29: b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390',
     30: 1,
     41: b'ATM Mobils',
     42: b'WIFI',
     57: b'7428b253defc164018c604a1ebbfebdf',
     60: 32936,
     61: 29430,
     62: 2479,
     63: 900,
     64: 30823,
     65: 32936,
     66: 30823,
     67: 32936,
     73: 1,
     74: b'/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm',
     76: 1,
     77: b'2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCS'
         b'Fn37p1AH_FLg==/base.apk',
     78: 3,
     79: 1,
     81: b'32',
     83: b'2019118693',
     86: b'OpenGLES2',
     87: 16383,
     88: 4,
     92: 9075,
     93: b'android',
     94: b'KqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptNrGB0Ll0L'
         b'Rz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2',
     95: 111227,
     97: 1,
     98: 1,
     99: b'4',
     100: b'4',
     102: b'GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'}
    fields[21] = "pt" if is_ghost else REGION_LANG.get(region.upper(), "en")
    fields[22] = open_id
    fields[29] = access_token
    return fields
