# main.py
import asyncio
import os
import threading
import signal
from dotenv import load_dotenv
from brain.agent import agent, NAME, detect_emotion, update_obs
import random

load_dotenv()

NAME = os.getenv("VTUBER_NAME")

async def main():
    from avatar.vtube_bridge import VTubeBridge
    from chat.reader import ChzzkReader
    from tts.tts import text_to_speech
    from control.discord_bot import VTuberController

    bridge = VTubeBridge()
    await bridge.connect()
    print(f"[✅] VTube Studio 연결 완료")

    topic = input("\n오늘 방송 주제 (없으면 엔터): ").strip()
    print(f"[주제] {topic if topic else '자유 주제'}")
    print(f"\n{'='*40}")
    print(f"  {NAME} 방송 시작!")
    print(f"{'='*40}\n")

    main_loop = asyncio.get_event_loop()

    async def handle_chat(nickname: str, content: str):
        # ── shake 키워드 감지 ──────────────────────────
        if reader.shake_enabled and content.strip().lower() == "shake":
            print(f"[흔들기] {nickname} shake!")
            reactions = [
                f"{nickname} 왜 이러는 거야.. 나 지금 방송 중이잖아 😔",
                f"어지러워.. {nickname} 좀 그만해줄래 💜",
                f"하.. {nickname} 나 지금 힘든데 😞",
                f"{nickname} 나 괜찮긴 한데.. 좀 살살 해줘 💜",
                f"흔들리니까 이상해.. {nickname} 😢",
                f"나 어지러워 {nickname}.. 조금만 쉬자 💜",
                f"{nickname} 왜 그래.. 나 지금 열심히 하고 있었는데 😔",
            ]
            msg = random.choice(reactions)
            await asyncio.gather(
                bridge.shake(duration=2.0),
                text_to_speech(msg),
                bridge.trigger_and_reset("Exp5 FaceShadow", duration=2.0)
            )
            return
        # ───────────────────────────────────────────────
        if content.startswith("[도네"):
            user_input = f"{nickname}님이 {content} 후원해주셨어요!"
        elif content == "[구독]":
            user_input = f"{nickname}님이 구독해주셨어요!"
        elif content == "[구독 선물]":
            user_input = f"{nickname}님이 구독 선물을 해주셨어요!"
        else:
            user_input = f"{nickname}: {content}"

        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: agent.invoke({
                    "user_input":       user_input,
                    "messages":         [],
                    "emotion":          "",
                    "vtube_expression": None,
                    "answer":           ""
                })),
                timeout=60.0  # 60초 안에 응답 없으면 포기
            )
        except asyncio.TimeoutError:
            print(f"[⚠️] 응답 타임아웃: {nickname}: {content}")
            return

        print(f"😊 감정: {result['emotion']} → {result['vtube_expression']}")
        print(f"🎤 {NAME}: {result['answer']}\n")

        await asyncio.gather(
            bridge.trigger_and_reset(result["vtube_expression"], duration=5.0),
            text_to_speech(result["answer"])
        )

    async def handle_subscription(nickname: str, gift: bool = False):
        msg = f"{nickname}님 구독 선물 감사합니다!" if gift else f"{nickname}님 구독 감사합니다!"
        print(f"[구독] {msg}")
        update_obs(msg)
        await text_to_speech(msg)

    reader = ChzzkReader(
        on_chat_callback=handle_chat,
        on_subscription_callback=handle_subscription,
        topic=topic
    )

    controller = VTuberController(reader=reader, main_loop=main_loop)
    reader.controller = controller  # 필터 알람용 역참조
    controller.bridge = bridge

    bot_thread = threading.Thread(target=controller.run, daemon=True)
    bot_thread.start()
    print("[✅] 디스코드 봇 시작!")

    def handle_exit(signum, frame):
        update_obs("😴 가온이 자는 중...")
        os._exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    await reader.start()

if __name__ == "__main__":
    asyncio.run(main())