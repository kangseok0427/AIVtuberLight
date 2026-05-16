# brain/agent.py
import os
import re
import asyncio
import json
from dotenv import load_dotenv
from typing import TypedDict, Literal, Annotated
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from brain.llm_config import get_think_llm, get_answer_llm, get_think_llm_with_tools

from brain.tools import SearchTool, MemoryTool
from tts.tts import text_to_speech

load_dotenv()

NAME     = os.getenv("VTUBER_NAME")
T_THINK  = float(os.getenv("VTUBER_THINK_TEMP"))
T_ANSWER = float(os.getenv("VTUBER_ANSWER_TEMP"))

# 툴 인스턴스
search_tool   = SearchTool().build()
memory_tool   = MemoryTool()
memory_search = memory_tool.build()
tools         = [search_tool, memory_search]

# LLM
llm_think = get_think_llm()
llm_answer = get_answer_llm()
llm_think_with_tools = get_think_llm_with_tools(llm_think, tools)

# 프롬프트 로더
def load_prompt(filename: str, **kwargs) -> str:
    with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
        return f.read().format(**kwargs)

# 상태 정의
class VTuberState(TypedDict):
    user_input:       str
    messages:         Annotated[list, add_messages]
    emotion:          str
    vtube_expression: str | None
    answer:           str

# 감정 맵
EMOTION_MAP = {
    "happy":     "Exp7 Laugh",
    "love":      "Exp2 Heart",
    "excited":   "Exp1 Sparkling",
    "surprised": "Exp6 Surprise",
    "confused":  "Exp3 Confused",
    "nervous":   "Exp10 Nervous",
    "sad":       "Exp5 FaceShadow",
    "angry":     "Exp8 Angry",
    "thinking":  "Exp9 Loading",
    "neutral":   None
}

def detect_emotion(answer: str) -> tuple[str, str]:
    match = re.search(r'\[EMOTION:(\w+)\]', answer)
    emotion = match.group(1) if match else "neutral"
    clean_answer = re.sub(r'\[EMOTION:\w+\]', '', answer).strip()
    return emotion, clean_answer

def update_obs(text: str):
    with open("obs/overlay.html", "r", encoding="utf-8") as f:
        overlay = f.read()
    updated = re.sub(
        r'<div id="message">.*?</div>',
        f'<div id="message">{text}</div>',
        overlay,
        flags=re.DOTALL
    )
    with open("obs/overlay.html", "w", encoding="utf-8") as f:
        f.write(updated)

# 노드 1 - think
def think_node(state: VTuberState) -> VTuberState:
    all_results = memory_tool.db.get()
    memory_context = ""

    if all_results and all_results['documents']:
        paired = list(zip(all_results['documents'], all_results['metadatas']))
        paired.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
        recent = paired[:3]
        recent.reverse()
        memory_context = "\n\n[최근 대화 기록]\n" + "\n".join(
            f"- {doc}" for doc, _ in recent
        )

    system = SystemMessage(content=load_prompt("think.txt", NAME=NAME))
    user_content = state["user_input"] + memory_context
    human = HumanMessage(content=user_content)
    messages = [system, human]

    try:
        response = llm_think_with_tools.invoke(messages)
    except Exception as e:
        print(f"[⚠️] Think 툴 오류, 툴 없이 재시도: {e}")
        response = llm_think.invoke(messages)

    return {**state, "messages": [system, human, response]}

# 노드 2 - answer
def load_snake_context() -> str:
    try:
        import json
        with open("/Users/lucas/snake_ai/game_state.json", "r") as f:
            state = json.load(f)
        return load_prompt("snake.txt",
            episode=state["episode"],
            score=state["score"],
            best_score=state["best_score"],
            loss=round(state["loss"], 4),
            epsilon=round(state["epsilon"], 2),
            avg_score=state["avg_score"],
            alive="살아있음" if state["alive"] else "죽음",
            event=state.get("event", "null")
        )
    except:
        return ""

def answer_node(state: VTuberState) -> VTuberState:
    try:
        snake_context = load_snake_context()
        system = SystemMessage(content=load_prompt("answer.txt", NAME=NAME) + "\n\n" + snake_context)

        tool_results = ""
        for msg in state["messages"]:
            if hasattr(msg, "type") and msg.type == "tool":
                tool_results += f"\n{msg.content}"

        user_content = ""
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                user_content = msg.content
                break

        if tool_results:
            user_content += f"\n\n[검색 결과]{tool_results}"

        human = HumanMessage(content=user_content)
        response = llm_answer.invoke([system, human])
        answer = response.content

        clarification = re.search(r'\[NEED_CLARIFICATION:(.*?)\]', answer)
        if clarification:
            question = clarification.group(1).strip()
            answer = question + " [EMOTION:confused]"

    except Exception as e:
        print(f"[⚠️] API 오류 (fallback 사용): {e}")
        import random
        answer = random.choice([
            "잠깐, 나 지금 좀 바빠.. 🙄 [EMOTION:neutral]",
            "음.. 지금은 대답하기 싫은데 💢 [EMOTION:angry]",
            "나중에 물어봐.. 지금 생각하는 중이야 🤔 [EMOTION:thinking]",
            "흥, 굳이 지금 대답해야 해? [EMOTION:neutral]",
            "어.. 잠깐만 있어봐 💜 [EMOTION:nervous]",
        ])

    emotion, clean_answer = detect_emotion(answer)
    vtube_expression = EMOTION_MAP.get(emotion, None)

    update_obs(clean_answer)
    memory_tool.save(state["user_input"], clean_answer)

    return {**state, "answer": clean_answer, "emotion": emotion, "vtube_expression": vtube_expression}
# 그래프 조립
graph = StateGraph(VTuberState)
graph.add_node("think",  think_node)
graph.add_node("tools",  ToolNode(tools))
graph.add_node("answer", answer_node)
graph.set_entry_point("think")

def should_use_tools(state: VTuberState) -> Literal["tools", "answer"]:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        print(f"[도구 사용] {last_msg.tool_calls}")
        return "tools"
    return "answer"

graph.add_conditional_edges("think", should_use_tools, {"tools": "tools", "answer": "answer"})
graph.add_edge("tools", "answer")
graph.add_edge("answer", END)

agent = graph.compile()