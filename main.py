# main.py
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

NAME = os.getenv("VTUBER_NAME")

async def main():

    from brain.agent import agent, NAME, EMOTION_MAP, detect_emotion, update_obs, load_prompt
    from avatar.vtube_bridge import VTubeBridge
    from chat.reader import ChzzkReader
    from tts.tts import text_to_speech

    bridge = VTubeBridge()
    await bridge.connect()
    print(f"[✅] VTube Studio 연결 완료")

    topic = input("\n오늘 방송 주제 (없으면 엔터): ").strip()
    print(f"[주제] {topic if topic else '자유 주제'}")
    print(f"\n{'='*40}")
    print(f"  {NAME} 방송 시작!")
    print(f"{'='*40}\n")

    async def handle_chat(nickname: str, content: str):
        if content.startswith("[도네"):
            user_input = f"{nickname}님이 {content} 후원해주셨어요!"
        elif content == "[구독]":
            user_input = f"{nickname}님이 구독해주셨어요!"
        elif content == "[구독 선물]":
            user_input = f"{nickname}님이 구독 선물을 해주셨어요!"
        else:
            user_input = f"{nickname}: {content}"

        # ✅ 별도 스레드에서 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: agent.invoke({
            "user_input":       user_input,
            "messages":         [],
            "emotion":          "",
            "vtube_expression": None,
            "answer":           ""
        }))

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
    await reader.start()

if __name__ == "__main__":
    asyncio.run(main())