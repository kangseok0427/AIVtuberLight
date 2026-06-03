# brain/tools/eternal_return.py
import os
import re
import asyncio
import httpx
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

ER_API_KEY  = os.getenv("ER_API_KEY")
ER_BASE_URL = "https://open-api.bser.io/v1"
HEADERS     = {"x-api-key": ER_API_KEY}

# 시작 시 한 번만 조회 후 캐싱 — None이면 아직 조회 안 한 것
_cached_season: int | None = None


async def _get(endpoint: str) -> dict:
    await asyncio.sleep(1.1)  # 레이트 리밋 — 비동기 sleep으로 이벤트 루프 안 막음
    print(f"[ER] API 요청: {endpoint}")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{ER_BASE_URL}{endpoint}", headers=HEADERS)
        data = resp.json()
        print(f"[ER] API 응답 코드: {data.get('code')} — {endpoint}")
        return data


async def get_current_season() -> int:
    """
    현재 시즌을 자동으로 찾아서 캐싱.
    탑랭커 API를 높은 시즌 번호부터 내려가며 데이터 있는 시즌 = 현재 시즌으로 판단.
    """
    global _cached_season
    if _cached_season is not None:
        print(f"[ER] 캐시된 시즌 사용: {_cached_season}")
        return _cached_season

    print("[ER] 현재 시즌 자동 탐색 시작...")
    for season in range(30, 0, -1):
        data = await _get(f"/rank/top/{season}/1")
        if data.get("code") == 200 and data.get("topRanks"):
            _cached_season = season
            print(f"[ER] 현재 시즌 탐색 완료: {season}")
            return season

    print("[ER] 시즌 탐색 실패 — fallback: 9")
    _cached_season = 9
    return 9


async def _get_user_id(nickname: str) -> str | None:
    data = await _get(f"/user/nickname?query={nickname}")
    if data.get("code") == 200:
        return data["user"]["userId"]
    print(f"[ER] 유저 조회 실패: '{nickname}' — {data.get('message')}")
    return None


def _parse_season(query: str) -> int | None:
    """쿼리에서 시즌 번호 추출. 없으면 None 반환 → 현재 시즌 자동 사용."""
    m = re.search(r'(\d+)\s*시즌', query)
    return int(m.group(1)) if m else None


def _parse_nickname(query: str) -> str:
    # 따옴표 안에 있으면 그걸 닉네임으로
    m = re.search(r'["\'](.+?)["\']', query)
    if m:
        return m.group(1)

    # 시즌 표현 / 모드 키워드 / 랭크 키워드 제거 후 첫 단어
    cleaned = re.sub(r'\d+\s*시즌', '', query)
    cleaned = re.sub(r'솔로|듀오|스쿼드|랭크|랭킹|탑|순위|top|1등', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return cleaned.split()[0] if cleaned.split() else query.split()[0]


async def _eternal_return_async(query: str) -> str:
    try:
        q        = query.lower()
        mode     = 2 if "듀오" in q else (3 if "스쿼드" in q else 1)
        mode_str = {1: "솔로", 2: "듀오", 3: "스쿼드"}[mode]

        # 시즌 — 쿼리에 명시 없으면 자동 탐색
        parsed_season = _parse_season(query)
        season = parsed_season if parsed_season is not None else await get_current_season()

        print(f"[ER] 검색 시작 — 시즌: {season} / 모드: {mode_str} / 쿼리: '{query}'")

        # 탑 랭커
        if "탑" in q or "랭킹" in q or "top" in q or "1등" in q or "순위" in q:
            data = await _get(f"/rank/top/{season}/{mode}")
            if data.get("code") != 200:
                return f"탑 랭커 조회 실패: {data.get('message')}"
            tops   = data.get("topRanks", [])[:5]
            result = f"{season}시즌 {mode_str} TOP {len(tops)}:\n"
            for r in tops:
                result += f"- {r['rank']}위: {r['nickname']} (MMR: {r['mmr']})\n"
            print(f"[ER] 탑랭커 조회 완료: {season}시즌 {mode_str}")
            return result

        # 유저 랭크
        nickname = _parse_nickname(query)
        print(f"[ER] 유저 랭크 조회: '{nickname}'")
        user_id = await _get_user_id(nickname)
        if not user_id:
            return f"유저 '{nickname}'를 찾을 수 없어요."

        data = await _get(f"/rank/uid/{user_id}/{season}/{mode}")
        if data.get("code") != 200:
            return f"랭크 조회 실패: {data.get('message')}"

        r    = data.get("userRank", {})
        mmr  = r.get("mmr", 0)
        rank = r.get("rank", 0)

        if mmr == 0 and rank == 0:
            return f"{nickname}님은 {season}시즌 {mode_str} 랭크 기록이 없어요."

        print(f"[ER] 유저 랭크 조회 완료: {nickname} {rank}위 MMR {mmr}")
        return f"{nickname} {season}시즌 {mode_str} 랭크: {rank}위 / MMR: {mmr}"

    except Exception as e:
        print(f"[ER] API 오류: {e}")
        return f"이터널리턴 API 오류: {e}"


class EternalReturnTool:
    def build(self):

        @tool
        def eternal_return_search(query: str) -> str:
            """
            이터널리턴 관련 정보 조회. 유저 랭크, 탑 랭커 조회 시 사용.
            query 예시:
            - '니키의땀찬스패츠 랭크'
            - '니키의땀찬스패츠 3시즌 랭크'
            - '솔로 탑랭커'
            - '듀오 탑랭커'
            """
            return asyncio.get_event_loop().run_until_complete(_eternal_return_async(query))

        return eternal_return_search