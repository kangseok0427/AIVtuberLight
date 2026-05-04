# chat/reader.py
import asyncio
import os
import time
import random
from dotenv import load_dotenv
from chzzkpy import ChatClient
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

CHANNEL_ID = os.getenv("CHZZK_CHANNEL_ID")
NID_AUT    = os.getenv("CHZZK_NID_AUT")
NID_SES    = os.getenv("CHZZK_NID_SES")
EXPIRE_SEC = 30
BUFFER_MAX = 20

class ChzzkReader:
    def __init__(self, on_chat_callback, on_subscription_callback=None, topic: str = ""):
        self.callback              = on_chat_callback
        self.subscription_callback = on_subscription_callback
        self.buffer                = []
        self.is_busy               = False
        self.topic                 = topic
        self.llm                   = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=10,
        )
        self.client = ChatClient(CHANNEL_ID)
        self.client.login(NID_AUT, NID_SES)