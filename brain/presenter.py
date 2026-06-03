# brain/presenter.py
import asyncio
import subprocess
import fitz
from pathlib import Path


class PDFPresenter:
    def __init__(self):
        self.slides   = []
        self.running  = False
        self.paused   = False
        self.current  = 0
        self.qa_wait  = 10   # 슬라이드당 질문 대기 시간 (초)
        self.pdf_path = None
        # 슬라이드 인덱스 → 실제 PDF 페이지 번호 매핑
        # 이미지만 있는 페이지 스킵해도 Preview 페이지 넘김이 어긋나지 않게
        self.page_indices: list[int] = []

    def load(self, path: str) -> int:
        self.pdf_path    = path
        self.slides      = []
        self.page_indices = []

        doc = fitz.open(path)
        for page_num, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                self.slides.append(text)
                self.page_indices.append(page_num)  # 실제 페이지 번호 기록
            else:
                print(f"[발표] 페이지 {page_num + 1} 텍스트 없음 — 이미지 전용 슬라이드로 처리")
        doc.close()

        print(f"[발표] {len(self.slides)}장 로드 완료 (전체 {doc.page_count}페이지)")
        return len(self.slides)

    async def _open_preview(self):
        proc = await asyncio.create_subprocess_exec(
            "open", "-a", "Preview", self.pdf_path
        )
        await proc.wait()

    async def _goto_page_preview(self, page_num: int):
        """Preview에서 특정 페이지로 이동 — 실제 PDF 페이지 번호 기준"""
        # AppleScript로 페이지 번호 직접 입력
        script = f'''
tell application "Preview"
    activate
end tell
tell application "System Events"
    tell process "Preview"
        keystroke "g" using command down
        delay 0.3
        keystroke "{page_num + 1}"
        key code 36
    end tell
end tell
'''
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        print(f"[발표] Preview 페이지 이동: {page_num + 1}페이지")

    def _split_text(self, text: str) -> list[str]:
        """
        텍스트 분량에 따라 1~3개로 분할
        짧으면 1개, 중간이면 2개, 길면 3개
        """
        words = text.split()
        total = len(words)

        if total <= 50:
            return [text]
        elif total <= 150:
            mid = total // 2
            return [
                " ".join(words[:mid]),
                " ".join(words[mid:])
            ]
        else:
            t1 = total // 3
            t2 = total * 2 // 3
            return [
                " ".join(words[:t1]),
                " ".join(words[t1:t2]),
                " ".join(words[t2:])
            ]

    def _build_prompt(
        self,
        slide_num: int,
        total: int,
        chunk_idx: int,
        total_chunks: int,
        chunk_text: str,
    ) -> str:
        if slide_num == 1 and chunk_idx == 0:
            position = "발표 첫 번째 슬라이드야. 시청자한테 발표 시작을 알리고 바로 내용 설명으로 들어가."
        elif slide_num == total and chunk_idx == total_chunks - 1:
            position = "마지막 슬라이드야. 내용 설명 후 발표 마무리 멘트도 자연스럽게 붙여줘."
        elif chunk_idx == 0:
            position = f"{slide_num}번째 슬라이드로 넘어왔어."
        else:
            position = f"{slide_num}번째 슬라이드 이어서 설명하는 부분이야."

        return (
            f"[발표 모드 - {slide_num}/{total}번 슬라이드, {chunk_idx+1}/{total_chunks}]\n"
            f"슬라이드 내용:\n{chunk_text}\n\n"
            f"## 지시사항\n"
            f"{position}\n"
            f"지금 이 슬라이드 내용을 시청자한테 발표자처럼 설명해야 해.\n\n"
            f"반드시 지킬 것:\n"
            f"1. 슬라이드에 있는 핵심 내용을 빠짐없이 다 짚어줘\n"
            f"2. 각 항목이 뭔지, 왜 중요한지, 어떻게 동작하는지 네 말로 풀어서 설명해\n"
            f"3. 단순 리액션('오 신기하다', '이거 재밌죠') 금지 — 내용 설명이 메인이야\n"
            f"4. 발표 말투로, 4~6문장으로 충분히 설명해\n"
            f"5. 캐릭터는 유지하되 이 슬라이드에서는 설명 완성도가 최우선\n"
        )

    def toggle_pause(self):
        self.paused = not self.paused
        state = "일시정지" if self.paused else "재개"
        print(f"[발표] {state}")
        return self.paused

    def stop(self):
        self.running = False
        self.paused  = False
        print("[발표] 종료")

    async def present(self, callback):
        self.running = True
        self.current = 0

        await self._open_preview()
        await asyncio.sleep(2)

        # 첫 슬라이드로 이동
        if self.page_indices:
            await self._goto_page_preview(self.page_indices[0])

        for i, slide_text in enumerate(self.slides):
            if not self.running:
                break

            self.current = i + 1
            print(f"[발표] 슬라이드 {self.current}/{len(self.slides)} (PDF {self.page_indices[i]+1}페이지)")

            chunks = self._split_text(slide_text)

            for j, chunk in enumerate(chunks):
                if not self.running:
                    return

                prompt = self._build_prompt(
                    slide_num=self.current,
                    total=len(self.slides),
                    chunk_idx=j,
                    total_chunks=len(chunks),
                    chunk_text=chunk,
                )
                await callback("발표", prompt)

            # 슬라이드당 대기 (일시정지 포함)
            elapsed = 0
            while elapsed < self.qa_wait:
                if not self.running:
                    return
                if not self.paused:
                    elapsed += 1
                await asyncio.sleep(1)

            # 다음 슬라이드로 이동 — 실제 페이지 번호 기준
            if self.running and i < len(self.slides) - 1:
                next_page = self.page_indices[i + 1]
                await self._goto_page_preview(next_page)

        if self.running:
            await callback("발표", "[발표 종료] 발표 다 끝났어! 시청자들한테 마무리 인사 해줘.")
            self.running = False