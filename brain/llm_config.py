# brain/llm_config.py
import os
from dotenv import load_dotenv
load_dotenv()

MODE = os.getenv("LLM_MODE", "school")


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
            model="qwen/qwen3.6-27b",
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
            model="qwen/qwen3.6-27b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=float(os.getenv("VTUBER_ANSWER_TEMP")),
            max_tokens=4000,
        )


def get_wiki_llm():
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
            model="openai/gpt-oss-20b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=4000,
        )


def get_topic_llm():
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
            model="openai/gpt-oss-20b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=10,
        )


def get_think_llm_with_tools(think_llm, tools):
    if MODE == "school":
        return think_llm.bind_tools(tools)
    else:
        return think_llm.bind_tools(tools, parallel_tool_calls=False)


def get_code_llm():
    """webinfection 전용 — qwen3.6-27b 메인, gpt-oss-20b 폴백"""
    from langchain_groq import ChatGroq

    class CodeLLM:
        def __init__(self):
            self.primary = ChatGroq(
                model="qwen/qwen3.6-27b",
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0.2,
                max_tokens=4000,
            )
            self.fallback = ChatGroq(
                model="openai/gpt-oss-20b",
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0.2,
                max_tokens=4000,
            )

        def invoke(self, *args, **kwargs):
            try:
                return self.primary.invoke(*args, **kwargs)
            except Exception as e:
                err = str(e)
                if "429" in err or "rate" in err.lower():
                    print(f"[CodeLLM] qwen 한도 초과 — gpt-oss-20b 폴백")
                    try:
                        return self.fallback.invoke(*args, **kwargs)
                    except Exception as e2:
                        if "429" in str(e2) or "rate" in str(e2).lower():
                            raise RuntimeError("ALL_MODELS_EXHAUSTED") from e2
                        raise e2
                raise

        def bind_tools(self, *args, **kwargs):
            return self.primary.bind_tools(*args, **kwargs)

    return CodeLLM()


def get_code_llm_with_tools(tools):
    llm = get_code_llm()
    return llm.bind_tools(tools, parallel_tool_calls=False)