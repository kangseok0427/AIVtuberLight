# brain/tools/code_reader.py
import os
from pathlib import Path
from langchain.tools import tool

IGNORE_DIRS = {
    ".git", "__pycache__", ".chroma",
    "node_modules", ".conda", "prompts"
}
IGNORE_FILES      = {".env", ".gitignore", ".DS_Store"}
IGNORE_EXTENSIONS = {".pyc", ".pyo", ".png", ".jpg", ".mp3", ".wav"}

PROJECT_ROOT      = Path(__file__).parent.parent.parent
WEBINFECTION_ROOT = Path("/Users/lucas/webinfection")


def _get_tree(root: Path, indent: int = 0) -> str:
    result = ""
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
        for entry in entries:
            if entry.name in IGNORE_DIRS or entry.name in IGNORE_FILES:
                continue
            prefix = "  " * indent + ("📄 " if entry.is_file() else "📁 ")
            result += f"{prefix}{entry.name}\n"
            if entry.is_dir() and entry.name not in IGNORE_DIRS:
                result += _get_tree(entry, indent + 1)
    except Exception:
        pass
    return result


def _collect_files(root: Path) -> dict[str, str]:
    files = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.name in IGNORE_FILES:
            continue
        if path.suffix in IGNORE_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8")
            rel     = str(path.relative_to(root))
            files[rel] = content
        except Exception as e:
            print(f"[CodeReader] 파일 읽기 실패: {path} — {e}")
    print(f"[CodeReader] 총 {len(files)}개 파일 수집 완료")
    return files


class CodeReaderTool:
    def build(self):

        @tool
        def code_reader(query: str) -> str:
            """
            가온이 자신의 코드 구조나 작동 방식, 또는 webinfection 게임 현재 코드를 확인할 때 사용.
            webinfection 코드 작업 전 반드시 호출해서 현재 코드 파악할 것.
            'webinfection', 'game.js', '게임 코드', '현재 파일' 키워드가 포함되면 webinfection 우선 탐색.
            """
            print(f"[CodeReader] 호출: '{query}'")

            wi_keywords = ["webinfection", "game.js", "게임 코드", "현재 파일", "게임 파일", "index.html"]
            is_wi = any(kw in query.lower() for kw in wi_keywords)

            # webinfection 쿼리면 game.js 우선 반환
            if is_wi:
                priority = ["src/game.js", "src/index.html", "src/style.css"]
                result = ""
                for p in priority:
                    target = WEBINFECTION_ROOT / p
                    if target.exists():
                        try:
                            content = target.read_text(encoding="utf-8")
                            lines   = content.splitlines()
                            preview = "\n".join(lines[:150])
                            if len(lines) > 150:
                                preview += f"\n... (총 {len(lines)}줄)"
                            result += f"\n[{p}]\n{preview}\n"
                        except Exception as e:
                            print(f"[CodeReader] 읽기 실패: {p} — {e}")
                print(f"[CodeReader] webinfection 파일 반환")
                return result.strip() if result else "webinfection 파일 없음"

            # 가온이 프로젝트
            root  = PROJECT_ROOT
            files = _collect_files(root)

            if not files:
                tree = _get_tree(root)
                return f"[디렉토리 구조]\n{tree}"

            if any(kw in query.lower() for kw in ["구조", "파일 목록", "tree", "어떻게 생겼"]):
                tree = _get_tree(root)
                return f"[가온이 프로젝트 구조]\n{tree}"

            keywords = query.lower().split()
            relevant = {}
            for rel, content in files.items():
                path_score    = sum(kw in rel.lower() for kw in keywords) * 2
                content_score = sum(content.lower().count(kw) for kw in keywords)
                score = path_score + content_score
                if score > 0:
                    relevant[rel] = (score, content)

            if not relevant:
                tree = _get_tree(root)
                return f"[프로젝트 구조]\n{tree}"

            top = sorted(relevant.items(), key=lambda x: x[1][0], reverse=True)[:2]
            print(f"[CodeReader] 반환 파일: {[rel for rel, _ in top]}")

            result = ""
            for rel, (_, content) in top:
                lines   = content.splitlines()
                preview = "\n".join(lines[:50])
                if len(lines) > 50:
                    preview += f"\n... (총 {len(lines)}줄)"
                result += f"\n[{rel}]\n{preview}\n"

            return result.strip()

        return code_reader