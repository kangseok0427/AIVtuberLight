# brain/tools/memory.py
import os
from datetime import datetime
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
load_dotenv()

class MemoryTool:
    def __init__(self, collection: str = "gaon_memory"):
        self.collection = collection
        self.embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.db = Chroma(
            collection_name=self.collection,
            embedding_function=self.embeddings,
            persist_directory=".chroma"
        )

    def save(self, user_input: str, answer: str):
        name = os.getenv("VTUBER_NAME", "가온")
        self.db.add_documents([
            Document(
                page_content=f"시청자: {user_input}\n{name}: {answer}",
                metadata={"timestamp": datetime.now().isoformat()}
            )
        ])

    def build(self):
        db = self.db

        @tool
        def memory_search(query: str) -> str:
            """과거 대화 기록에서 관련 맥락을 찾을 때 사용."""
            results = db.similarity_search(query, k=3)
            if not results:
                return "관련 대화 기록이 없어요."
            return "\n".join(
                f"- [{r.metadata.get('timestamp', '')}] {r.page_content}"
                for r in results
            )

        return memory_search