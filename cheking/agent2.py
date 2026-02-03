# ======================================================
# agent2_chatgroq_table.py
# ======================================================
import os
import json
import functools
from typing import Annotated, Sequence
import pandas as pd

from langchain_core.messages import AIMessage, BaseMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_tavily import TavilySearch
from langchain_experimental.utilities import PythonREPL
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq

# ----------------------------
# Environment Keys
# ----------------------------
os.environ["TAVILY_API_KEY"] = "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"
CHAT_GROQ_API_KEY = "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"

# ======================================================
# Tools
# ======================================================
tavily_tool = TavilySearch(max_results=3)
repl = PythonREPL()

@tool
def python_repl(code: Annotated[str, "Python code to execute for charts."]):
    """Execute Python code and return stdout for chart generation."""
    try:
        result = repl.run(code)
        return f"Successfully executed:\n`python\n{code}\n`\nStdout: {result}"
    except Exception as e:
        return f"Execution failed: {repr(e)}"

tools = [tavily_tool, python_repl]

# ======================================================
# Agent State
# ======================================================
from typing import TypedDict, Sequence

class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    sender: str

# ======================================================
# LLM Setup (ChatGroq)
# ======================================================
llm = ChatGroq(
    api_key=CHAT_GROQ_API_KEY,
    model="llama-3.1-8b-instant",
    temperature=0,
)

# ======================================================
# Agent creation helper (concise)
# ======================================================
def create_agent(llm, system_message: str):
    """
    Returns a callable agent that uses ChatGroq for concise responses.
    """
    def agent_callable(state: AgentState):
        user_input = "\n".join([msg.content for msg in state["messages"]])
        full_input = f"{system_message}\nRespond concisely in 50-100 words.\n{user_input}"

        response_obj = llm.invoke(input=full_input)

        # Extract actual string content
        if hasattr(response_obj, "content"):
            content_str = response_obj.content
        elif isinstance(response_obj, str):
            content_str = response_obj
        else:
            content_str = str(response_obj)

        return HumanMessage(content=content_str, name="agent")

    return agent_callable

# ======================================================
# Chart Agent (returns Pandas table instead of charts)
# ======================================================
def create_table_agent(llm, system_message: str):
    """
    Returns a callable agent that produces a Pandas table instead of charts.
    """
    def agent_callable(state: AgentState):
        user_input = "\n".join([msg.content for msg in state["messages"]])
        full_input = f"{system_message}\nReturn the data as a Pandas DataFrame dictionary.\n{user_input}"

        response_obj = llm.invoke(input=full_input)

        if hasattr(response_obj, "content"):
            content_str = response_obj.content
        elif isinstance(response_obj, str):
            content_str = response_obj
        else:
            content_str = str(response_obj)

        # Try to convert response to Pandas DataFrame
        try:
            # Expecting ChatGroq to return a list of dicts or dict of lists
            data_dict = eval(content_str)
            df = pd.DataFrame(data_dict)
            content_str = f"Pandas DataFrame:\n{df}"
        except Exception:
            pass  # fallback: just show raw text

        return HumanMessage(content=content_str, name="Chart Generator")

    return agent_callable

# ======================================================
# Agent Node
# ======================================================
def agent_node(state: AgentState, agent, name: str):
    response = agent(state)

    if not isinstance(response, FunctionMessage):
        response = HumanMessage(**response.model_dump(exclude={"type", "name"}), name=name)

    node_output = {
        "node": name,
        "sender": name,
        "messages": [response.model_dump() if hasattr(response, "model_dump") else {"content": response.content}]
    }

    # Print node output immediately
    print(json.dumps(node_output, indent=2))
    print("----")
    return {"messages": [response], "sender": name}

# ======================================================
# Router
# ======================================================
def router(state):
    last_msg = state["messages"][-1]
    if "function_call" in last_msg.additional_kwargs:
        return "call_tool"
    if "FINAL ANSWER" in getattr(last_msg, "content", ""):
        return "end"
    return "continue"

# ======================================================
# Agents
# ======================================================
research_agent = create_agent(
    llm,
    system_message="You are a Researcher AI. Provide concise factual data for charting."
)
research_node = functools.partial(agent_node, agent=research_agent, name="Researcher")

chart_agent = create_table_agent(
    llm,
    system_message="You are a Chart Generator AI. Provide data as a Pandas DataFrame, not a chart."
)
chart_node = functools.partial(agent_node, agent=chart_agent, name="Chart Generator")

# ======================================================
# Tool Node
# ======================================================
tool_node = ToolNode(tools)

# ======================================================
# Workflow Graph
# ======================================================
workflow = StateGraph(AgentState)
workflow.add_node("Researcher", research_node)
workflow.add_node("Chart Generator", chart_node)
workflow.add_node("call_tool", tool_node)

workflow.add_conditional_edges(
    "Researcher",
    router,
    {"continue": "Chart Generator", "call_tool": "call_tool", "end": END},
)
workflow.add_conditional_edges(
    "Chart Generator",
    router,
    {"continue": "Researcher", "call_tool": "call_tool", "end": END},
)
workflow.add_conditional_edges(
    "call_tool",
    lambda s: s["sender"],
    {"Researcher": "Researcher", "Chart Generator": "Chart Generator"},
)
workflow.set_entry_point("Researcher")

graph = workflow.compile()

# ======================================================
# Run Workflow
# ======================================================
if __name__ == "__main__":
    initial_state = {
        "messages": [
            HumanMessage(
                content=(
                    "Fetch India's GDP over the past 1 year, "
                    "then show it as a Pandas DataFrame table. Once done, finish."
                )
            )
        ],
        "sender": "user",
    }

    for _ in graph.stream(initial_state, {"recursion_limit": 150}):
        pass
