# control/discord_bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

class VTuberController:
    def __init__(self, reader, main_loop: asyncio.AbstractEventLoop):
        self.reader    = reader
        self.main_loop = main_loop
        self.channel   = None
        self.presenter = None

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
        self._setup()

    def _setup(self):
        reader = self.reader

        @self.bot.event
        async def on_ready():
            print(f"[디스코드] 봇 연결됨: {self.bot.user}")
            self.channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
            if self.channel:
                await self.channel.send("✅ 가온 봇 온라인!")

        @self.bot.command(name="status")
        async def status(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            buf  = len(reader.buffer)
            busy = "응답 중" if reader.is_busy else "대기 중"
            presenting = "발표 중" if self.presenter and self.presenter.running else "없음"
            await ctx.send(
                f"✅ 상태: 정상 운영중\n"
                f"💬 버퍼: {buf}개 채팅 대기\n"
                f"🎤 {busy}\n"
                f"📄 발표: {presenting}"
            )

        @self.bot.command(name="clear")
        async def clear(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            reader.buffer.clear()
            await ctx.send("🗑️ 버퍼 비웠어!")

        @self.bot.command(name="topic")
        async def topic(ctx, *, args=None):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not args:
                await ctx.send(f"현재 주제: {reader.topic or '자유 주제'}")
                return
            reader.topic = args
            await ctx.send(f"✅ 주제 변경: {reader.topic}")

        @self.bot.command(name="present")
        async def present(ctx, *, path=None):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not path:
                await ctx.send("사용법: /present [PDF경로]")
                return
            from brain.presenter import PDFPresenter
            self.presenter = PDFPresenter(callback=reader.callback)
            self.presenter.load(path)
            await ctx.send(f"📄 발표 시작!")
            asyncio.run_coroutine_threadsafe(
                self.presenter.present(interval=30),
                self.main_loop
            )

        @self.bot.command(name="pause")
        async def pause(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.presenter:
                self.presenter.pause()
                await ctx.send("⏸ 발표 일시정지!")
            else:
                await ctx.send("진행 중인 발표가 없어!")

        @self.bot.command(name="resume")
        async def resume(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.presenter:
                self.presenter.resume()
                await ctx.send("▶ 발표 재개!")
            else:
                await ctx.send("진행 중인 발표가 없어!")

        @self.bot.command(name="qa")
        async def qa(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.presenter:
                self.presenter.start_qa()
                await ctx.send("🙋 질문타임 시작!")
                asyncio.run_coroutine_threadsafe(
                    reader.callback("발표", "잠깐, 질문타임이야! 궁금한 거 있으면 채팅으로 물어봐 😊"),
                    self.main_loop
                )
            else:
                await ctx.send("진행 중인 발표가 없어!")

        @self.bot.command(name="qa_end")
        async def qa_end(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.presenter:
                self.presenter.end_qa()
                await ctx.send("✅ 질문타임 종료! 발표 재개!")
            else:
                await ctx.send("진행 중인 발표가 없어!")

        @self.bot.command(name="stop_present")
        async def stop_present(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.presenter:
                self.presenter.stop()
                await ctx.send("⏹ 발표 종료!")
            else:
                await ctx.send("진행 중인 발표가 없어!")

        @self.bot.command(name="stop")
        async def stop(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            await ctx.send("⏹ 방송 종료됨!")
            from brain.agent import update_obs
            update_obs("😴 가온이 자는 중...")
            await asyncio.sleep(1)
            os._exit(0)

        @self.bot.command(name="help")
        async def help_cmd(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            await ctx.send(
                "📋 명령어 목록\n\n"
                "🔧 기본\n"
                "/status - 현재 상태 확인\n"
                "/clear - 채팅 버퍼 비우기\n"
                "/topic [주제] - 방송 주제 변경\n"
                "/stop - 방송 종료\n\n"
                "📄 발표\n"
                "/present [PDF경로] - 발표 시작\n"
                "/pause - 발표 일시정지\n"
                "/resume - 발표 재개\n"
                "/qa - 질문타임 시작\n"
                "/qa_end - 질문타임 종료\n"
                "/stop_present - 발표 종료\n\n"
                "/help - 도움말"
            )

    def run(self):
        self.bot.run(DISCORD_TOKEN)