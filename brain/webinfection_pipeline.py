# brain/webinfection_pipeline.py
import os
import re
import json
import subprocess
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from brain.llm_config import get_code_llm
from brain.tools.code_writer import CodeWriterTool
from brain.tools.code_executor import CodeExecutorTool
from ipc.notifier import notify

WEBINFECTION_ROOT = Path("/Users/lucas/webinfection")

llm_code           = get_code_llm()
code_writer_tool   = CodeWriterTool()
code_executor_tool = CodeExecutorTool()


def _read_files() -> str:
    result  = ""
    src_dir = WEBINFECTION_ROOT / "src"
    if src_dir.exists():
        for f in sorted(src_dir.rglob("*")):
            if f.is_file() and f.suffix in {".html", ".js", ".css", ".svg"}:
                rel     = str(f.relative_to(WEBINFECTION_ROOT))
                content = f.read_text(encoding="utf-8")
                lines   = content.splitlines()
                preview = "\n".join(lines[:80])
                if len(lines) > 80:
                    preview += f"\n... (총 {len(lines)}줄)"
                result += f"\n[{rel}]\n{preview}\n"
    return result.strip()


def _get_fallback_llm():
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=os.getenv("OLLAMA_ANSWER_MODEL"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
        temperature=0.2,
        num_predict=8000,
    )


def _escape_json_strings(s: str) -> str:
    result    = []
    in_string = False
    i         = 0
    while i < len(s):
        c = s[i]
        if c == '"' and (i == 0 or s[i-1] != '\\'):
            in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\t':
            result.append('\\t')
        elif in_string and c == '\r':
            result.append('\\r')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def _parse_json(content: str) -> dict:
    try:
        start = content.index('{')
        end   = content.rindex('}') + 1
        raw   = _escape_json_strings(content[start:end])
        return json.loads(raw)
    except Exception as e:
        print(f"[Pipeline] JSON 파싱 실패: {e}")
        print(f"[Pipeline] LLM 원본 응답: {content[:200]}")
        return {}


def _generate_code(user_request: str, current_code: str) -> dict | str:
    system = SystemMessage(content="""너는 webinfection 웹게임 개발자야.
현재 게임 코드를 보고 사용자 요청에 맞게 수정하거나 기능을 추가해줘.

규칙:
- 반드시 JSON 형식으로만 응답. 마크다운 코드블록 사용 금지.
- 수정/생성할 파일: {"파일경로": "전체 내용"} 형식
- 삭제할 파일: {"파일경로": "__DELETE__"} 형식
- 예시: {"src/game.js": "__DELETE__", "src/core.js": "전체 코드 내용"}
- 변경 없는 파일은 포함하지 마.
- 코드에 생각 과정 절대 포함하지 마. 순수 코드만.
- 문자열 안에 줄바꿈은 \\n으로 이스케이프해서 유효한 JSON을 반환해.""")

    human = HumanMessage(content=f"""현재 코드:
{current_code}

요청: {user_request}

수정된 파일을 JSON으로 반환해줘.""")

    try:
        response = llm_code.invoke([system, human])

    except RuntimeError as e:
        if "ALL_MODELS_EXHAUSTED" in str(e):
            print(f"[Pipeline] 모든 모델 한도 초과")
            return "아.. 지금 내 두뇌가 완전히 방전됐어 😔 잠깐 쉬고 나서 다시 시도해줘 💜 [EMOTION:sad]"
        raise

    except Exception as e:
        err = str(e)
        if "Please try again in" in err:
            match     = re.search(r'Please try again in (.+?)\.', err)
            wait_time = match.group(1) if match else "잠시"
            print(f"[Pipeline] groq 한도 초과 — {wait_time} 후 재시도, ollama 폴백")
            try:
                response = _get_fallback_llm().invoke([system, human])
            except Exception as e2:
                print(f"[Pipeline] ollama도 실패: {e2}")
                return f"지금 AI 두뇌가 좀 과부하 상태야.. {wait_time} 후에 다시 시도해줘 💜 [EMOTION:nervous]"
        else:
            print(f"[Pipeline] 실패: {e} — ollama 폴백")
            try:
                response = _get_fallback_llm().invoke([system, human])
            except Exception as e2:
                print(f"[Pipeline] ollama도 실패: {e2}")
                return "코드 생성 실패했어.. 잠깐 후에 다시 시도해줘 💜 [EMOTION:sad]"

    content = response.content.strip()
    content = content.replace("```json", "").replace("```", "").strip()
    return _parse_json(content) or {}


def _sanity_check(files: dict) -> list[str]:
    issues = []
    for filename, content in files.items():
        if content == "__DELETE__":
            continue
        lines = content.strip().splitlines()
        if len(lines) <= 1:
            issues.append(f"{filename}: 너무 짧음 ({len(lines)}줄)")
        if len(content.strip()) < 50:
            issues.append(f"{filename}: 내용 너무 적음")
    return issues


