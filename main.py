# AIVtuberLight/main.py
import asyncio
import os
import json
import random
import threading
import signal
import time
from dotenv import load_dotenv
from brain.agent import agent, update_obs, memory_tool, detect_emotion, EMOTION_MAP
from brain.webinfection_pipeline import run_pipeline

load_dotenv()

NAME            = os.getenv("VTUBER_NAME")
GAME_STATE_PATH = "/Users/lucas/MechanicoC/checkpoints/mechanico_status.json"
QUEUE_PATH      = "command_queue.json"
WHISPER_INTERVAL_SEC = 300

SLOW_RESPONSE_MESSAGES = [
    "잠깐만, 생각 좀 하고 있어.. 💜",
    "음.. 조금만 기다려줘 🤔",
    "어, 나 지금 열심히 생각 중이야.. ⏳",
    "잠깐, 좀 복잡한 질문이야.. 💜",
    "생각보다 어려운 질문인데.. 잠깐만 ⏳",
]


async def main():
    from avatar.vtube_bridge import VTubeBridge
    from chat.reader import ChzzkReader
    from tts.tts import text_to_speech

    bridge = VTubeBridge()
    await bridge.connect()
    print(f"[✅] VTube Studio 연결 완료")
    print(f"\n{'='*40}\n  {NAME} 방송 시작!\n{'='*40}\n")

    main_loop       = asyncio.get_event_loop()
    whisper_enabled = True

    # ── 위스퍼 ───────────────────────────────────────
    async def do_whisper():
        print("[위스퍼] 혼잣말 트리거")
        try:
            result = await asyncio.wait_for(
                main_loop.run_in_executor(None, lambda: agent.invoke({
                    "user_input":       "[위스퍼] 지금 떠오르는 생각이나 느낀 점을 짧게 혼잣말로 말해줘.",
                    "messages":         [],
                    "emotion":          "",
                    "vtube_expression": None,
                    "answer":           "",
                    "is_fallback":      False,
                })),
                timeout=30.0
            )
            if not result.get("is_fallback"):
                print(f"[위스퍼] {NAME}: {result['answer']}")
                await asyncio.gather(
                    bridge.trigger_and_reset(result["vtube_expression"], duration=3.0),
                    text_to_speech(result["answer"])
                )
        except asyncio.TimeoutError:
            print("[위스퍼] 타임아웃")
        except Exception as e:
            print(f"[위스퍼] 오류: {e}")

    async def whisper_loop():
        print("[위스퍼] 루프 시작 (5분 간격)")
        while True:
            await asyncio.sleep(WHISPER_INTERVAL_SEC)
            if not whisper_enabled:
                continue
            while hasattr(reader, 'is_busy') and reader.is_busy:
                await asyncio.sleep(1)
            asyncio.create_task(do_whisper())

    # ── IPC 커맨드 큐 폴링 ───────────────────────────
    async def command_queue_loop():
        nonlocal whisper_enabled
        print("[IPC] 커맨드 큐 폴링 시작")
        while True:
            await asyncio.sleep(2)
            try:
                if not os.path.exists(QUEUE_PATH):
                    continue
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                if not queue:
                    continue
                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                    json.dump([], f)
                for item in queue:
                    cmd  = item.get("cmd")
                    args = item.get("args", {})
                    print(f"[IPC] 수신: {cmd} {args}")
                    if cmd == "say":
                        reader.priority_buffer.append(("디스코드", args.get("text", ""), time.time()))
                    elif cmd == "clear":
                        reader.buffer.clear()
                    elif cmd == "topic":
                        reader.topic = args.get("topic", "")
                    elif cmd == "news_on":
                        reader.news_enabled = True
                    elif cmd == "news_off":
                        reader.news_enabled = False
                    elif cmd == "news_topic":
                        reader.news_topic = args.get("topic", "IT 기술")
                    elif cmd == "shake_on":
                        reader.shake_enabled = True
                    elif cmd == "shake_off":
                        reader.shake_enabled = False
                    elif cmd == "whisper_on":
                        whisper_enabled = True
                    elif cmd == "whisper_off":
                        whisper_enabled = False
                    elif cmd == "present":
                        path = args.get("path", "")
                        if os.path.exists(path):
                            from brain.presenter import PDFPresenter
                            reader.presenter = PDFPresenter()
                            count = reader.presenter.load(path)
                            print(f"[IPC] 발표 시작: {count}장")
                            asyncio.create_task(reader.presenter.present(callback=reader.callback))
                    elif cmd == "qa_on":
                        if hasattr(reader, 'presenter') and reader.presenter:
                            reader.presenter.paused = True
                    elif cmd == "qa_off":
                        if hasattr(reader, 'presenter') and reader.presenter:
                            reader.presenter.paused = False
                    elif cmd == "stop_present":
                        if hasattr(reader, 'presenter') and reader.presenter:
                            reader.presenter.stop()
            except Exception as e:
                print(f"[IPC] 오류: {e}")

    # ── 게임 클리어 감지 ─────────────────────────────
    async def game_event_loop():
        last_cleared = None
        print("[Game] 이벤트 감지 루프 시작")
        while True:
            await asyncio.sleep(2)
            try:
                with open(GAME_STATE_PATH, "r") as f:
                    state = json.load(f)
                cleared = state.get("cleared", 0)
                if last_cleared is None:
                    last_cleared = cleared
                elif cleared > last_cleared:
                    last_cleared = cleared
                    stage = state.get("stage", "?")
                    zone  = state.get("zone", "?")
                    ep    = state.get("episode", "?")
                    print(f"[Game] 클리어! {stage} {zone}구역 ep={ep} total={cleared}")
            except Exception:
                pass

    # ── 채팅 처리 ────────────────────────────────────
    async def handle_chat(nickname: str, content: str):
        from tts.tts import text_to_speech

        # shake
        if reader.shake_enabled and content.strip().lower() == "shake":
            print(f"[흔들기] {nickname}")
            msg = random.choice([
                f"{nickname} 왜 이러는 거야.. 나 지금 방송 중이잖아 😔",
                f"어지러워.. {nickname} 좀 그만해줄래 💜",
                f"하.. {nickname} 나 지금 힘든데 😞",
                f"{nickname} 나 괜찮긴 한데.. 좀 살살 해줘 💜",
                f"흔들리니까 이상해.. {nickname} 😢",
                f"나 어지러워 {nickname}.. 조금만 쉬자 💜",
                f"{nickname} 왜 그래.. 나 지금 열심히 하고 있었는데 😔",
            ])
            await bridge.trigger_and_reset("Exp5 FaceShadow", duration=0.5)
            await asyncio.gather(bridge.shake(duration=2.0), text_to_speech(msg))
            return

        # [개발] 태그 감지 → webinfection 파이프라인
        if content.startswith("[개발]"):
            dev_request = content[4:].strip()
            print(f"[Pipeline] 개발 태그 감지: '{dev_request[:40]}'")
            try:
                result = await asyncio.wait_for(
                    main_loop.run_in_executor(None, lambda: run_pipeline(dev_request)),
                    timeout=120.0
                )
                emotion, clean = detect_emotion(result)
                vtube_expr = EMOTION_MAP.get(emotion, None)
                update_obs(clean)
                print(f"🎤 {NAME}: {clean}")
                await asyncio.gather(
                    bridge.trigger_and_reset(vtube_expr, duration=3.0),
                    text_to_speech(clean)
                )
            except asyncio.TimeoutError:
                print(f"[Pipeline] 타임아웃")
                await text_to_speech("잠깐만, 코드 수정하는 중이야.. 💜")
            except Exception as e:
                print(f"[Pipeline] 오류: {e}")
            return

        # user_input 포맷
        if content.startswith("[도네]"):
            user_input = f"{nickname}님이 도네이션 해주셨어요! {content[5:].strip()}"
        elif content == "[구독]":
            user_input = f"{nickname}님이 구독해주셨어요!"
        elif content == "[구독 선물]":
            user_input = f"{nickname}님이 구독 선물을 해주셨어요!"
        else:
            user_input = f"{nickname}: {content}"

        # agent 호출
        agent_task = main_loop.run_in_executor(
            None,
            lambda: agent.invoke({
                "user_input":       user_input,
                "messages":         [],
                "emotion":          "",
                "vtube_expression": None,
                "answer":           "",
                "is_fallback":      False,
            })
        )

        try:
            result = await asyncio.wait_for(asyncio.shield(agent_task), timeout=60.0)
        except asyncio.TimeoutError:
            slow_msg = random.choice(SLOW_RESPONSE_MESSAGES)
            print(f"[⏳] 응답 지연 60초 — {slow_msg}")
            await text_to_speech(slow_msg)
            try:
                result = await asyncio.wait_for(agent_task, timeout=120.0)
            except asyncio.TimeoutError:
                print(f"[⚠️] 응답 타임아웃 180초: {nickname}: {content}")
                return

        print(f"😊 감정: {result['emotion']} → {result['vtube_expression']}")
        print(f"🎤 {NAME}: {result['answer']}\n")

        if not result.get("is_fallback", False):
            threading.Thread(
                target=memory_tool.save,
                args=(user_input, result["answer"]),
                daemon=True
            ).start()
        else:
            print(f"[Memory] fallback — 저장 스킵")

        await asyncio.gather(
            bridge.trigger_and_reset(result["vtube_expression"], duration=5.0),
            text_to_speech(result["answer"])
        )

    async def handle_subscription(nickname: str, gift: bool = False):
        from tts.tts import text_to_speech
        msg = f"{nickname}님 구독 선물 감사합니다!" if gift else f"{nickname}님 구독 감사합니다!"
        print(f"[구독] {msg}")
        update_obs(msg)
        await text_to_speech(msg)

    reader = ChzzkReader(on_chat_callback=handle_chat, on_subscription_callback=handle_subscription, topic="")

    def handle_exit(signum, frame):
        update_obs("😴 가온이 자는 중...")
        os._exit(0)

    signal.signal(signal.SIGINT,  handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    asyncio.create_task(game_event_loop())
    asyncio.create_task(whisper_loop())
    asyncio.create_task(command_queue_loop())
    print("[✅] 게임 이벤트 / 위스퍼 / IPC 루프 시작!")

    await reader.start()


if __name__ == "__main__":
    asyncio.run(main())