# brain/tools/eternal_return.py
import os
import re
import time
import httpx
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

ER_API_KEY     = os.getenv("ER_API_KEY")
ER_BASE_URL    = "https://open-api.bser.io/v1"
HEADERS        = {"x-api-key": ER_API_KEY}
CURRENT_SEASON = 9  # 공개 시즌 번호 (API ID = 17)

def _to_api_id(season: int) -> int:
    return season * 2 - 1

def _get(endpoint: str) -> dict:
    time.sleep(1.1)
    with httpx.Client(timeout=10) as client:
        return client.get(f"{ER_BASE_URL}{endpoint}", headers=HEADERS).json()

def _get_user_id(nickname: str) -> str | None:
    data = _get(f"/user/nickname?query={nickname}")
    return data["user"]["userId"] if data.get("code") == 200 else None

def _parse_season(query: str) -> int:
    m = re.search(r'(\d+)\s*시즌', query)
    return int(m.group(1)) if m else CURRENT_SEASON

def _parse_nickname(query: str) -> str:
    m = re.search(r'["\'](.+?)["\']', query)
    return m.group(1) if m else query.split()[0]

def build_eternal_return_tool():

    @tool
    def eternal_return_search(query: str) -> str:
        """
        이터널리턴 관련 정보 조회. 유저 랭크, 탑 랭커 조회 시 사용.
        query 예시:
        - '니키의땀찬스패츠 랭크'
        - '니키의땀찬스패츠 3시즌 랭크'
        - '솔로 탑랭커'
        - '9시즌 듀오 탑랭커'
        """
        try:
            q        = query.lower()
            season   = _parse_season(query)
            api_id   = _to_api_id(season)
            mode     = 2 if "듀오" in q else (3 if "스쿼드" in q else 1)
            mode_str = {1: "솔로", 2: "듀오", 3: "스쿼드"}[mode]

            # 탑 랭커
            if "탑" in q or "랭킹" in q or "top" in q or "1등" in q or "순위" in q:
                data = _get(f"/rank/top/{api_id}/{mode}")
                if data.get("code") != 200:
                    return f"탑 랭커 조회 실패: {data.get('message')}"
                tops   = data.get("topRanks", [])[:5]
                result = f"{season}시즌 {mode_str} TOP {len(tops)}:\n"
                for r in tops:
                    result += f"- {r['rank']}위: {r['nickname']} (MMR: {r['mmr']})\n"
                return result

            # 유저 랭크
            nickname = _parse_nickname(query)
            user_id  = _get_user_id(nickname)
            if not user_id:
                return f"유저 '{nickname}'를 찾을 수 없어요."

            data = _get(f"/rank/uid/{user_id}/{api_id}/{mode}")
            if data.get("code") != 200:
                return f"랭크 조회 실패: {data.get('message')}"

            r    = data.get("userRank", {})
            mmr  = r.get("mmr", 0)
            rank = r.get("rank", 0)

            if mmr == 0 and rank == 0:
                return f"{nickname}님은 {season}시즌 {mode_str} 랭크 기록이 없어요."

            return f"{nickname} {season}시즌 {mode_str} 랭크: {rank}위 / MMR: {mmr}"

        except Exception as e:
            return f"이터널리턴 API 오류: {e}"

    return eternal_return_search