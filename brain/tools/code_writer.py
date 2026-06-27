# brain/tools/code_writer.py
from pathlib import Path
from langchain.tools import tool

WEBINFECTION_ROOT = Path("/Users/lucas/webinfection")
ALLOWED_EXTENSIONS = {".html", ".js", ".css", ".md", ".json"}


class CodeWriterTool:
    def build(self):

        @tool
        def code_writer(filename: str, content: str = "", delete: bool = False) -> str:
            """
            webinfection 게임 파일을 생성/수정/삭제할 때 사용.
            filename: 'src/index.html' 처럼 webinfection 루트 기준 상대경로.
            content: 파일 전체 내용. delete가 True면 비워도 됨.
            delete: True면 파일 삭제.
            """
            print(f"[CodeWriter] 호출: '{filename}' delete={delete}")

            target = (WEBINFECTION_ROOT / filename).resolve()

            if not str(target).startswith(str(WEBINFECTION_ROOT.resolve())):
                return f"❌ 허용되지 않은 경로: {filename}"

            if target.suffix not in ALLOWED_EXTENSIONS:
                return f"❌ 허용되지 않은 확장자: {target.suffix}"

            try:
                if delete:
                    if not target.exists():
                        return f"⚠️ 파일 없음: {filename}"
                    target.unlink()
                    print(f"[CodeWriter] 삭제 완료: {filename}")
                    return f"✅ {filename} 삭제 완료"
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                    lines = len(content.splitlines())
                    print(f"[CodeWriter] 저장 완료: {filename} ({lines}줄)")
                    return f"✅ {filename} 저장 완료 ({lines}줄)"
            except Exception as e:
                print(f"[CodeWriter] 실패: {e}")
                return f"❌ 실패: {e}"

        return code_writer