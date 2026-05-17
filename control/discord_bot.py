# control/discord_bot.py
import os
import re
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

FILTER_PATTERNS = [
    r"[시씨][0이발팔ㅂ]",
    r"[ㅅs][ㅣi][0o][ㅂb]",
    r"ㅅㅂ|ㅄ|ㄱㅅ|ㅈㄹ|ㄷㅊ",
    r"좆|보지|씹|잡년|창녀",
    r"(.)\1{4,}",
    r"https?://\S+\.(xyz|tk|ml|ga|cf)",
]

COMPILED_FILTERS = [re.compile(p, re.IGNORECASE) for p in FILTER_PATTERNS]

def check_chat(username: str, text: str) -> str | None:
    for pattern in COMPILED_FILTERS:
        m = pattern.search(text)
        if m:
            return f"패턴 매칭: `{m.group()}`"
    return None


class VTuberController:
    def __init__(self, reader, main_loop: asyncio.AbstractEventLoop):
        self.reader     = reader
        self.main_loop  = main_loop
        self.channel    = None
        self.presenter  = None

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
        self._setup()

    async def send_filter_alert(self, username: str, text: str, reason: str):
        if not self.channel:
            return
        embed = discord.Embed(
            title="🚨 채팅 필터 감지",
            color=discord.Color.red()
        )
        embed.add_field(name="유저", value=username, inline=True)
        embed.add_field(name="사유", value=reason, inline=True)
        embed.add_field(name="내용", value=f"||{text}||", inline=False)
        asyncio.run_coroutine_threadsafe(
            self.channel.send(embed=embed),
            self.bot.loop
        )

    def _setup(self):
        reader = self.reader

        @self.bot.event
        async def on_ready():
            print(f"[디스코드] 봇 연결됨: {self.bot.user}")
            self.channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
            if self.channel:
                await self.channel.send("✅ 가온 봇 온라인!")

        @self.bot.command(name="say")
        async def say(ctx, *, text=None):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not text:
                await ctx.send("사용법: /say [내용]")
                return
            import time
            reader.priority_buffer.append(("디스코드", text, time.time()))
            await ctx.send(f"📢 우선 전달: `{text}`")

        @self.bot.command(name="status")
        async def status(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            buf  = len(reader.buffer)
            busy = "응답 중" if reader.is_busy else "대기 중"
            presenting = f"발표 중 ({self.presenter.current}/{len(self.presenter.slides)}장)" if self.presenter and self.presenter.running else "없음"
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
            if not os.path.exists(path):
                await ctx.send(f"❌ 파일 없음: `{path}`")
                return

            from brain.presenter import PDFPresenter
            self.presenter = PDFPresenter(reader=reader, main_loop=self.main_loop)
            count = self.presenter.load(path)
            await ctx.send(f"📄 발표 시작! 총 {count}장")

            asyncio.run_coroutine_threadsafe(
                self.presenter.present(callback=reader.callback),
                self.main_loop
            )

        @self.bot.command(name="qa")
        async def qa(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not self.presenter or not self.presenter.running:
                await ctx.send("진행 중인 발표가 없어!")
                return
            paused = self.presenter.toggle_pause()
            if paused:
                await ctx.send("⏸ 질문타임! 채팅으로 질문해줘")
            else:
                await ctx.send("▶ 발표 재개!")

        @self.bot.command(name="stop_present")
        async def stop_present(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not self.presenter:
                await ctx.send("진행 중인 발표가 없어!")
                return
            self.presenter.stop()
            await ctx.send("⏹ 발표 종료!")

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
                "/say [내용] - 가온이에게 직접 전달 (최우선)\n"
                "/status - 현재 상태 확인\n"
                "/clear - 채팅 버퍼 비우기\n"
                "/topic [주제] - 방송 주제 변경\n"
                "/stop - 방송 종료\n\n"
                "📄 발표\n"
                "/present [PDF경로] - 발표 시작\n"
                "/qa - 질문타임 토글 (일시정지/재개)\n"
                "/stop_present - 발표 종료\n\n"
                "/help - 도움말"
            )

    def run(self):
        self.bot.run(DISCORD_TOKEN)