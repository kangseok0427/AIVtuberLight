# main.py
import asyncio
import os
import json
import random
import threading
import signal
import discord
from dotenv import load_dotenv
from brain.agent import agent, update_obs, memory_tool

load_dotenv()

NAME            = os.getenv("VTUBER_NAME")
GAME_STATE_PATH = "/Users/lucas/MechanicoC/checkpoints/mechanico_status.json"

# 이벤트별 중얼거리기 프롬프트
WHISPER_PROMPTS = {
    "battle_start":  "[중얼거리기] 전투 시작됐어. 현재 게임 상태 보면서 짧게 혼잣말해줘. 1문장.",
    "battle_win":    "[중얼거리기] 전투에서 이겼어! 현재 게임 상태 보면서 짧게 흥분해줘. 1문장.",
    "battle_lose":   "[중얼거리기] 전투에서 졌어.. 현재 게임 상태 보면서 짧게 속상해해줘. 1문장.",
    "boss_appear":   "[중얼거리기] 보스가 나타났어! 현재 게임 상태 보면서 짧게 긴장해줘. 1문장.",
    "party_ko":      "[중얼거리기] 파티원이 쓰러졌어.. 현재 게임 상태 보면서 짧게 걱정해줘. 1문장.",
    "skill_used":    "[중얼거리기] 스킬을 썼어. 현재 게임 상태 보면서 짧게 반응해줘. 1문장.",
    "critical":      "[중얼거리기] 크리티컬이 터졌어! 현재 게임 상태 보면서 짧게 흥분해줘. 1문장.",
    "flee_success":  "[중얼거리기] 도망 성공했어! 현재 게임 상태 보면서 짧게 안도해줘. 1문장.",
    "flee_fail":     "[중얼거리기] 도망 실패했어.. 현재 게임 상태 보면서 짧게 당황해줘. 1문장.",
    "dungeon_clear": "[중얼거리기] 던전 클리어! 현재 게임 상태 보면서 짧게 자랑해줘. 1문장.",
    "gameover":      "[중얼거리기] 게임오버야.. 현재 게임 상태 보면서 짧게 반응해줘. 1문장.",
    "episode_end":   "[중얼거리기] 이번 판 끝났어. 현재 게임 상태 보면서 짧게 회고해줘. 1문장.",
}


