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
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=float(os.getenv("VTUBER_THINK_TEMP")),
            max_tokens=1024,
        )

def get_answer_llm():
    if MODE == "school":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_ANSWER_MODEL"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=float(os.getenv("VTUBER_ANSWER_TEMP")),
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=float(os.getenv("VTUBER_ANSWER_TEMP")),
            max_tokens=1024,
        )