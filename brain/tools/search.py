# brain/tools/search.py
from langchain.tools import tool
from ddgs import DDGS


class SearchTool:
    def __init__(self, max_results: int = 3):
        self.max_results = max_results

    def build(self):
        max_results = self.max_results

        @tool
        def internet_search(query: str) -> str:
            """인터넷에서 최신 정보를 검색할 때 사용."""
            print(f"[Search] 검색 시작: '{query}'")
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))

                if not results:
                    print(f"[Search] 결과 없음: '{query}'")
                    return "검색 결과가 없어요."

                print(f"[Search] 결과 {len(results)}개: '{query}'")
                return "\n".join(
                    f"- {r['title']}: {r['body']}" for r in results
                )
            except Exception as e:
                print(f"[Search] 검색 실패: '{query}' — {e}")
                return f"검색 실패: {e}"

        return internet_search