# brain/agent.py
import os
import re
import asyncio
from dotenv import load_dotenv
from typing import TypedDict, Literal, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages

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
llm_think = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=T_THINK,
    max_tokens=1024,
)
llm_answer = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=T_ANSWER,
    max_tokens=1024,
)
llm_think_with_tools = llm_think.bind_tools(tools, parallel_tool_calls=False)

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
    response = llm_think_with_tools.invoke(messages)
    return {**state, "messages": [system, human, response]}

# 노드 2 - answer
def answer_node(state: VTuberState) -> VTuberState:
    system = SystemMessage(content=load_prompt("answer.txt", NAME=NAME))

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

    # 되묻기 처리
    clarification = re.search(r'\[NEED_CLARIFICATION:(.*?)\]', answer)
    if clarification:
        question = clarification.group(1).strip()
        answer = question + " [EMOTION:confused]"

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
        return "tools"
    return "answer"

graph.add_conditional_edges("think", should_use_tools, {"tools": "tools", "answer": "answer"})
graph.add_edge("tools", "answer")
graph.add_edge("answer", END)

agent = graph.compile()