def _llm_review(files: dict, user_request: str) -> list[str]:
    review_content = "\n".join(
        f"[{f}]\n{c[:500]}" for f, c in files.items() if c != "__DELETE__"
    )
    system = SystemMessage(content="""너는 웹게임 코드 리뷰어야.
코드에 심각한 문제가 있는지만 체크해.

심각한 문제:
- 명백한 문법 오류
- canvas나 ctx 미정의
- 게임 루프(requestAnimationFrame) 없음
- 요청한 기능이 구현 안 됨

문제 없으면 반드시 "OK"만 출력.
문제 있으면 한 줄로 이유만 출력.""")

    human = HumanMessage(content=f"요청: {user_request}\n\n코드:\n{review_content}")

    try:
        response = llm_code.invoke([system, human])
    except Exception as e:
        print(f"[Pipeline] 리뷰 groq 실패 — ollama 폴백: {e}")
        try:
            response = _get_fallback_llm().invoke([system, human])
        except Exception as e2:
            print(f"[Pipeline] 리뷰 ollama도 실패: {e2}")
            return []

    result = response.content.strip()
    if result == "OK":
        return []
    return [result]


def _auto_deploy(user_request: str) -> bool:
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=str(WEBINFECTION_ROOT), check=True, capture_output=True
        )
        result_commit = subprocess.run(
            ["git", "commit", "-m", f"gaon: {user_request[:50]}"],
            cwd=str(WEBINFECTION_ROOT),
            capture_output=True, text=True
        )
        if "nothing to commit" in result_commit.stdout + result_commit.stderr:
            print(f"[Pipeline] 변경사항 없음 — 배포 스킵")
            return True
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(WEBINFECTION_ROOT), check=True, capture_output=True
        )
        print(f"[Pipeline] 자동 배포 완료")
        return True
    except Exception as e:
        print(f"[Pipeline] 배포 실패: {e}")
        return False


def run_pipeline(user_request: str) -> str:
    print(f"[Pipeline] 시작: '{user_request[:40]}'")

    # Step 1
    print(f"[Pipeline] Step 1 — 코드 읽기")
    current_code = _read_files()
    if not current_code:
        return "webinfection 파일을 찾을 수 없어 💜 [EMOTION:confused]"

    # Step 2
    print(f"[Pipeline] Step 2 — 코드 생성")
    final_result = None
    request      = user_request

    for attempt in range(2):
        generated = _generate_code(request, current_code)

        if isinstance(generated, str):
            return generated
        if not generated:
            print(f"[Pipeline] 생성 실패 ({attempt+1}회)")
            continue

        issues = _sanity_check(generated)
        if issues:
            print(f"[Pipeline] sanity check 실패 ({attempt+1}회): {issues}")
            request = f"{user_request}\n\n이전 코드 문제: {', '.join(issues)}"
            continue

        review_issues = _llm_review(generated, user_request)
        if review_issues:
            print(f"[Pipeline] LLM 리뷰 실패 ({attempt+1}회): {review_issues}")
            request = f"{user_request}\n\n이전 코드 문제점: {', '.join(review_issues)}"
            continue

        final_result = generated
        break

    if not final_result:
        return "코드 생성 두 번 시도했는데 퀄리티가 별로야.. 다시 요청해줘 💜 [EMOTION:sad]"

    # Step 3
    print(f"[Pipeline] Step 3 — 파일 저장/삭제")
    writer  = code_writer_tool.build()
    saved   = []
    deleted = []

    for filename, content in final_result.items():
        if content == "__DELETE__":
            r = writer.invoke({"filename": filename, "content": "", "delete": True})
            print(f"[Pipeline] {r}")
            deleted.append(filename)
        else:
            r = writer.invoke({"filename": filename, "content": content})
            print(f"[Pipeline] {r}")
            saved.append(filename)

    # Step 4
    print(f"[Pipeline] Step 4 — 문법 검증")
    executor = code_executor_tool.build()
    errors   = []
    for filename in saved:
        if filename.endswith(".js"):
            r = executor.invoke({"filename": filename})
            print(f"[Pipeline] {r}")
            if "❌" in r:
                errors.append(f"{filename}: {r}")

    if errors:
        print(f"[Pipeline] 문법 오류 감지 — 재시도")
        fix_request = f"{user_request}\n\n문법 오류 수정 필요:\n" + "\n".join(errors)
        fixed = _generate_code(fix_request, current_code)
        if isinstance(fixed, dict) and fixed:
            for filename, content in fixed.items():
                if content != "__DELETE__":
                    writer.invoke({"filename": filename, "content": content})

    # Step 5
    print(f"[Pipeline] Step 5 — 자동 배포")
    success = _auto_deploy(user_request)

    if not success:
        notify("deploy_request", message=user_request[:50])
        return "배포 실패해서 수동 승인 요청 보냈어 💜 [EMOTION:nervous]"

    summary = []
    if saved:
        summary.append(f"수정: {', '.join(saved)}")
    if deleted:
        summary.append(f"삭제: {', '.join(deleted)}")

    return f"완료! {' / '.join(summary)} — 자동 배포까지 끝냈어 🚀 [EMOTION:excited]"