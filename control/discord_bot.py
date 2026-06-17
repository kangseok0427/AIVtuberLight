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
        self.reader      = reader
        self.main_loop   = main_loop
        self.channel     = None
        self.presenter   = None
        self.bridge      = None
        self.set_whisper = None  # main.py에서 주입

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
        self._setup()

    async def send_filter_alert(self, username: str, text: str, reason: str):
        if not self.channel:
            return
        embed = discord.Embed(title="🚨 채팅 필터 감지", color=discord.Color.red())
        embed.add_field(name="유저", value=username,      inline=True)
        embed.add_field(name="사유", value=reason,        inline=True)
        embed.add_field(name="내용", value=f"||{text}||", inline=False)
        asyncio.run_coroutine_threadsafe(
            self.channel.send(embed=embed),
            self.bot.loop
        )

    async def send_alert(self, title: str, message: str, color=discord.Color.orange()):
        if not self.channel:
            return
        embed = discord.Embed(title=title, description=message, color=color)
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
            news = f"ON ({reader.news_topic})" if reader.news_enabled else "OFF"
            presenting = (
                f"발표 중 ({self.presenter.current}/{len(self.presenter.slides)}장)"
                if self.presenter and self.presenter.running else "없음"
            )
            await ctx.send(
                f"✅ 상태: 정상 운영중\n"
                f"💬 버퍼: {buf}개 채팅 대기\n"
                f"🎤 {busy}\n"
                f"📰 뉴스 브리핑: {news}\n"
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

        # 뉴스 브리핑
        @self.bot.command(name="news_on")
        async def news_on(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            reader.news_enabled = True
            await ctx.send(f"📰 뉴스 브리핑 ON! 주제: {reader.news_topic}")

        @self.bot.command(name="news_off")
        async def news_off(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            reader.news_enabled = False
            await ctx.send("📰 뉴스 브리핑 OFF!")

        @self.bot.command(name="news_topic")
        async def news_topic(ctx, *, keyword=None):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not keyword:
                await ctx.send(f"현재 뉴스 주제: {reader.news_topic}\n사용법: /news_topic [키워드]")
                return
            reader.news_topic = keyword
            await ctx.send(f"📰 뉴스 주제 변경: {keyword}")

        # 흔들기
        @self.bot.command(name="shake_on")
        async def shake_on(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            reader.shake_enabled = True
            await ctx.send("💜 흔들기 ON! 채팅에 shake 치면 흔들려!")

        @self.bot.command(name="shake_off")
        async def shake_off(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            reader.shake_enabled = False
            await ctx.send("✅ 흔들기 OFF!")

        # 중얼거리기
        @self.bot.command(name="whisper_on")
        async def whisper_on(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.set_whisper:
                self.set_whisper(True)
            await ctx.send("💭 중얼거리기 ON!")

        @self.bot.command(name="whisper_off")
        async def whisper_off(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if self.set_whisper:
                self.set_whisper(False)
            await ctx.send("💭 중얼거리기 OFF!")

        # 발표
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
            self.presenter = PDFPresenter()
            count = self.presenter.load(path)
            await ctx.send(f"📄 발표 시작! 총 {count}장")
            asyncio.run_coroutine_threadsafe(
                self.presenter.present(callback=reader.callback),
                self.main_loop
            )

        @self.bot.command(name="qa_on")
        async def qa_on(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not self.presenter or not self.presenter.running:
                await ctx.send("진행 중인 발표가 없어!")
                return
            self.presenter.paused = True
            await ctx.send("⏸ 질문타임 시작! 채팅으로 질문해줘")

        @self.bot.command(name="qa_off")
        async def qa_off(ctx):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if not self.presenter or not self.presenter.running:
                await ctx.send("진행 중인 발표가 없어!")
                return
            self.presenter.paused = False
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

        @self.bot.command(name="mode")
        async def mode(ctx, *, m=None):
            if ctx.channel.id != DISCORD_CHANNEL_ID:
                return
            if m == "1":
                await ctx.send("🎤 음성 모드 — 아직 런타임 전환 미구현!")
            elif m == "2":
                await ctx.send("💬 채팅 모드 — 아직 런타임 전환 미구현!")
            else:
                await ctx.send("사용법: /mode 1 (음성) / /mode 2 (채팅)")

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
                "/say [내용] — 가온이에게 직접 전달 (최우선)\n"
                "/status — 현재 상태 확인\n"
                "/clear — 채팅 버퍼 비우기\n"
                "/topic [주제] — 방송 주제 변경\n"
                "/mode 1/2 — 음성/채팅 모드 전환\n"
                "/stop — 방송 종료\n\n"
                "📰 뉴스 브리핑\n"
                "/news_on — 정시 브리핑 시작\n"
                "/news_off — 정시 브리핑 중지\n"
                "/news_topic [키워드] — 뉴스 주제 변경\n\n"
                "💜 벌칙\n"
                "/shake_on — 채팅 shake 감지 ON\n"
                "/shake_off — 채팅 shake 감지 OFF\n\n"
                "💭 중얼거리기\n"
                "/whisper_on — 게임 이벤트 자동 반응 ON\n"
                "/whisper_off — 게임 이벤트 자동 반응 OFF\n\n"
                "📄 발표\n"
                "/present [PDF경로] — 발표 시작\n"
                "/qa_on — 질문타임 시작 (발표 일시정지)\n"
                "/qa_off — 질문타임 종료 (발표 재개)\n"
                "/stop_present — 발표 종료\n\n"
                "/help — 도움말"
            )

    def run(self):
        self.bot.run(DISCORD_TOKEN)