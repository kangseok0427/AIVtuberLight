# brain/tools/memory.py
import os
import json
from datetime import datetime
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
load_dotenv()

class MemoryTool:
    def __init__(self):
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
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",  # 70b → 8b로 교체
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=256,  # 512 → 256으로 줄이기
        )

    def _extract_nickname(self, user_input: str) -> str:
        if ": " in user_input:
            return user_input.split(": ")[0].strip()
        return "익명"

    def _get_wiki(self, nickname: str) -> tuple[str, str | None]:
        """시청자 위키 조회 → (내용, doc_id)"""
        try:
            results = self.wiki_db.get(
                where={"nickname": nickname},
                limit=1
            )
            if results and results['documents']:
                doc_id = results['ids'][0] if results['ids'] else None
                return results['documents'][0], doc_id
        except Exception:
            pass
        return "", None

    def _update_wiki(self, nickname: str, user_input: str, answer: str):
        if nickname == "익명":
            return

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
- JSON 형식으로만 출력해
- 새로운 정보가 없으면 빈 JSON {} 출력""")

        human = HumanMessage(content=f"""기존 프로필:
{existing_text if existing_text else "없음"}

새 대화:
시청자: {user_input}
가온: {answer}

위 대화에서 {nickname}에 대한 새로운 정보가 있으면 프로필을 업데이트해서 JSON으로 출력해.
기존 프로필 정보도 포함해서 전체 프로필을 출력해줘.""")

        try:
            response = self.llm.invoke([system, human])
            content = response.content.strip()

            if '{' not in content:
                return

            json_str = content[content.index('{'):content.rindex('}')+1]
            profile = json.loads(json_str)

            if not profile:
                return

            # 기존 위키 삭제 (id로 정확하게)
            if existing_id:
                try:
                    self.wiki_db.delete(ids=[existing_id])
                except Exception as e:
                    print(f"[Wiki] 삭제 실패: {e}")

            # 새 프로필 저장
            profile_text = f"시청자 {nickname} 프로필:\n"
            for k, v in profile.items():
                profile_text += f"- {k}: {v}\n"

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
            print(f"[Wiki] {nickname} 프로필 업데이트 완료")

        except Exception as e:
            print(f"[Wiki] 업데이트 실패: {e}")

    def save(self, user_input: str, answer: str):
        name = os.getenv("VTUBER_NAME", "가온")
        nickname = self._extract_nickname(user_input)

        self.db.add_documents([
            Document(
                page_content=f"시청자: {user_input}\n{name}: {answer}",
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "nickname": nickname,
                    "type": "memory"
                }
            )
        ])

        self._update_wiki(nickname, user_input, answer)

    def build(self):
        wiki_db = self.wiki_db

        @tool
        def memory_search(query: str) -> str:
            """시청자 프로필과 과거 정보를 조회할 때 사용."""
            nickname = query.split(": ")[0].strip() if ": " in query else query
            try:
                wiki_data = wiki_db.get(
                    where={"nickname": nickname},
                    limit=1
                )
                wiki_text = wiki_data['documents'][0] if wiki_data and wiki_data['documents'] else ""
            except Exception:
                wiki_results = wiki_db.similarity_search(query, k=1)
                wiki_text = wiki_results[0].page_content if wiki_results else ""

            if wiki_text:
                return f"[시청자 프로필]\n{wiki_text}"
            return "관련 프로필 정보가 없어요."

        return memory_search