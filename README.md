# 🎙️ AI VTuber — 24시간 자율 방송 AI

> 치지직에서 24시간 혼자 방송하는 AI입니다.  
> 시청자 채팅을 읽고, 생각하고, 목소리로 대답하고, 표정도 바꿉니다.

<br>

## 이게 뭐예요?

사람 없이 혼자 방송하는 AI 스트리머입니다.

시청자가 채팅을 치면 → AI가 읽고 → 생각하고 → 목소리로 대답하고 → 아바타 표정도 바뀝니다.  
단순한 챗봇이 아니라, **기억도 하고 (시청자 이름 기억), 도구도 쓰고 (검색, 게임 데이터 조회), 감정 표현도 합니다.**

<br>

## 어떻게 동작하나요?

```
시청자 채팅 입력
      ↓
채팅 수집 · 필터링 (도배, 욕설 걸러냄)
      ↓
메모리 검색 (이 시청자 전에 뭐 얘기했지?)
      ↓
LLM 추론 (뭐라고 답할지 생각)
      ↓
도구 사용 (필요하면 검색하거나 게임 데이터 가져옴)
      ↓
TTS 음성 합성 (텍스트 → 목소리)
      ↓
아바타 표정 변경 + 방송 송출
```

<br>

## 기술 스택

| 역할 | 사용 기술 |
|------|-----------|
| 방송 플랫폼 | 치지직 (채팅 WebSocket 수집) |
| 추론 모델 | Groq llama-3.3-70b (생각) + llama-3.1-8b (대답) |
| 보조 모델 | 학교 Ollama gemma4:26b |
| 단기 메모리 | ChromaDB — 최근 대화 5개 유지 |
| 장기 메모리 | ChromaDB — 시청자별 정보 Wiki |
| 음성 인식 | Groq Whisper STT |
| 음성 합성 | Edge TTS (피치 +20Hz, 속도 +5%) |
| 아바타 제어 | VTube Studio WebSocket API |
| 원격 제어 | Discord 봇 (슬래시 커맨드) |
| 서버 | Apple M1 맥미니 8GB |
| 언어 / 환경 | Python 3.11, conda (vtuber) |

<br>

## 프로젝트 구조

```
ai-vtuber/
├── main.py                  # 전체 실행 진입점
├── brain/
│   ├── agent.py             # AI 판단 · Tool Use 오케스트레이션
│   ├── llm_config.py        # 모델 설정 (Groq / Ollama 라우팅)
│   ├── presenter.py         # 응답 후처리 · 발화 준비
│   └── tools/
│       ├── search.py        # 웹 검색 도구
│       ├── memory.py        # 메모리 읽기/쓰기
│       ├── code_reader.py   # 코드 분석 도구
│       └── eternal_return.py # 게임 데이터 API 연동
├── avatar/
│   └── vtube_bridge.py      # VTube Studio WebSocket 제어
├── chat/
│   └── reader.py            # 치지직 채팅 실시간 수집
├── tts/
│   └── tts.py               # Edge TTS 음성 합성
├── voice/
│   └── listener.py          # Whisper STT 음성 인식
├── control/
│   ├── discord_bot.py       # 원격 제어 봇
│   └── filter.py            # 채팅 필터링 규칙
└── prompts/
    ├── think.txt            # 추론용 시스템 프롬프트
    ├── answer.txt           # 발화용 시스템 프롬프트
    └── snake.txt            # 캐릭터 설정 (Niki)
```

<br>

## 단계별 기능 설명

### Stage 1 · 채팅 수집 · 필터링
치지직 채팅을 WebSocket으로 실시간 수집합니다.  
도배, 금지어, 봇 메시지를 자동으로 걸러내고 AI가 처리할 수 있는 형태로 변환합니다.  
`chat/reader.py` · `control/filter.py`

---

### Stage 2 · 음성 입출력 (STT / TTS)
마이크 입력을 Groq Whisper로 텍스트로 변환(STT)하고,  
AI 응답을 Edge TTS로 음성 합성(TTS)해서 방송에 출력합니다.  
피치와 속도를 조정해 VTuber 캐릭터에 맞는 목소리를 구현했습니다.  
`tts/tts.py` · `voice/listener.py`

---

### Stage 3 · 메모리 시스템
- **단기 메모리**: 최근 대화 5개를 벡터 DB에 저장해 대화 흐름을 유지합니다.
- **장기 메모리**: 시청자별 정보(이름, 관심사, 과거 대화)를 Wiki처럼 누적 저장합니다.  
  벡터 유사도 검색으로 관련 기억을 빠르게 불러옵니다.  
`brain/tools/memory.py`

---

### Stage 4 · 멀티 LLM 추론 파이프라인
2단계로 구성되어 있습니다.
1. **Think 모델** (llama-3.3-70b): 내부적으로 상황을 분석하고 무엇을 말할지 판단
2. **Answer 모델** (llama-3.1-8b): 실제 방송에서 발화할 문장 생성

Groq API와 학교 Ollama 서버를 상황에 따라 자동 선택합니다.  
`brain/agent.py` · `brain/llm_config.py` · `brain/presenter.py`

---

### Stage 5 · Tool Use (도구 사용)
AI가 대화 중 필요하다고 판단하면 스스로 도구를 호출합니다.
- 웹 검색으로 최신 정보 확인
- Eternal Return API로 게임 실시간 데이터 조회
- 코드 분석 및 설명  

`brain/tools/`

---

### Stage 6 · 아바타 연동 (VTube Studio)
VTube Studio WebSocket API를 통해 AI 감정 상태를 Live2D 아바타에 실시간 반영합니다.  
기쁨, 놀람, 당황 등 감정에 따라 표정과 모션이 자동으로 바뀝니다.  
`avatar/vtube_bridge.py`

---

### Stage 7 · 원격 제어 · 운영
Discord 봇으로 방송 중 실시간 제어가 가능합니다.
- `/mode 1` — 음성 응답 모드
- `/mode 2` — 채팅 응답 모드

M1 맥미니 단일 서버에서 전체 파이프라인을 24시간 운영합니다.  
`control/discord_bot.py` · `main.py`

<br>

## 앞으로 할 것 (작업 큐)

- [ ] `/mode` 디스코드 명령어 — 음성/채팅 모드 런타임 전환
- [ ] VLM 연동 — 영상 도네이션·카페 이미지 분석 후 리액션
- [ ] LoRA 파인튜닝 — 데이터 충분히 쌓이면 캐릭터 특화 학습
- [ ] 메인컴 분리 — RTX 5060Ti로 게임 학습 / M1은 방송 송출 전담

<br>

## 캐릭터

- **이름**: Niki
- **방송**: 치지직 24시간 상시 방송
- **특기**: Eternal Return 게임 분석 · 시청자 기억 · 실시간 검색

<br>

---

> 1학년 개인 프로젝트 | AI 소프트웨어학과 | 학번 2601110276