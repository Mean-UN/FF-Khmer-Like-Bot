"""Guest creation protocol fields from the supplied reference implementation."""

import os
from datetime import datetime, timezone
import guest_network
import random

import time

# Defaults supplied by the reference client; deployments can replace or clear them.
REGISTER_COOKIE = "datadome=oYpIhVco_RFvLHe_T9KFd5wuY0gcQuNfrlt4rHJY5QOkwv4TGt8gPMK32MbHuBdzJyfXnXlfzNZT_2tHr2kys8AMYT2~T71QP1S78_7Pdx4JLOXdSrflPT6cOX2vsyJh"
TOKEN_COOKIE = "datadome=y23Z3X17pgkMHEt5zY8dqxC6BIf7WJMgC0RXNbqifHT7t9zajKe_hegFb1Ie9_7JixXpz7FRGVodOn~mWPk_NrqIIhUOXDYqKOahzoRQcyEy77GWEMcdA9_MqPJeM5qv"


def oauth_cookie(stage):
    if stage == "register":
        return os.environ.get("GUEST_REGISTER_COOKIE", REGISTER_COOKIE).strip()
    if stage == "token":
        return os.environ.get("GUEST_TOKEN_COOKIE", TOKEN_COOKIE).strip()
    raise ValueError("Unknown guest OAuth stage")

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn","PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt"}

CREATION_HOST = "loginbp.ppmainecoonghj.com"
REGION_HOSTS = dict.fromkeys((*REGION_LANG, "SG", "EU", "US", "LK", "GHOST"), CREATION_HOST)
REGION_HOSTS.update(ME="loginbp.common.ggbluefox.com", TH="loginbp.common.ggbluefox.com")

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


def creation_login_fields(region, open_id, access_token, is_ghost=False, device=None):
    lang = "pt" if is_ghost else REGION_LANG.get(region.upper(), "en")
    dev = device or guest_network.DevicePool.get()
    gpu, model, os_str = dev["gpu"], dev["model"], dev["android_full"]
    gpu_full = f"{gpu}|OpenGL ES 3.2"
    operator, network = dev["operator"], dev["network"]
    device_uuid, cpu = dev["uuid"], dev["cpu"]
    ip_addr = guest_network.FastIPSpoofer.get_ip()
    open_id_b, access_token_b = open_id.encode(), access_token.encode()
    return {
            3:  datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            4:  b'free fire',
            5:  1,
            7:  "2.132.4",
            8:  os_str,
            9:  b'Handheld',
            10: operator,
            11: network,
            12: 1280,
            13: 720,
            14: b'240',
            15: cpu,
            16: random.choice([5951, 6000, 6100, 5500]),
            17: gpu,
            18: gpu_full,
            19: f'Google|{device_uuid}',
            20: ip_addr,
            21: lang,
            22: open_id_b,
            23: b'4',
            24: b'Handheld',
            25: model,
            26: lang,
            29: access_token_b,
            30: 1,
            41: operator,
            42: network,
            57: b'1ac4b80ecf0478a44203bf8fac6120f5',
            60: 30000, 61: 30000, 62: 2519, 63: 243,
            64: 32357, 65: 34308, 66: 32357, 67: 34308, 73: 1,
            74: b'/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/lib/arm',
            76: 2,
            77: b'428775ab8c8845bd341b5357ec61d15e|/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/base.apk',
            78: 2, 79: 1,
            81: b'32', 83: b'2019118525', 85: 3,
            86: b'OpenGLES3', 87: 4095, 88: 4,
            92: random.choice([19788, 20000, 21000]),
            93: b'android_max',
            94: b'KqsHT2gyPt7vUCc9SCjv2ioi3WEZSEL86ErvXB38suVVK/Z4IVt78ESl/r2S15C1pqu/j6ZmgFL7HbwoFiiVconX08ooKiisQffvEAPCo/C+Lahr',
            96: b'{"cur_rate":null,"support_etc2":true}',
            97: 1, 98: 1, 99: b'4', 100: b'4', 102: b'',
            104: 77149, 105: 1,
            106: b'https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462',
            107: b'c8e41b7a93f02d56e1a94c7b8203f5d1',
        }

