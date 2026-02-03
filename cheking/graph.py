import json
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

def run_with_trace(app, initial_state):
    trace = {
        "user_input": initial_state["messages"][0].content,
        "steps": [],
        "final_answer": None,
    }

    for step in app.stream(initial_state, {"recursion_limit": 50}):
        for node_name, state in step.items():
            step_entry = {
                "node": node_name,
                "sender": state.get("sender"),
                "messages": [],
            }

            for msg in state.get("messages", []):
                if isinstance(msg, HumanMessage):
                    step_entry["messages"].append({
                        "type": "human",
                        "content": msg.content,
                    })

                elif isinstance(msg, AIMessage):
                    step_entry["messages"].append({
                        "type": "ai",
                        "content": msg.content,
                        "tool_calls": msg.tool_calls or [],
                    })

                    # capture final answer
                    if msg.content and "FINAL ANSWER" in msg.content:
                        trace["final_answer"] = msg.content

                elif isinstance(msg, ToolMessage):
                    step_entry["messages"].append({
                        "type": "tool",
                        "tool_name": msg.name,
                        "tool_call_id": msg.tool_call_id,
                        "result": msg.content,
                    })

            trace["steps"].append(step_entry)

    # fallback final answer
    if not trace["final_answer"]:
        trace["final_answer"] = trace["steps"][-1]["messages"][-1].get("content")

    return trace
                                                                                                                                                                                                                                                                                                       # graph.py
import json
from typing import TypedDict, Sequence
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)

from agent import (
    AgentState,
    inspiration_node,
    news_node,
    places_node,
    tool_node,
)

# ======================================================
# Router
# ======================================================
def router(state: AgentState):
    last = state["messages"][-1]

    # If model requested a tool
    if getattr(last, "tool_calls", None):
        return "tools"

    # Stop condition
    if isinstance(last, AIMessage) and "FINAL ANSWER" in last.content:
        return "end"

    # Agent routing
    if state["sender"] == "inspiration":
        return "news"

    if state["sender"] == "news":
        return "places"

    return "inspiration"


# ======================================================
# Build Graph
# ======================================================
graph = StateGraph(AgentState)

graph.add_node("inspiration", inspiration_node)
graph.add_node("news", news_node)
graph.add_node("places", places_node)
graph.add_node("tools", tool_node)

graph.set_entry_point("inspiration")

graph.add_conditional_edges(
    "inspiration",
    router,
    {
        "news": "news",
        "tools": "tools",
        "end": END,
    },
)

graph.add_conditional_edges(
    "news",
    router,
    {
        "places": "places",
        "tools": "tools",
        "end": END,
    },
)

graph.add_conditional_edges(
    "places",
    router,
    {
        "inspiration": "inspiration",
        "tools": "tools",
        "end": END,
    },
)

graph.add_conditional_edges(
    "tools",
    lambda s: s["sender"],
    {
        "inspiration": "inspiration",
        "news": "news",
        "places": "places",
    },
)

app = graph.compile()


import json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

def run_node_by_node(app, initial_state):
    for step in app.stream(initial_state, {"recursion_limit": 50}):
        for node_name, state in step.items():
            node_output = {
                "node": node_name,
                "sender": state.get("sender"),
                "messages": [],
            }

            for msg in state.get("messages", []):
                if isinstance(msg, HumanMessage):
                    node_output["messages"].append({
                        "type": "human",
                        "content": msg.content,
                    })
                elif isinstance(msg, AIMessage):
                    node_output["messages"].append({
                        "type": "ai",
                        "content": msg.content,
                        "tool_calls": msg.tool_calls or [],
                    })
                elif isinstance(msg, ToolMessage):
                    node_output["messages"].append({
                        "type": "tool",
                        "tool_name": msg.name,
                        "tool_call_id": msg.tool_call_id,
                        "result": msg.content,
                    })

            # Print the node output immediately in JSON
            print(json.dumps(node_output, indent=2))

# ===========================
# Example usage
# ===========================
if __name__ == "__main__":
    initial_state = {
        "messages": [HumanMessage(content="plan a three day trip for india")],
        "sender": "user",
    }

    run_node_by_node(app, initial_state)
