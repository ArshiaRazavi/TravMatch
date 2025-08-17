# city_map.py
ALIASES = {
    # Tehran
    "تهران": "THR", "طهران": "THR", "ika": "IKA", "imam": "IKA", "imam khomeini": "IKA",
    "tehran": "THR", "thr": "THR", "ika (imam)": "IKA",
    # Toronto
    "تورنتو": "YYZ", "toronto": "YYZ", "yyz": "YYZ", "pearson": "YYZ",
    # Vancouver
    "ونکوور": "YVR", "vancouver": "YVR", "yvr": "YVR",
    # Montreal
    "مونترال": "YUL", "montreal": "YUL", "yul": "YUL",
    # add more as you see them
}

def to_code(s: str) -> str:
    if not s: return ""
    k = s.strip().lower()
    return ALIASES.get(k, "")
