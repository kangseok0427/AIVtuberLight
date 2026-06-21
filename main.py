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

WHISPER_INTERVAL_SEC = 300  # 5분마다 혼잣말

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
    from control.discord_bot import VTuberController

    # ── 초기화 ──────────────────────────────────────
    bridge = VTubeBridge()
    await bridge.connect()
    print(f"[✅] VTube Studio 연결 완료")

    print(f"\n{'='*40}\n  {NAME} 방송 시작!\n{'='*40}\n")

    main_loop       = asyncio.get_event_loop()
    whisper_enabled = True
    # ────────────────────────────────────────────────

    # ── 위스퍼 (혼잣말) ──────────────────────────────
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
    # ────────────────────────────────────────────────

    # ── 게임 이벤트 감지 루프 (클리어 알림 전용) ──────
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
                    print(f"[Game] 클리어 감지! {stage} {zone}구역 — 총 {cleared}클리어")
                    if reader.controller and reader.controller.channel:
                        embed = discord.Embed(title="🎉 던전 클리어!", color=discord.Color.green())
                        embed.add_field(name="스테이지", value=f"{stage} {zone}구역", inline=True)
                        embed.add_field(name="에피소드", value=f"{ep}판",             inline=True)
                        embed.add_field(name="총 클리어", value=f"{cleared}회",       inline=True)
                        asyncio.run_coroutine_threadsafe(
                            reader.controller.channel.send(embed=embed),
                            reader.controller.bot.loop
                        )
            except Exception:
                pass
    # ────────────────────────────────────────────────

    # ── 채팅 처리 ────────────────────────────────────
    async def handle_chat(nickname: str, content: str):
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

        # 60초 경과 시 안내 멘트
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
            print(f"[Memory] fallback — 저장 스킵")

        await asyncio.gather(
            bridge.trigger_and_reset(result["vtube_expression"], duration=5.0),
            text_to_speech(result["answer"])
        )
    # ────────────────────────────────────────────────

    async def handle_subscription(nickname: str, gift: bool = False):
        msg = f"{nickname}님 구독 선물 감사합니다!" if gift else f"{nickname}님 구독 감사합니다!"
        print(f"[구독] {msg}")
        update_obs(msg)
        await text_to_speech(msg)

    # ── 컨트롤러 & 봇 ────────────────────────────────
    reader     = ChzzkReader(on_chat_callback=handle_chat, on_subscription_callback=handle_subscription, topic="")
    controller = VTuberController(reader=reader, main_loop=main_loop)
    controller.bridge = bridge
    reader.controller = controller

    def set_whisper(v: bool):
        nonlocal whisper_enabled
        whisper_enabled = v
        print(f"[위스퍼] {'ON' if v else 'OFF'}")
    controller.set_whisper = set_whisper

    threading.Thread(target=controller.run, daemon=True).start()
    print("[✅] 디스코드 봇 시작!")
    # ────────────────────────────────────────────────

    def handle_exit(signum, frame):
        update_obs("😴 가온이 자는 중...")
        os._exit(0)

    signal.signal(signal.SIGINT,  handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # ── 실행 ─────────────────────────────────────────
    asyncio.create_task(game_event_loop())
    print("[✅] 게임 이벤트 감지 시작!")
    asyncio.create_task(whisper_loop())
    print("[✅] 위스퍼(혼잣말) 루프 시작!")

    await reader.start()
    # ────────────────────────────────────────────────


if __name__ == "__main__":
    asyncio.run(main())