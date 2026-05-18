# chat/reader.py
import asyncio
import aiohttp
import httpx
import json
import os
import re
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from control.discord_bot import check_chat

load_dotenv()

CHANNEL_ID = os.getenv("CHZZK_CHANNEL_ID")
NID_AUT    = os.getenv("CHZZK_NID_AUT")
NID_SES    = os.getenv("CHZZK_NID_SES")
EXPIRE_SEC = 30
BUFFER_MAX = 20

API_BASE  = "https://api.chzzk.naver.com"
GAME_BASE = "https://comm-api.game.naver.com/nng_main"
WS_URL    = "wss://kr-ss1.chat.naver.com/chat"

def _is_emoji_only(text: str) -> bool:
    cleaned = re.sub(r'\{:[^}]+:\}', '', text).strip()
    if not cleaned:
        return True
    return not bool(re.search(r'[ㄱ-ㅎㅏ-ㅣ가-힣a-zA-Z0-9]', cleaned))


class ChzzkReader:
    def __init__(self, on_chat_callback, on_subscription_callback=None, topic: str = ""):
        self.callback              = on_chat_callback
        self.subscription_callback = on_subscription_callback
        self.buffer                = []
        self.priority_buffer       = []
        self.is_busy               = False
        self.topic                 = topic
        self.controller            = None
        self.news_enabled          = False
        self.news_topic            = "IT 기술"
        self.last_news_hour        = -1
        self.llm                   = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=10,
        )
        self.cookies = {
            "NID_AUT": NID_AUT,
            "NID_SES": NID_SES,
        }
        self.chat_channel_id = None
        self.access_token    = None

    async def _get_chat_channel_id(self) -> str:
        url = f"{API_BASE}/service/v2/channels/{CHANNEL_ID}/live-detail"
        print(f"[치지직] 채널 정보 요청 중...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://chzzk.naver.com",
        }
        async with httpx.AsyncClient(
            cookies=self.cookies,
            headers=headers,
            timeout=15,
            follow_redirects=True
        ) as client:
            resp = await client.get(url)
            print(f"[치지직] 응답 코드: {resp.status_code}")
            data = resp.json()
            channel_id = data["content"]["chatChannelId"]
            print(f"[치지직] 채팅 채널 ID: {channel_id}")
            return channel_id

    async def _get_access_token(self) -> str:
        url = f"{GAME_BASE}/v1/chats/access-token?channelId={self.chat_channel_id}&chatType=STREAMING"
        async with httpx.AsyncClient(
            cookies=self.cookies,
            timeout=15,
            follow_redirects=True
        ) as client:
            resp = await client.get(url)
            data = resp.json()
            token = data["content"]["accessToken"]
            return token

    async def _connect_websocket(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                print("[치지직] WebSocket 연결됨!")
                connect_msg = {
                    "ver": "2",
                    "cmd": 100,
                    "svcid": "game",
                    "cid": self.chat_channel_id,
                    "bdy": {
                        "uid": None,
                        "devType": 2001,
                        "accTkn": self.access_token,
                        "auth": "READ"
                    },
                    "tid": 1
                }
                await ws.send_str(json.dumps(connect_msg))

                async def ping_loop():
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send_str(json.dumps({"ver": "2", "cmd": 0}))
                        except:
                            break

                asyncio.create_task(ping_loop())

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(json.loads(msg.data))
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        print("[치지직] WebSocket 닫힘")
                        break

    async def _handle_message(self, data: dict):
        cmd = data.get("cmd")

        if cmd == 93101:
            for chat in data.get("bdy", []):
                try:
                    profile  = json.loads(chat.get("profile", "{}"))
                    nickname = profile.get("nickname", "익명")
                    content  = chat.get("msg", "")
                    if not content:
                        return

                    if _is_emoji_only(content):
                        print(f"[필터] 이모티콘: {nickname}: {content}")
                        return

                    reason = check_chat(nickname, content)
                    if reason:
                        print(f"[필터] {nickname}: {content} ({reason})")
                        if self.controller:
                            asyncio.create_task(
                                self.controller.send_filter_alert(nickname, content, reason)
                            )
                        return

                    print(f"[채팅] {nickname}: {content}")
                    if len(self.buffer) >= BUFFER_MAX:
                        self.buffer.pop(0)
                    self.buffer.append((nickname, content, time.time()))
                except Exception as e:
                    print(f"[채팅 파싱 오류] {e}")

        elif cmd == 93102:
            for donation in data.get("bdy", []):
                try:
                    profile  = json.loads(donation.get("profile", "{}"))
                    nickname = profile.get("nickname", "익명")
                    amount   = donation.get("extras", {}).get("payAmount", 0)
                    content  = donation.get("msg", "")
                    print(f"[도네] {nickname}: {amount}원 {content}")
                    self.buffer.insert(0, (
                        nickname,
                        f"[도네 {amount}원] {content}" if content else f"[도네 {amount}원]",
                        time.time()
                    ))
                except Exception as e:
                    print(f"[도네 파싱 오류] {e}")

    async def _run_news_briefing(self):
        print(f"[뉴스] 브리핑 시작: {self.news_topic}")
        prompt = (
            f"[뉴스 브리핑 시간]\n"
            f"지금 {self.news_topic} 관련 최신 뉴스 3~5개 검색해서 "
            f"아나운서처럼 핵심만 브리핑해줘. "
            f"각 뉴스마다 짧게 한마디 코멘트도 추가해줘."
        )
        self.is_busy = True
        try:
            await self.callback("뉴스", prompt)
        finally:
            self.is_busy = False

    def _pick_by_topic_sync(self) -> tuple:
        candidates = self.buffer[-5:]
        chat_list = "\n".join(
            f"{i+1}. {nick}: {content}"
            for i, (nick, content, _) in enumerate(candidates)
        )
        system = SystemMessage(content="""You are a chat selector for a VTuber stream.
Given a list of chat messages and a topic, select the most relevant message number.
Respond with ONLY a single number. Nothing else.""")
        human = HumanMessage(content=f"""Topic: {self.topic}

Chat messages:
{chat_list}

Which message number is most relevant to the topic? Reply with just the number.""")
        try:
            response = self.llm.invoke([system, human])
            idx = int(response.content.strip()) - 1
            idx = max(0, min(idx, len(candidates) - 1))
            return candidates[idx]
        except:
            return random.choice(candidates)

    async def pick_and_respond(self):
        while True:
            await asyncio.sleep(0.5)

            # ── 정시 뉴스 브리핑 체크 ─────────────────────
            if self.news_enabled and not self.is_busy:
                now = datetime.now()
                if now.minute == 0 and now.hour != self.last_news_hour:
                    self.last_news_hour = now.hour
                    asyncio.create_task(self._run_news_briefing())
                    continue
            # ───────────────────────────────────────────────

            if self.is_busy:
                continue

            if self.priority_buffer:
                nickname, content, _ = self.priority_buffer.pop(0)
                print(f"[우선처리] {nickname}: {content}")
                self.is_busy = True
                asyncio.create_task(self._run_callback(nickname, content))
                continue

            if not self.buffer:
                continue

            now_ts = time.time()
            self.buffer = [
                item for item in self.buffer
                if now_ts - item[2] <= EXPIRE_SEC
            ]

            if not self.buffer:
                continue

            if self.topic and len(self.buffer) > 1:
                loop = asyncio.get_event_loop()
                picked = await loop.run_in_executor(None, self._pick_by_topic_sync)
            else:
                picked = random.choice(self.buffer)

            self.buffer.clear()
            nickname, content, _ = picked
            print(f"[응답 중] {nickname}: {content}")

            self.is_busy = True
            asyncio.create_task(self._run_callback(nickname, content))

    async def _run_callback(self, nickname: str, content: str):
        try:
            await self.callback(nickname, content)
        finally:
            self.is_busy = False

    async def start(self):
        asyncio.create_task(self.pick_and_respond())
        first = True
        while True:
            try:
                self.chat_channel_id = await self._get_chat_channel_id()
                self.access_token    = await self._get_access_token()
                await self._connect_websocket()
            except Exception as e:
                if first:
                    first = False
                print("[치지직] 재연결 중...")
                await asyncio.sleep(10)