# brain/llm_config.py
import os
from dotenv import load_dotenv
load_dotenv()

MODE = os.getenv("LLM_MODE", "groq")


def get_think_llm():
    if MODE == "school":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_THINK_MODEL"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=float(os.getenv("VTUBER_THINK_TEMP")),
            num_predict=4000,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=float(os.getenv("VTUBER_THINK_TEMP")),
            max_tokens=4000,
        )


def get_answer_llm():
    if MODE == "school":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_ANSWER_MODEL"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=float(os.getenv("VTUBER_ANSWER_TEMP")),
            num_predict=4000,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=float(os.getenv("VTUBER_ANSWER_TEMP")),
            max_tokens=4000,
        )


def get_wiki_llm():
    """Wiki 프로필 업데이트 전용 — 정확도 우선이라 temperature 0.1 고정"""
    if MODE == "school":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_ANSWER_MODEL"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=0.1,
            num_predict=4000,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=4000,
        )


def get_topic_llm():
    """토픽 관련 채팅 선택 전용 — 숫자 하나만 뽑으면 돼서 max_tokens 10 고정"""
    if MODE == "school":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_ANSWER_MODEL"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=0.1,
            num_predict=10,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=10,
        )


def get_think_llm_with_tools(think_llm, tools):
    if MODE == "school":
        return think_llm.bind_tools(tools)
    else:
        return think_llm.bind_tools(tools, parallel_tool_calls=False)