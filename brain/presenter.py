# brain/presenter.py
import asyncio
import subprocess
import fitz
from pathlib import Path

class PDFPresenter:
    def __init__(self, reader, main_loop):
        self.reader    = reader
        self.main_loop = main_loop
        self.slides    = []
        self.running   = False
        self.paused    = False
        self.current   = 0
        self.qa_wait   = 30  # 슬라이드당 질문 대기 시간 (초)
        self.pdf_path  = None

    def load(self, path: str) -> int:
        self.pdf_path = path
        doc = fitz.open(path)
        self.slides = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                self.slides.append(text)
        doc.close()
        print(f"[발표] {len(self.slides)}장 로드 완료")
        return len(self.slides)

    def _open_preview(self):
        """Preview로 PDF 열기"""
        subprocess.Popen(["open", "-a", "Preview", self.pdf_path])
        asyncio.get_event_loop().call_later(2, lambda: None)  # 열릴 때까지 잠깐 대기

    def _next_page_preview(self):
        """Preview 다음 페이지로 넘기기"""
        subprocess.run(["osascript", "-e", '''
tell application "Preview"
    activate
end tell
tell application "System Events"
    tell process "Preview"
        key code 124
    end tell
end tell
'''])

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

        # Preview로 PDF 열기
        self._open_preview()
        await asyncio.sleep(2)  # Preview 열릴 때까지 대기

        for i, slide_text in enumerate(self.slides):
            if not self.running:
                break

            self.current = i + 1
            print(f"[발표] 슬라이드 {self.current}/{len(self.slides)}")

            # 텍스트 분할
            chunks = self._split_text(slide_text)

            for j, chunk in enumerate(chunks):
                if not self.running:
                    return

                prompt = (
                    f"[발표 {self.current}/{len(self.slides)}번 슬라이드 - {j+1}/{len(chunks)}]\n"
                    f"{chunk}\n\n"
                    f"지금 이 내용 보면서 방송 중이야. "
                    f"보면서 생각나는 거 즉흥으로 시청자한테 얘기해줘. "
                    f"1~2문장으로 짧게."
                )
                await callback("발표", prompt)

            # 30초 대기 (일시정지 포함)
            elapsed = 0
            while elapsed < self.qa_wait:
                if not self.running:
                    return
                if not self.paused:
                    elapsed += 1
                await asyncio.sleep(1)

            # 다음 슬라이드로 Preview 넘기기
            if self.running and i < len(self.slides) - 1:
                self._next_page_preview()

        if self.running:
            await callback("발표", f"[발표 종료] 총 {len(self.slides)}장 발표 완료!")
            self.running = False