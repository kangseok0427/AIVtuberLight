# brain/tools/memory.py
import os
import json
from datetime import datetime
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from brain.llm_config import get_wiki_llm
from dotenv import load_dotenv
load_dotenv()


class MemoryTool:
    def __init__(self):
        print("[Memory] 초기화 시작")

        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.db = Chroma(
            collection_name="gaon_memory",
            embedding_function=self.embeddings,
            persist_directory=".chroma"
        )
        self.wiki_db = Chroma(
            collection_name="gaon_wiki",
            embedding_function=self.embeddings,
            persist_directory=".chroma"
        )
        self.llm = get_wiki_llm()

        # ❸ fix: @tool 함수를 __init__에서 한 번만 생성해서 캐싱
        self._memory_search_tool = self._build_memory_search()

        print(f"[Memory] 초기화 완료 (LLM_MODE: {os.getenv('LLM_MODE', 'groq')})")

    def _extract_nickname(self, user_input: str) -> str:
        """닉네임 추출. 'nickname: message' 형식에서 닉네임만 반환."""
        # split 횟수를 1로 제한해서 닉네임 안에 ": " 있어도 안 잘림
        if ": " in user_input:
            return user_input.split(": ", 1)[0].strip()
        print(f"[Memory] 닉네임 추출 실패 — 익명 처리: '{user_input[:30]}'")
        return "익명"

    def _get_wiki(self, nickname: str) -> tuple[str, str | None]:
        """Wiki DB에서 닉네임으로 프로필 조회. (프로필 텍스트, doc_id) 반환."""
        print(f"[Memory] Wiki 조회: {nickname}")
        try:
            # ❶ fix: .get()은 limit 파라미터 미지원 → 제거 후 [0]으로 첫 번째만 사용
            results = self.wiki_db.get(
                where={"nickname": nickname}
            )
            if results and results['documents']:
                doc_id = results['ids'][0] if results['ids'] else None
                print(f"[Memory] Wiki 조회 성공: {nickname}")
                return results['documents'][0], doc_id
            print(f"[Memory] Wiki 없음: {nickname}")
        except Exception as e:
            print(f"[Memory] Wiki 조회 실패: {nickname} — {e}")
        return "", None

    def _update_wiki(self, nickname: str, user_input: str, answer: str):
        """대화를 LLM으로 분석해서 시청자 프로필(Wiki)을 업데이트."""
        if nickname == "익명":
            print("[Memory] 익명 유저 — Wiki 업데이트 스킵")
            return

        print(f"[Memory] Wiki 업데이트 시작: {nickname}")
        existing_text, existing_id = self._get_wiki(nickname)

        system = SystemMessage(content="""너는 시청자 프로필을 관리하는 AI야.
대화를 분석해서 시청자에 대한 중요한 정보를 추출하고 프로필을 업데이트해.

추출할 정보 예시:
- 거주지, 직업, 전공
- 취미, 관심사
- 키우는 동물
- 자주 언급하는 것들
- 성격이나 특징

규칙:
- 확실한 정보만 저장해
- 기존 프로필과 충돌하면 최신 정보 우선
- JSON 형식으로만 출력해. 앞뒤 설명 없이 JSON만.
- 마크다운 코드블록(```) 사용 금지
- 새로운 정보가 없으면 빈 JSON {} 출력""")

        human = HumanMessage(content=f"""기존 프로필:
{existing_text if existing_text else "없음"}

새 대화:
시청자: {user_input}
가온: {answer}

위 대화에서 {nickname}에 대한 새로운 정보가 있으면 프로필을 업데이트해서 JSON으로 출력해.
기존 프로필 정보도 포함해서 전체 프로필을 출력해줘.""")

        try:
            print(f"[Memory] LLM 호출 시작: {nickname}")
            response = self.llm.invoke([system, human])
            print(f"[Memory] LLM 호출 완료: {nickname}")
            content = response.content.strip()

            if '{' not in content:
                print(f"[Memory] JSON 없음 — Wiki 업데이트 스킵: {nickname}")
                return

            # 코드블록 제거
            content = content.replace("```json", "").replace("```", "").strip()

            # { } 사이만 추출
            try:
                start = content.index('{')
                end   = content.rindex('}') + 1
            except ValueError:
                print(f"[Memory] JSON 구조 파싱 실패 — 스킵: {nickname}")
                return

            json_str = content[start:end]

            try:
                profile = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"[Memory] JSON 파싱 실패: {nickname} — {e}")
                return

            if not profile:
                print(f"[Memory] 새 정보 없음 — Wiki 업데이트 스킵: {nickname}")
                return

            # 기존 프로필 삭제
            if existing_id:
                try:
                    self.wiki_db.delete(ids=[existing_id])
                    print(f"[Memory] 기존 Wiki 삭제 완료: {nickname}")
                except Exception as e:
                    print(f"[Memory] 기존 Wiki 삭제 실패: {nickname} — {e}")

            # 새 프로필 저장
            profile_text = f"시청자 {nickname} 프로필:\n"
            for k, v in profile.items():
                profile_text += f"- {k}: {v}\n"

            try:
                self.wiki_db.add_documents([
                    Document(
                        page_content=profile_text,
                        metadata={
                            "nickname": nickname,
                            "updated": datetime.now().isoformat(),
                            "type": "wiki"
                        }
                    )
                ])
                print(f"[Memory] Wiki 업데이트 완료: {nickname}\n{profile_text}")
            except Exception as e:
                print(f"[Memory] Wiki 저장 실패: {nickname} — {e}")

        except Exception as e:
            print(f"[Memory] LLM 호출 실패: {nickname} — {e}")

    def save(self, user_input: str, answer: str):
        """대화를 단기 메모리에 저장하고, Wiki(장기 메모리)를 업데이트."""
        name     = os.getenv("VTUBER_NAME", "가온")
        nickname = self._extract_nickname(user_input)
        print(f"[Memory] 대화 저장: {nickname}")

        try:
            self.db.add_documents([
                Document(
                    page_content=f"시청자: {user_input}\n{name}: {answer}",
                    metadata={
                        "timestamp": datetime.now().isoformat(),
                        "nickname":  nickname,
                        "type":      "memory"
                    }
                )
            ])
            print(f"[Memory] 단기 메모리 저장 완료: {nickname}")
        except Exception as e:
            print(f"[Memory] 단기 메모리 저장 실패: {nickname} — {e}")
            # ❹ fix: 단기 저장 실패 시 Wiki 업데이트도 스킵 (의도된 설계 — 대화 없이 프로필만 업데이트되는 상황 방지)
            return

        self._update_wiki(nickname, user_input, answer)

    def _build_memory_search(self):
        """
        ❸ fix: @tool 함수를 __init__에서 한 번만 빌드해서 캐싱.
        build()를 여러 번 호출해도 같은 툴 객체를 재사용함.
        """
        db      = self.db
        wiki_db = self.wiki_db

        # ❺ fix: 닉네임 추출을 _extract_nickname()으로 위임 (인라인 중복 제거)
        extract_nickname = self._extract_nickname

        @tool
        def memory_search(query: str) -> str:
            """시청자 프로필과 과거 대화 정보를 조회할 때 사용."""
            # ❺ fix: 인라인 split 로직 제거 → _extract_nickname() 재사용
            nickname = extract_nickname(query)
            print(f"[Memory] memory_search 호출: '{query}' → 닉네임: '{nickname}'")

            result_parts = []

            # 1. Wiki (장기 메모리) — 메타데이터 정확 매칭
            try:
                # ❶ fix: limit 파라미터 제거
                wiki_data = wiki_db.get(
                    where={"nickname": nickname}
                )
                if wiki_data and wiki_data['documents']:
                    print(f"[Memory] Wiki 조회 성공: {nickname}")
                    result_parts.append(f"[시청자 프로필]\n{wiki_data['documents'][0]}")
                else:
                    print(f"[Memory] Wiki 없음: {nickname}")
            except Exception as e:
                print(f"[Memory] Wiki 조회 실패: {nickname} — {e}")

            # 2. 단기 메모리 — 유사도 검색
            try:
                recent = db.similarity_search(
                    query,
                    k=5,
                    filter={"nickname": nickname}
                )
                if recent:
                    recent_text = "\n---\n".join([r.page_content for r in recent])
                    print(f"[Memory] 단기 메모리 {len(recent)}개 조회 성공: {nickname}")
                    result_parts.append(f"[최근 대화]\n{recent_text}")
                else:
                    print(f"[Memory] 단기 메모리 없음: {nickname}")
            except Exception as e:
                print(f"[Memory] 단기 메모리 조회 실패: {nickname} — {e}")

            if result_parts:
                return "\n\n".join(result_parts)
            return "관련 정보가 없어요."

        return memory_search

    def build(self):
        """캐싱된 memory_search 툴 반환."""
        return self._memory_search_tool