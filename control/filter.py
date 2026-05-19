# control/filter.py
import re

FILTER_PATTERNS = [
    r"[시씨][0이발팔ㅂ]",
    r"[ㅅs][ㅣi][0o][ㅂb]",
    r"ㅅㅂ|ㅄ|ㄱㅅ|ㅈㄹ|ㄷㅊ",
    r"좆|보지|씹|잡년|창녀",
    r"(.)\1{4,}",
    r"https?://\S+\.(xyz|tk|ml|ga|cf)",
    r"ㅈㄴ|ㅈ같|ㄲㅈ|ㅂㅅ",
    r"tlqkf|shiba|siba",
    r"걸레|보빨|찐따|병신|뇨석|느금",
    r"bshin",
    r"[시씨ㅅ][.\-_\s*1!|][발바ㅂ]",
]

COMPILED_FILTERS = [re.compile(p, re.IGNORECASE) for p in FILTER_PATTERNS]

def check_chat(username: str, text: str) -> str | None:
    for pattern in COMPILED_FILTERS:
        m = pattern.search(text)
        if m:
            return f"패턴 매칭: `{m.group()}`"
    return None