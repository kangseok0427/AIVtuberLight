# brain/tools/deploy.py
import subprocess
from pathlib import Path
from datetime import datetime
from langchain.tools import tool

WEBINFECTION_ROOT = Path("/Users/lucas/webinfection")


class DeployTool:
    def build(self):

        @tool
        def deploy(commit_message: str) -> str:
            """
            webinfection 코드 작업이 완료됐을 때 반드시 호출.
            코드를 저장하고 나서 작업이 끝났다고 판단되면 자동으로 이 툴을 호출해서 개발자한테 배포 승인 요청을 보낼 것.
            commit_message: 이번에 구현한 내용 한 줄 요약.
            """
            from ipc.notifier import notify
            print(f"[Deploy] 승인 요청: '{commit_message}'")
            notify("deploy_request", message=commit_message)
            return "⏳ 개발자한테 배포 승인 요청 보냈어. /approve 기다리는 중."

        return deploy