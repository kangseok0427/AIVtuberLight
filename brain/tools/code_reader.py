# brain/tools/code_reader.py
import os
from pathlib import Path
from langchain.tools import tool

# 제외 목록 — IGNORE_DIRS에 통합
IGNORE_DIRS = {
    ".git", "__pycache__", ".chroma",
    "node_modules", ".conda", "prompts"
}
IGNORE_FILES      = {".env", ".gitignore", ".DS_Store"}
IGNORE_EXTENSIONS = {".pyc", ".pyo", ".png", ".jpg", ".mp3", ".wav"}

PROJECT_ROOT = Path(__file__).parent.parent.parent  # ai-vtuber/


def _collect_files() -> dict[str, str]:
    """프로젝트 파일 전체 수집 → {상대경로: 내용}"""
    files = {}
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        # 제외 디렉토리 — 경로 어딘가에 포함되면 스킵
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        # 제외 파일명 / 확장자
        if path.name in IGNORE_FILES:
            continue
        if path.suffix in IGNORE_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8")
            rel = str(path.relative_to(PROJECT_ROOT))
            files[rel] = content
        except Exception as e:
            print(f"[CodeReader] 파일 읽기 실패: {path} — {e}")
            continue

    print(f"[CodeReader] 총 {len(files)}개 파일 수집 완료")
    return files


class CodeReaderTool:
    def build(self):

        @tool
        def code_reader(query: str) -> str:
            """
            가온이 자신의 코드 구조나 작동 방식을 설명할 때 사용.
            시청자가 '너 어떻게 만들어졌어?', '이 기능 어떻게 돼?' 같은 질문을 할 때 호출.
            """
            print(f"[CodeReader] 호출: '{query}'")
            files = _collect_files()

            if not files:
                return "코드 파일을 찾을 수 없어."

            # 키워드로 관련 파일 필터링
            keywords = query.lower().split()
            relevant = {}
            for rel, content in files.items():
                # 경로 매칭은 2점, 내용 매칭은 등장 횟수만큼 점수
                path_score    = sum(kw in rel.lower() for kw in keywords) * 2
                content_score = sum(content.lower().count(kw) for kw in keywords)
                score = path_score + content_score
                if score > 0:
                    relevant[rel] = (score, content)

            # 관련 파일 없으면 구조만 반환
            if not relevant:
                structure = "\n".join(files.keys())
                print(f"[CodeReader] 관련 파일 없음 — 구조 반환")
                return f"[프로젝트 구조]\n{structure}"

            # 점수 높은 파일 최대 2개만
            top = sorted(relevant.items(), key=lambda x: x[1][0], reverse=True)[:2]
            print(f"[CodeReader] 반환 파일: {[rel for rel, _ in top]}")

            result = ""
            for rel, (_, content) in top:
                lines   = content.splitlines()
                preview = "\n".join(lines[:100])
                if len(lines) > 100:
                    preview += f"\n... (총 {len(lines)}줄)"
                result += f"\n[{rel}]\n{preview}\n"

            return result.strip()

        return code_reader