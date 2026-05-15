# 🎭 가온 AI VTuber

> 치지직 방송 플랫폼에서 시청자 채팅을 읽고 실시간으로 반응하는 AI VTuber 시스템

---

## ✨ 주요 기능

- 🗨️ **실시간 채팅 반응** — 치지직 채팅을 읽고 자동으로 답변
- 🧠 **LangGraph 에이전트** — think / answer 노드 분리로 사고 후 답변
- 🔍 **인터넷 검색** — 모르는 건 실시간으로 검색해서 대답
- 💾 **대화 메모리** — ChromaDB로 시청자와의 대화 기억
- 😊 **감정 표현** — 답변에 따라 VTube Studio 표정 자동 변환
- 🎙️ **TTS** — Edge TTS로 실시간 음성 출력
- 📺 **OBS 자막** — 답변 내용 실시간 오버레이
- 🎮 **뱀 게임 AI 연동** — 학습 중인 DQN AI 상태를 실시간으로 인식하고 반응
- 📄 **PDF 발표 모드** — PDF 파일 업로드 시 슬라이드별 자동 발표 + 질문타임
- 🤖 **디스코드 봇 원격 제어** — 어디서든 방송 상태 확인 및 제어

---

## 🧩 기술 스택

| 분류 | 기술 |
|------|------|
| 에이전트 | LangGraph, LangChain |
| LLM (Think) | Groq — `llama-3.3-70b-versatile` |
| LLM (Answer) | Google Gemini Flash 2.5 |
| 임베딩 | HuggingFace `paraphrase-multilingual-MiniLM-L12-v2` |
| 벡터 DB | ChromaDB |
| 인터넷 검색 | DuckDuckGo (ddgs) |
| TTS | Edge TTS |
| 아바타 | VTube Studio WebSocket API |
| 방송 | OBS Studio + VB-Cable |
| 채팅 | 치지직 WebSocket 직접 구현 (aiohttp + httpx) |
| 원격 제어 | Discord Bot |
| 뱀 게임 AI | DQN (PyTorch + MPS) |

---

## 🎀 캐릭터 — 가온

- 여성 VTuber
- 보라색 포니테일 · 상어이빨 · 보라색 후드티
- 픽셀 아트 아바타
- 기본적으로 따뜻하고 친절하지만 가끔 츤데레 기질
- 반말 · 이모지 1~2개 · 짧고 자연스러운 답변
- 현재 뱀 게임 AI를 자신의 무의식으로 인식하고 학습 과정을 실시간으로 공유

---

## 🏗 아키텍처

```
치지직 채팅
    ↓
버퍼 + 주제 필터링 (Groq)
    ↓
LangGraph 에이전트
    ├── think_node (Groq)
    ├── tools (검색 / 메모리)
    └── answer_node (Gemini Flash)
        └── snake.txt (뱀 게임 상태 실시간 주입)
    ↓
감정 분류 → VTube Studio 표정 제어
    ↓
Edge TTS → VB-Cable
    ↓
VTube Studio 립싱크 + OBS 자막
    ↓
치지직 방송 송출
```

---

## 🤖 디스코드 봇 명령어

| 명령어 | 설명 |
|--------|------|
| `/status` | 현재 상태 확인 |
| `/clear` | 채팅 버퍼 비우기 |
| `/topic [주제]` | 방송 주제 변경 |
| `/present [경로]` | PDF 발표 시작 |
| `/pause` / `/resume` | 발표 일시정지 / 재개 |
| `/qa` / `/qa_end` | 질문타임 시작 / 종료 |
| `/stop` | 방송 종료 |