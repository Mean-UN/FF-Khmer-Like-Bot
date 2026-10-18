"""Device and network profiles adapted from the supplied guest client."""
import random
import threading

class FastIPSpoofer:
    _POOL = [f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(20000)]
    _idx = 0
    _lock = threading.Lock()
    @classmethod
    def get(cls):
        with cls._lock:
            ip = cls._POOL[cls._idx % len(cls._POOL)]
            cls._idx += 1
            return ip

    @classmethod
    def get_ip(cls):
        return cls.get()

class WAFBypass:
    _uas = [
        "GarenaMSDK/4.0.42(SM-A525F ;Android)",
        "GarenaMSDK/4.0.39(SM-A325M;Android 13;en;HK;)",
        "GarenaMSDK/4.0.38(Redmi Note 10;Android 12;en;ID;)",
        "GarenaMSDK/4.0.40(Poco X3;Android 11;en;SG;)",
        "GarenaMSDK/4.0.41(SM-S918B;Android 14;en;IN;)",
        "GarenaMSDK/4.0.42(OnePlus 11;Android 13;en;US;)",
        "GarenaMSDK/4.0.39(Xiaomi 13 Pro;Android 13;pt;BR;)",
        "GarenaMSDK/4.0.40(Pixel 7 Pro;Android 14;en;US;)",
        "GarenaMSDK/4.0.42(Infinix X6819;Android 13;en;PK;)",
        "GarenaMSDK/4.0.41(vivo 1906;Android 11;en;BD;)",
    ]
    @staticmethod
    def get_ua(): return random.choice(WAFBypass._uas)

class DevicePool:
    _devices, _index, _lock = [], 0, threading.Lock()
    DEVICE_MODELS = [
        ("Asus ASUS_I005DA", "ARMv7 VFPv3 NEON VMH | 2400 | 2", "Adreno (TM) 640"),
        ("SM-A525F", "ARMv8 VFPv4 NEON VMH | 2200 | 8", "Adreno (TM) 618"),
        ("SM-A325M", "ARMv8 VFPv4 NEON VMH | 2000 | 8", "Mali-G52"),
        ("SM-S918B", "ARMv8 VFPv4 NEON VMH | 3200 | 8", "Adreno (TM) 740"),
        ("Redmi Note 10","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 619"),
        ("Redmi Note 11","ARMv8 VFPv4 NEON VMH | 2400 | 8","Adreno (TM) 610"),
        ("Poco X3","ARMv8 VFPv4 NEON VMH | 2300 | 8","Adreno (TM) 618"),
        ("Poco M4 Pro","ARMv8 VFPv4 NEON VMH | 2200 | 8","Mali-G57"),
        ("Pixel 6","ARMv8 VFPv4 NEON VMH | 2800 | 8","Mali-G78"),
        ("Pixel 7 Pro","ARMv8 VFPv4 NEON VMH | 2800 | 8","Mali-G710"),
        ("OnePlus 9","ARMv8 VFPv4 NEON VMH | 2800 | 8","Adreno (TM) 660"),
        ("OnePlus 11","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
        ("Xiaomi 13 Pro","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
        ("Infinix X6819","ARMv8 VFPv4 NEON VMH | 2400 | 8","Mali-G57"),
        ("vivo 1906","ARMv8 VFPv4 NEON VMH | 2000 | 8","Adreno (TM) 610"),
        ("OPPO CPH2211","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 619"),
        ("realme RMX3363","ARMv8 VFPv4 NEON VMH | 2400 | 8","Adreno (TM) 642"),
        ("TECNO KI5","ARMv8 VFPv4 NEON VMH | 2000 | 8","Mali-G52"),
    ]
    ANDROID_VERSIONS = [
        ("Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)","9","28"),
        ("Android OS 10 / API-29 (QKQ1.200114.002)","10","29"),
        ("Android OS 11 / API-30 (RP1A.201005.001)","11","30"),
        ("Android OS 12 / API-31 (SP1A.210812.016)","12","31"),
        ("Android OS 12L / API-32 (SP2A.220505.002)","12","32"),
        ("Android OS 13 / API-33 (TQ3A.230805.001)","13","33"),
        ("Android OS 14 / API-34 (UP1A.231005.007)","14","34"),
    ]
    NETWORKS  = ["WIFI","4G","5G"]
    OPERATORS = ["ATM Mobils","Telkomsel","Indosat","XL Axiata","Airtel","Jio","Vodafone","Globe","Smart","Viettel","Mobifone","Claro","Vivo"]
    SDK_VER   = ["4.0.38","4.0.39","4.0.40","4.0.41","4.0.42"]

    @classmethod
    def _rh(cls, n): return ''.join(random.choices("0123456789abcdef", k=n))
    @classmethod
    def _uuid(cls): return f"{cls._rh(8)}-{cls._rh(4)}-{cls._rh(4)}-{cls._rh(4)}-{cls._rh(12)}"
    @classmethod
    def _mac(cls):  return "02:" + ":".join(cls._rh(2) for _ in range(5))

    @classmethod
    def init_pool(cls, count=1000):
        if cls._devices: return
        for _ in range(count):
            model, cpu, gpu = random.choice(cls.DEVICE_MODELS)
            android_full, android_ver, api = random.choice(cls.ANDROID_VERSIONS)
            cls._devices.append({
                "model": model, "brand": model.split()[0], "cpu": cpu, "gpu": gpu,
                "android_full": android_full, "android_version": android_ver, "api_level": api,
                "operator": random.choice(cls.OPERATORS), "network": random.choice(cls.NETWORKS),
                "sdk": random.choice(cls.SDK_VER), "mac": cls._mac(),
                "device_id": cls._rh(32), "android_id": cls._rh(16), "uuid": cls._uuid(),
                "imei": cls._rh(15), "fingerprint": cls._rh(40), "gl_renderer": "OpenGL ES 3.2",
                "lang_code": random.choice(["en","in","ar","hi","vi","th","pt","ru","es","bn","ur","zh"]),
            })

    @classmethod
    def get(cls):
        with cls._lock:
            dev = cls._devices[cls._index % len(cls._devices)]
            cls._index += 1
            return dev

    @classmethod
    def headers(cls, device=None):
        d = device or cls.get()
        return {
            "X-Device-Id": d["device_id"], "X-Android-Id": d["android_id"],
            "X-Device-Model": d["model"],  "X-Device-Brand": d["brand"],
            "X-OS-Version": d["android_version"], "X-API-Level": d["api_level"],
            "X-SDK-Version": d["sdk"], "X-Network-Type": d["network"],
            "X-Operator": d["operator"], "X-IMEI": d["imei"],
            "X-Mac": d["mac"], "X-Client-Uuid": d["uuid"],
        }

DevicePool.init_pool(1000)

def merge_headers(headers, device):
    updated = dict(headers)
    updated.update(DevicePool.headers(device))
    for key in ("X-Forwarded-For", "X-Real-IP", "X-Client-IP", "CF-Connecting-IP", "True-Client-IP"):
        updated.setdefault(key, FastIPSpoofer.get())
    updated.setdefault("Forwarded", f"for={FastIPSpoofer.get()}")
    return updated