async def main():
    from avatar.vtube_bridge import VTubeBridge
    from chat.reader import ChzzkReader
    from tts.tts import text_to_speech
    from control.discord_bot import VTuberController

    bridge = VTubeBridge()
    await bridge.connect()
    print(f"[✅] VTube Studio 연결 완료")

    topic = input("\n오늘 방송 주제 (없으면 엔터): ").strip()
    mode  = input("모드 선택 (1: 음성, 2: 채팅): ").strip()

    print(f"[주제] {topic if topic else '자유 주제'}")
    print(f"[모드] {'음성 입력' if mode == '1' else '채팅 입력'}")
    print(f"\n{'='*40}")
    print(f"  {NAME} 방송 시작!")
    print(f"{'='*40}\n")

    main_loop        = asyncio.get_event_loop()
    whisper_enabled  = True   # /whisper on/off 토글
    last_event       = None   # 직전 이벤트 — 중복 방지

    SLOW_RESPONSE_MESSAGES = [
        "잠깐만, 생각 좀 하고 있어.. 💜",
        "음.. 조금만 기다려줘 🤔",
        "어, 나 지금 열심히 생각 중이야.. ⏳",
        "잠깐, 좀 복잡한 질문이야.. 💜",
        "생각보다 어려운 질문인데.. 잠깐만 ⏳",
    ]

    async def do_whisper(event: str):
        """중얼거리기 — agent 통해서 짧게 반응"""
        prompt = WHISPER_PROMPTS.get(event)
        if not prompt:
            return
        print(f"[중얼거리기] 이벤트: {event}")
        try:
            result = await asyncio.wait_for(
                main_loop.run_in_executor(None, lambda: agent.invoke({
                    "user_input":       prompt,
                    "messages":         [],
                    "emotion":          "",
                    "vtube_expression": None,
                    "answer":           "",
                    "is_fallback":      False,
                })),
                timeout=30.0
            )
            if not result.get("is_fallback"):
                await asyncio.gather(
                    bridge.trigger_and_reset(result["vtube_expression"], duration=3.0),
                    text_to_speech(result["answer"])
                )
                print(f"[중얼거리기] {NAME}: {result['answer']}")
        except asyncio.TimeoutError:
            print(f"[중얼거리기] 타임아웃: {event}")
        except Exception as e:
            print(f"[중얼거리기] 오류: {e}")

    async def game_event_loop():
        """게임 상태 JSON 폴링 — 이벤트 감지 시 중얼거리기"""
        nonlocal last_event, whisper_enabled
        print("[Game] 이벤트 감지 루프 시작")
        while True:
            await asyncio.sleep(2)  # 2초마다 폴링
            if not whisper_enabled:
                continue
            try:
                with open(GAME_STATE_PATH, "r") as f:
                    state = json.load(f)
                event = state.get("event", "")
                if not event or event == last_event:
                    continue
                last_event = event
                if event in WHISPER_PROMPTS:
                    # 채팅 처리 중이면 잠깐 대기
                    while hasattr(reader, 'is_busy') and reader.is_busy:
                        await asyncio.sleep(1)
                    asyncio.create_task(do_whisper(event))
            except Exception as e:
                pass  # 파일 없거나 파싱 실패면 조용히 넘김

    async def handle_chat(nickname: str, content: str):
        # shake 키워드 감지
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
            await bridge.trigger_and_reset("Exp5 FaceShadow", duration=0.5)
            await asyncio.gather(
                bridge.shake(duration=2.0),
                text_to_speech(msg)
            )
            return

        if content.startswith("[도네]"):
            user_input = f"{nickname}님이 도네이션 해주셨어요! {content[5:].strip()}"
        elif content == "[구독]":
            user_input = f"{nickname}님이 구독해주셨어요!"
        elif content == "[구독 선물]":
            user_input = f"{nickname}님이 구독 선물을 해주셨어요!"
        else:
            user_input = f"{nickname}: {content}"

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
            result = await asyncio.wait_for(
                asyncio.shield(agent_task),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            slow_msg = random.choice(SLOW_RESPONSE_MESSAGES)
            print(f"[⏳] 응답 지연 60초 — 안내 멘트: {slow_msg}")
            await text_to_speech(slow_msg)
            try:
                result = await asyncio.wait_for(agent_task, timeout=120.0)
            except asyncio.TimeoutError:
                print(f"[⚠️] 응답 타임아웃 180초: {nickname}: {content}")
                if reader.controller and reader.controller.channel:
                    embed = discord.Embed(title="⚠️ 응답 타임아웃", color=discord.Color.orange())
                    embed.add_field(name="유저", value=nickname, inline=True)
                    embed.add_field(name="내용", value=content,  inline=True)
                    asyncio.run_coroutine_threadsafe(
                        reader.controller.channel.send(embed=embed),
                        reader.controller.bot.loop
                    )
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
            print(f"[Memory] fallback 응답 — 저장 스킵")

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
    controller.bridge = bridge
    reader.controller = controller

    # whisper 토글 함수 주입
    def set_whisper(v: bool):
        nonlocal whisper_enabled
        whisper_enabled = v
    controller.set_whisper = set_whisper

    bot_thread = threading.Thread(target=controller.run, daemon=True)
    bot_thread.start()
    print("[✅] 디스코드 봇 시작!")

    def handle_exit(signum, frame):
        update_obs("😴 가온이 자는 중...")
        os._exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # 게임 이벤트 감지 루프 시작
    asyncio.create_task(game_event_loop())

    if mode == "1":
        from voice.listener import voice_loop
        asyncio.create_task(voice_loop(handle_chat, name="개발자"))
        print("[✅] 음성 모드 시작!")
        await asyncio.Event().wait()
    else:
        await reader.start()


if __name__ == "__main__":
    asyncio.run(main())