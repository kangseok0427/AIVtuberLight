# brain/tools/code_executor.py
import subprocess
from pathlib import Path
from langchain.tools import tool

WEBINFECTION_ROOT = Path("/Users/lucas/webinfection")


class CodeExecutorTool:
    def build(self):

        @tool
        def code_executor(filename: str) -> str:
            """
            webinfection 게임 파일의 문법을 검증할 때 사용.
            JS 파일은 node로 문법 체크, HTML은 구조 확인.
            filename: 'src/game.js' 처럼 webinfection 루트 기준 상대경로.
            """
            print(f"[CodeExecutor] 호출: '{filename}'")

            target = (WEBINFECTION_ROOT / filename).resolve()

            if not str(target).startswith(str(WEBINFECTION_ROOT.resolve())):
                return f"❌ 허용되지 않은 경로: {filename}"

            if not target.exists():
                return f"❌ 파일 없음: {filename}"

            try:
                if target.suffix == ".js":
                    result = subprocess.run(
                        ["node", "--check", str(target)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        return f"✅ {filename} 문법 이상 없음"
                    else:
                        return f"❌ 문법 오류:\n{result.stderr}"

                elif target.suffix == ".html":
                    content = target.read_text(encoding="utf-8")
                    checks = []
                    if "<!DOCTYPE html>" not in content:
                        checks.append("DOCTYPE 없음")
                    if "<html" not in content:
                        checks.append("<html> 태그 없음")
                    if "<body" not in content:
                        checks.append("<body> 태그 없음")
                    if checks:
                        return f"⚠️ HTML 구조 경고: {', '.join(checks)}"
                    return f"✅ {filename} 구조 이상 없음"

                else:
                    return f"✅ {filename} — 검증 대상 아님 (내용만 저장됨)"

            except subprocess.TimeoutExpired:
                return f"❌ 검증 타임아웃: {filename}"
            except FileNotFoundError:
                return f"❌ node가 설치되어 있지 않음"
            except Exception as e:
                return f"❌ 검증 실패: {e}"

        return code_executor