def activation_fields(region, open_id, jwt):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    fields = {
        3: now, 4: "free fire", 5: 1, 7: "2.133.9",
        8: "Android OS 15 / API-35 (V2UUIS35.39-21-7-5-1-5/319a58-a9271)",
        9: "Handheld", 10: "airtel", 11: "CarrierDataNetwork",
        12: 2400, 13: 1080, 14: "400",
        15: "ARM64 FP ASIMD AES | 4800 | 8", 16: 7461,
        17: "Adreno (TM) 710",
        18: "OpenGL ES 3.2 V@0615.98 (GIT@0c393b63cf, I94e2bd5684, 1746191168) (Date:05/02/25)",
        19: "Google|0ea5b865-94e6-42dd-9f40-f52a63378bc7",
        20: "27.59.76.15", 21: "en",
        22: open_id, 23: "4",
        24: "Handheld", 25: "motorola moto g96 5G", 26: "TW",
        29: jwt, 30: 1,
        41: "airtel", 42: "4G",
        57: "1ac4b80ecf0478a44203bf8fac6120f5",
        60: 111316, 61: 73226, 62: 690, 64: 73354,
        65: 111316, 66: 73354, 67: 111316,
        73: 3,
        74: "/data/app/~~xI7rymUmXZFbQjaBVyScAw==/com.dts.freefiremax-lX62T7VsUJ9zo5dV1_axug==/lib/arm64",
        76: 2,
        77: "38f4751a330688ab124c2c804cec90a5|/data/app/~~xI7rymUmXZFbQjaBVyScAw==/com.dts.freefiremax-lX62T7VsUJ9zo5dV1_axug==/base.apk",
        78: 2, 79: 2, 81: "64", 83: "2019118527", 85: 3,
        86: "OpenGLES3", 87: 4095, 88: 4,
        90: "New Delhi", 91: "DL", 92: 12573, 93: "android_max",
        94: "KqsHT0wswggWbev04P17TGvl/w+c875HviaAj4qL+YhymI7Psonj/aQgNTNLf+4nm1LzYE6DxxzpZH9FX0Kt119zYuGdivC/V7aWpj4/HNhVAwJy",
        95: 111107,
        96: '{"cur_rate":[60,90,120,144],"support_etc2":true}',
        97: 1, 99: "0", 100: "4", 102: "",
        104: 95926, 105: 1,
        106: "https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.7a99d677ab872769",
    }
    fields[26] = region.upper()
    return fields

FIELD_22_HEX = '4747524501010100620200001052aa0d669c6a368f08338060d2ee0690053af84a41edcd3558556ec10f24f46c93ac64ca41a16732c46a2cb071246a79b8929032f9e1b6f4ef331bd53cabf29b09b97349a46e9863c0314e1a0d80819fef8aabf03876b3d037db354a7ccb5c1bce96411fb3753f6f50e44c69c4ed617fa30efb8ffc0517ff2f636739be1f304d999cfd6fd48bf69454199794c3dc88f55a4bdbd66534d5a061359cdfd1fb680cd37918df9fdb3cf7d80067b0a3506c90063cf62b2ccec11e23913a2fd7c4ef091331967bb518a5ad1e551146b90821be800883abadde39d6c80a5d798611466c748f075481806c5842ce45e6bd4e3368ec08fe2ec41ceb880cd86249eb71693f79f0bccf9e590c3fae12519fe08c7a1905d0927690109e0df28574bb14847225db1a59230e6662ed7730e15ff9a6c815cb41b420edeada735a4b03e181037c37c2c850257311df2f07b0a56e759372cbd0268e3f13a292ee4373e38ab5096e0342a5e0d7fec6da2bbc265d74baadd2b24ee4f74862f82c21d6694bac53f8ce80312a30068a6276a641c19b11d0305c6fe2f531ac7de578b29f543697f5c73663e6f23aa15277b6122dcd4d4171e38f9ac0b173f39c58416a16c5c1f4a35acd065ce78f449cf538a249339e763272d458e4ed86c976591a9c066b3a37111e44091eb6b5a795249f3e5145db022a6055f2cc675936391312f688f89627845df222a91156555225be36f9714a0ba50246d0f003bda3c9c1292ab73b4f79635ddd023218eda93a302d79e023404c14396544a930b98ed54771aca7fec10d095587685b473e81a9619764fad9256529dcd6e911f4f4629612287d4ee3ec5389f6ec4ec020b0e2aac017232a9197be9e46239ce690fe5d4872b2e98e651510c971667f3aca8b59f3e9d50e43'
