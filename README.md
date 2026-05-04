# 🎭 가온 AI VTuber

치지직 방송 플랫폼에서 시청자 채팅을 읽고 실시간으로 반응하는 AI VTuber 시스템.

---

## 🏗 아키텍처

```
치지직 채팅
    ↓
버퍼 + 주제 필터링 (Groq)
    ↓
LangGraph 에이전트
    ├── think_node (툴 호출 판단 · Groq)
    ├── tools (인터넷 검색 / 대화 메모리)
    └── answer_node (캐릭터 답변 생성 · Gemini Flash)
    ↓
감정 분류 → VTube Studio 표정 제어
    ↓
Edge TTS → VB-Cable
    ↓
VTube Studio 립싱크 + OBS 자막 오버레이
    ↓
치지직 방송 송출
```

---

## 🛠 필수 준비물

### 소프트웨어
- Anaconda (Python 3.11)
- VTube Studio
- OBS Studio
- VB-Cable → https://vb-audio.com/Cable

### API 키
- Google AI Studio (Gemini Flash + 임베딩) → https://aistudio.google.com
- Groq → https://console.groq.com

---

## 📦 설치

### 1. 저장소 클론
```bash
git clone https://github.com/your-repo/ai-vtuber.git
cd ai-vtuber
```

### 2. 가상환경 생성 및 패키지 설치
```bash
conda env create -f environment.yml
conda activate vtuber
```

### 3. 환경변수 설정
`.env` 파일을 생성하고 아래 내용을 채워줘:

```bash
# LLM API
GOOGLE_API_KEY=         # Google AI Studio에서 발급
GROQ_API_KEY=           # Groq Console에서 발급

# 캐릭터
VTUBER_NAME=가온
VTUBER_THINK_TEMP=0.1
VTUBER_ANSWER_TEMP=0.8

# TTS
TTS_VOICE=ko-KR-SunHiNeural
TTS_PITCH=+20Hz
TTS_RATE=+5%

# VTube Studio
VTUBE_TOKEN=            # 첫 실행 시 자동 발급

# 치지직
CHZZK_NID_AUT=          # 네이버 쿠키
CHZZK_NID_SES=          # 네이버 쿠키
CHZZK_CHANNEL_ID=       # 치지직 채널 ID
```

### 4. 네이버 쿠키 확인 방법
1. Chrome에서 치지직 접속 후 로그인
2. F12 → Application 탭
3. Cookies → `https://chzzk.naver.com`
4. `NID_AUT`, `NID_SES` 값 복사

### 5. 프롬프트 파일 생성
`prompts/` 폴더에 아래 두 파일을 직접 작성:
- `think.txt` → think 노드 시스템 프롬프트
- `answer.txt` → answer 노드 (캐릭터 설정 포함) 시스템 프롬프트

---

## 🎭 VTube Studio 설정

1. VTube Studio → 설정 → API 서버 → 활성화
2. 포트: `8001`
3. 립싱크 → Use microphone → **VB-Cable** 선택
4. 아래 표정 파일이 모델에 있어야 함:

```
Exp1 Sparkling.exp3.json
Exp2 Heart.exp3.json
Exp3 Confused.exp3.json
Exp5 FaceShadow.exp3.json
Exp6 Surprise.exp3.json
Exp7 Laugh.exp3.json
Exp8 Angry.exp3.json
Exp9 Loading.exp3.json
Exp10 Nervous.exp3.json
```

### VTube Studio 토큰 발급
`VTUBE_TOKEN` 비워두고 실행하면 자동으로 발급돼. VTube Studio 팝업 허용 후 터미널에 출력된 토큰을 `.env`에 저장하면 됨.

---

## 📺 OBS 설정

- 인코더: NVENC (Windows)
- 비트레이트: 3000~4000 kbps
- 해상도: 1280x720 / FPS: 30
- 소스 추가:
  - 윈도우 캡처: VTube Studio
  - 브라우저 (로컬 파일): `obs/overlay.html`
  - 오디오 입력 캡처: VB-Cable

---

## 🚀 실행

```bash
conda activate vtuber
python main.py
```

실행 순서:
1. VTube Studio 실행
2. OBS 실행
3. `python main.py`
4. 방송 주제 입력
5. 치지직에서 방송 시작!

---

## 📁 프로젝트 구조

```
ai-vtuber/
├── main.py
├── environment.yml
├── brain/
│   ├── agent.py
│   └── tools/
│       ├── __init__.py
│       ├── search.py
│       └── memory.py
├── avatar/
│   └── vtube_bridge.py
├── chat/
│   └── reader.py
├── tts/
│   └── tts.py
├── obs/
│   └── overlay.html
└── prompts/          # gitignore
    ├── think.txt
    └── answer.txt
```

---

## ❓ 트러블슈팅

**VTube Studio 연결 끊김**
→ 자동으로 재연결함. 자주 끊기면 VTube Studio API 설정 확인.

**토큰 만료**
→ `.env`에서 `VTUBE_TOKEN` 삭제 후 재실행.

**채팅이 안 읽힘**
→ `CHZZK_NID_AUT`, `CHZZK_NID_SES` 만료됐을 수 있음. 다시 발급.

**메모리 초기화**
```bash
rm -rf .chroma
```