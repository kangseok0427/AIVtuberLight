# control/filter.py
import re

FILTER_PATTERNS = [
    (r"[시씨][0이발팔ㅂ]",              "욕설 변형 (시발 류)"),
    (r"[ㅅs][ㅣi][0o][ㅂb]",           "욕설 변형 (알파벳 혼용)"),
    (r"ㅅㅂ|ㅄ|ㄱㅅ|ㅈㄹ|ㄷㅊ",        "초성 욕설"),
    (r"좆|보지|씹|잡년|창녀",           "직접 욕설"),
    (r"(.)\1{4,}",                      "도배 (같은 문자 4회 이상 반복)"),
    (r"https?://\S+\.(xyz|tk|ml|ga|cf)","스팸 링크 (의심 도메인)"),
    (r"ㅈㄴ|ㅈ같|ㄲㅈ|ㅂㅅ",           "초성 욕설 2"),
    (r"tlqkf|shiba|siba",              "욕설 로마자 변형"),
    (r"걸레|보빨|찐따|병신|뇨석|느금",  "비하 표현"),
    (r"bshin",                          "병신 로마자 변형"),
    (r"[시씨ㅅ][.\-_\s*1!|][발바ㅂ]",  "욕설 특수문자 혼용"),
]

COMPILED_FILTERS = [
    (re.compile(p, re.IGNORECASE), desc)
    for p, desc in FILTER_PATTERNS
]

def check_chat(username: str, text: str) -> str | None:
    for pattern, desc in COMPILED_FILTERS:
        m = pattern.search(text)
        if m:
            return f"[필터] {desc} — 매칭: `{m.group()}`"
    return None