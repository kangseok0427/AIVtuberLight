# brain/agent.py
import os
import re
import asyncio
import json
import random
import threading
from dotenv import load_dotenv
from typing import TypedDict, Literal, Annotated
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from brain.llm_config import get_think_llm, get_answer_llm, get_think_llm_with_tools

from brain.tools import SearchTool, MemoryTool, CodeReaderTool, EternalReturnTool
from tts.tts import text_to_speech

load_dotenv()

NAME = os.getenv("VTUBER_NAME")

# 툴 인스턴스
search_tool   = SearchTool().build()
memory_tool   = MemoryTool()
memory_search = memory_tool.build()
code_reader   = CodeReaderTool().build()
er_tool       = EternalReturnTool().build()
tools         = [search_tool, memory_search, code_reader, er_tool]

# LLM
llm_think            = get_think_llm()
llm_answer           = get_answer_llm()
llm_think_with_tools = get_think_llm_with_tools(llm_think, tools)


def load_prompt(filename: str, **kwargs) -> str:
    with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
        return f.read().format(**kwargs)


def _get_memory_context(limit: int) -> str:
    try:
        all_results = memory_tool.db.get()
        if not all_results or not all_results['documents']:
            return ""
        paired = list(zip(all_results['documents'], all_results['metadatas']))
        paired.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
        recent = paired[:limit]
        recent.reverse()
        return "\n\n[최근 대화 기록]\n" + "\n".join(f"- {doc}" for doc, _ in recent)
    except Exception as e:
        print(f"[Memory] 컨텍스트 로드 실패: {e}")
        return ""


def load_game_context() -> str:
    try:
        with open("/Users/lucas/MechanicoC/checkpoints/mechanico_status.json", "r") as f:
            state = json.load(f)
        result = load_prompt("game.txt",
            episode=state.get("episode", 0),
            total_steps=state.get("total_steps", 0),
            stage=state.get("stage", "?"),
            zone=state.get("zone", 0),
            cleared=state.get("cleared", 0),
            gold=state.get("gold", 0),
            party_alive=", ".join(state.get("party_alive", [])) or "없음",
            party_ko=", ".join(state.get("party_ko", [])) or "없음",
            loss=round(state.get("loss", 0), 4),
            epsilon=round(state.get("epsilon", 1), 2),
            avg_reward=round(state.get("avg_reward", 0), 3),
            event=state.get("event", "없음"),
        )
        print(f"[Game] 컨텍스트 로드됨: ep={state.get('episode')} stage={state.get('stage')} event={state.get('event')}")
        return result
    except Exception as e:
        print(f"[Game] 컨텍스트 로드 실패: {e}")
        return ""


class VTuberState(TypedDict):
    user_input:       str
    messages:         Annotated[list, add_messages]
    emotion:          str
    vtube_expression: str | None
    answer:           str
    is_fallback:      bool


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

FALLBACK_RESPONSES = [
    "잠깐, 나 지금 좀 바빠.. 🙄 [EMOTION:neutral]",
    "음.. 지금은 대답하기 싫은데 💢 [EMOTION:angry]",
    "나중에 물어봐.. 지금 생각하는 중이야 🤔 [EMOTION:thinking]",
    "흥, 굳이 지금 대답해야 해? [EMOTION:neutral]",
    "어.. 잠깐만 있어봐 💜 [EMOTION:nervous]",
]


def detect_emotion(answer: str) -> tuple[str, str]:
    match = re.search(r'\[EMOTION:\s*(\w+)\s*\]', answer)
    emotion = match.group(1) if match else "neutral"
    clean_answer = re.sub(r'\[EMOTION:\s*\w+\s*\]', '', answer).strip()
    return emotion, clean_answer


def update_obs(text: str):
    try:
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
    except Exception as e:
        print(f"[OBS] 오버레이 업데이트 실패: {e}")


def think_node(state: VTuberState) -> VTuberState:
    print(f"[Think] 시작: '{state['user_input'][:30]}'")
    memory_context = _get_memory_context(limit=3)

    system = SystemMessage(content=load_prompt("think.txt", NAME=NAME))
    human  = HumanMessage(content=state["user_input"] + memory_context)

    try:
        response = llm_think_with_tools.invoke([system, human])
        print(f"[Think] 완료 — tool_calls: {bool(getattr(response, 'tool_calls', None))}")
    except Exception as e:
        print(f"[Think] 툴 오류, 툴 없이 재시도: {e}")
        response = llm_think.invoke([system, human])

    return {**state, "messages": [system, human, response]}


def answer_node(state: VTuberState) -> VTuberState:
    print(f"[Answer] 시작")
    is_fallback = False

    try:
        game_context = load_game_context()
        system = SystemMessage(
            content=load_prompt("answer.txt", NAME=NAME) + "\n\n" + game_context
        )

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

        user_content += _get_memory_context(limit=3)

        human    = HumanMessage(content=user_content)
        response = llm_answer.invoke([system, human])
        answer   = response.content
        print(f"[Answer] LLM 응답 완료")

        clarification = re.search(r'\[NEED_CLARIFICATION:(.*?)\]', answer)
        if clarification:
            question = clarification.group(1).strip()
            answer = question + " [EMOTION:confused]"

    except Exception as e:
        print(f"[Answer] 오류 발생 — fallback 사용: {e}")
        answer = random.choice(FALLBACK_RESPONSES)
        is_fallback = True

    emotion, clean_answer = detect_emotion(answer)
    vtube_expression = EMOTION_MAP.get(emotion, None)
    print(f"[Answer] 감정: {emotion} / 표정: {vtube_expression} / fallback: {is_fallback}")

    update_obs(clean_answer)

    return {**state, "answer": clean_answer, "emotion": emotion, "vtube_expression": vtube_expression, "is_fallback": is_fallback}


def should_use_tools(state: VTuberState) -> Literal["tools", "answer"]:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        print(f"[Graph] 툴 사용: {last_msg.tool_calls}")
        return "tools"
    print(f"[Graph] 툴 미사용 → answer")
    return "answer"


graph = StateGraph(VTuberState)
graph.add_node("think",  think_node)
graph.add_node("tools",  ToolNode(tools))
graph.add_node("answer", answer_node)
graph.set_entry_point("think")
graph.add_conditional_edges("think", should_use_tools, {"tools": "tools", "answer": "answer"})
graph.add_edge("tools", "answer")
graph.add_edge("answer", END)

agent = graph.compile()