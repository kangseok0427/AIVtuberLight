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
            await ctx.send(
                f"✅ 상태: 정상 운영중\n"
                f"💬 버퍼: {buf}개 채팅 대기\n"
                f"🎤 {busy}"
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
                "📋 명령어 목록\n"
                "/status - 현재 상태 확인\n"
                "/clear - 채팅 버퍼 비우기\n"
                "/topic [주제] - 방송 주제 변경\n"
                "/stop - 방송 종료\n"
                "/help - 도움말"
            )

    def run(self):
        self.bot.run(DISCORD_TOKEN)