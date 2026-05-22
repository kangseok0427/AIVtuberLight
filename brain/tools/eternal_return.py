# brain/tools/eternal_return.py
import os
import httpx
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

ER_API_KEY  = os.getenv("ER_API_KEY")
ER_BASE_URL = "https://open-api.eternalreturn.io/open-api"
HEADERS     = {"x-api-key": ER_API_KEY}

async def _get(endpoint: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{ER_BASE_URL}{endpoint}", headers=HEADERS)
        return resp.json()

def _get_sync(endpoint: str) -> dict:
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{ER_BASE_URL}{endpoint}", headers=HEADERS)
        return resp.json()

def build_eternal_return_tool():

    @tool
    def eternal_return_search(query: str) -> str:
        """
        이터널리턴 관련 정보를 조회할 때 사용.
        시청자가 캐릭터 정보, 아이템, 매치 결과, 랭킹 등을 물어볼 때 호출.
        query 예시: '매그너스 정보', '내 최근 매치', '현재 랭킹'
        """
        try:
            q = query.lower()

            # 유저 닉네임으로 매치 조회
            if "매치" in q or "전적" in q or "결과" in q:
                # 쿼리에서 닉네임 추출 (예: "가온0033 전적")
                words = query.split()
                nickname = words[0] if len(words) > 1 else ""
                if not nickname:
                    return "닉네임을 함께 알려줘! 예: '가온0033 전적'"

                # 유저 번호 조회
                user_data = _get_sync(f"/v1/user/nickname?nickname={nickname}")
                if user_data.get("code") != 200:
                    return f"유저 {nickname}를 찾을 수 없어요."
                user_num = user_data["user"]["userNum"]

                # 최근 매치 조회
                match_data = _get_sync(f"/v1/user/games/{user_num}")
                if match_data.get("code") != 200:
                    return "매치 데이터를 가져올 수 없어요."

                games = match_data.get("userGames", [])[:3]
                if not games:
                    return "최근 매치 기록이 없어요."

                result = f"{nickname} 최근 매치:\n"
                for g in games:
                    result += (
                        f"- 캐릭터: {g.get('characterNum')} "
                        f"| 순위: {g.get('gameRank')}등 "
                        f"| 킬: {g.get('playerKill')} "
                        f"| 데미지: {g.get('damageToPlayer')}\n"
                    )
                return result

            # 랭킹 조회
            elif "랭킹" in q or "랭크" in q or "순위" in q:
                rank_data = _get_sync("/v1/rank/top?seasonId=0&matchingTeamMode=1")
                if rank_data.get("code") != 200:
                    return "랭킹 데이터를 가져올 수 없어요."
                tops = rank_data.get("topRanks", [])[:5]
                result = "현재 솔로 랭킹 TOP 5:\n"
                for r in tops:
                    result += f"- {r.get('rank')}위: {r.get('nickname')} (MMR: {r.get('mmr')})\n"
                return result

            # 캐릭터/게임 메타 데이터
            elif "캐릭터" in q or "메타" in q or "픽률" in q:
                meta_data = _get_sync("/v1/data/Character")
                if meta_data.get("code") != 200:
                    return "캐릭터 데이터를 가져올 수 없어요."
                chars = meta_data.get("data", [])
                # 쿼리에 특정 캐릭터 이름 있으면 필터
                names = [c.get("name", {}).get("Korean", "") for c in chars]
                matched = [n for n in names if any(kw in q for kw in [n.lower(), n])]
                if matched:
                    return f"캐릭터 검색 결과: {', '.join(matched[:5])}"
                return f"전체 캐릭터 수: {len(chars)}명"

            else:
                return "매치 전적, 랭킹, 캐릭터 정보를 물어봐줘!"

        except Exception as e:
            return f"이터널리턴 API 오류: {e}"

    return eternal_return_search