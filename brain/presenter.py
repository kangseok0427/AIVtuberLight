# brain/presenter.py
import fitz
import asyncio

class PDFPresenter:
    def __init__(self, callback):
        self.callback  = callback
        self.slides    = []
        self.current   = 0
        self.running   = False
        self.paused    = False
        self.qa_mode   = False  # 질문타임 여부

    def load(self, pdf_path: str):
        doc = fitz.open(pdf_path)
        self.slides = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                self.slides.append(text)
        doc.close()
        self.current = 0
        print(f"[발표] {len(self.slides)}페이지 로드됨")

    def has_next(self) -> bool:
        return self.current < len(self.slides)

    def next_slide(self) -> str:
        if self.has_next():
            slide = self.slides[self.current]
            self.current += 1
            return f"[발표 {self.current}/{len(self.slides)}페이지]\n{slide}"
        return ""

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.running = False
        self.paused  = False
        self.qa_mode = False

    def start_qa(self):
        """질문타임 시작 - 채팅 자유롭게 받기"""
        self.qa_mode = True
        self.paused  = True

    def end_qa(self):
        """질문타임 종료 - 발표 재개"""
        self.qa_mode = False
        self.paused  = False

    async def present(self, interval: int = 30):
        self.running = True
        while self.running and self.has_next():
            # 일시정지 대기
            while self.paused:
                await asyncio.sleep(1)
                if not self.running:
                    return

            slide_content = self.next_slide()
            prompt = f"다음 내용을 발표해줘. 캐릭터 유지하면서 자연스럽게 설명해: {slide_content}"
            await self.callback("발표", prompt)
            await asyncio.sleep(interval)

        if self.running:
            await self.callback("발표", "발표가 끝났어! 질문 있으면 해줘 😊")
        self.running = False
        print("[발표] 끝!")