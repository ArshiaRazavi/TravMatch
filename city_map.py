# city_map.py — FA/EN city/airport aliases → IATA code

import re

ALIASES = {
    # ---- Iran (city or main airport) ----
    "تهران": "THR", "tehran": "THR", "thr": "THR",
    "امام": "IKA", "امام خمینی": "IKA", "ikia": "IKA", "ika": "IKA",
    "mehrabad": "THR", "مهرآباد": "THR",

    "مشهد": "MHD", "mashhad": "MHD", "mhd": "MHD",
    "شیراز": "SYZ", "shiraz": "SYZ", "syz": "SYZ",
    "اصفهان": "IFN", "isfahan": "IFN", "ifn": "IFN",
    "تبریز": "TBZ", "tabriz": "TBZ", "tbz": "TBZ",
    "اهواز": "AWZ", "ahvaz": "AWZ", "awz": "AWZ",
    "کیش": "KIH", "kish": "KIH", "kih": "KIH",
    "قشم": "GSM", "qeshm": "GSM", "gsm": "GSM",
    "کرمان": "KER", "kerman": "KER", "ker": "KER",
    "یزد": "AZD", "yazd": "AZD", "azd": "AZD",
    "بندرعباس": "BND", "bandar abbas": "BND", "bnd": "BND",
    "رشت": "RAS", "rasht": "RAS", "ras": "RAS",
    "ارومیه": "OMH", "urmia": "OMH", "omh": "OMH",
    "ساری": "SRY", "sari": "SRY", "sry": "SRY",
    "بوشهر": "BUZ", "bushehr": "BUZ", "buz": "BUZ",

    # ---- Canada ----
    "تورنتو": "YYZ", "toronto": "YYZ", "yyz": "YYZ", "pearson": "YYZ",
    "ونکوور": "YVR", "vancouver": "YVR", "yvr": "YVR",
    "مونترال": "YUL", "montreal": "YUL", "yul": "YUL",
    "ادمونتون": "YEG", "edmonton": "YEG", "yeg": "YEG",
    "کلگری": "YYC", "calgary": "YYC", "yyc": "YYC",
    "اتاوا": "YOW", "ottawa": "YOW", "yow": "YOW",
    "هالیفاکس": "YHZ", "halifax": "YHZ", "yhz": "YHZ",
    "وینیپگ": "YWG", "winnipeg": "YWG", "ywg": "YWG",
    "کبک": "YQB", "quebec": "YQB", "yqb": "YQB",
    "ویکتوریا": "YYJ", "victoria": "YYJ", "yyj": "YYJ",
    "همیلتون": "YHM", "hamilton": "YHM", "yhm": "YHM",
    "واترلو": "YKF", "waterloo": "YKF", "ykf": "YKF",
    "لندن کانادا": "YXU", "london": "YXU", "yxu": "YXU",
    "ساسکاتون": "YXE", "saskatoon": "YXE", "yxe": "YXE",
    "رجاینا": "YQR", "regina": "YQR", "yqr": "YQR",

    # ---- Common layovers (often appear in posts) ----
    "استانبول": "IST", "istanbul": "IST", "ist": "IST",
    "صبیحه": "SAW", "sabiha": "SAW", "saw": "SAW",
    "دبی": "DXB", "dubai": "DXB", "dxb": "DXB",
    "دوحه": "DOH", "doha": "DOH", "doh": "DOH",
    "ابوظبی": "AUH", "abu dhabi": "AUH", "auh": "AUH",
    "مسقط": "MCT", "muscat": "MCT", "mct": "MCT",
}

def _norm(s: str) -> str:
    if not s: return ""
    s = s.strip().lower()
    # remove generic words
    s = s.replace("airport", "").replace("intl", "").replace("international", "")
    # drop parentheses content and punctuation
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^\w\u0600-\u06FF\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def to_code(s: str) -> str:
    """Return IATA code or '' if unknown."""
    k = _norm(s)
    return ALIASES.get(k, "")
