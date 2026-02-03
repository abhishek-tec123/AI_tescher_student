import os
import functools
import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_experimental.utilities import PythonREPL
from langchain_groq import ChatGroq

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# =========================================================
# 1. API KEYS
# =========================================================
os.environ["GROQ_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"

# =========================================================
# 2. TOOLS
# =========================================================
tavily_tool = TavilySearchResults(max_results=5)

repl = PythonREPL()

@tool(description="Execute Python code and return output")
def python_repl(code: Annotated[str, "Python code to execute"]):
    """Runs Python code in a sandboxed REPL."""
    try:
        return repl.run(code)
    except Exception as e:
        return f"Error: {e}"

tools = [tavily_tool, python_repl]

# =========================================================
# 3. AGENT STATE (FIXED)
# =========================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sender: str

# =========================================================
# 4. ROUTER
# =========================================================
def router(state: AgentState):
    last = state["messages"][-1]

    if last.tool_calls:
        return "tools"

    if "FINAL ANSWER" in last.content:
        return "end"

    return "continue"

# =========================================================
# 5. AGENT FACTORY (Groq-safe)
# =========================================================
def create_agent(llm, tools, system_message):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a collaborative AI agent.\n"
                "Use tools when needed.\n"
                "When finished, respond with 'FINAL ANSWER'.\n\n"
                f"{system_message}",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    return prompt | llm.bind_tools(tools)

# =========================================================
# 6. AGENT NODE (FIXED)
# =========================================================
def agent_node(state: AgentState, agent, name: str):
    response = agent.invoke(state)

    return {
        "messages": [response],  # MUST be a list
        "sender": name,
    }

# =========================================================
# 7. LLM + AGENTS
# =========================================================
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
)

research_agent = create_agent(
    llm,
    [tavily_tool],
    "Research factual data accurately.",
)

chart_agent = create_agent(
    llm,
    [python_repl],
    "Use Python to analyze or visualize data.",
)

research_node = functools.partial(agent_node, agent=research_agent, name="Researcher")
chart_node = functools.partial(agent_node, agent=chart_agent, name="ChartGenerator")

# =========================================================
# 8. GRAPH
# =========================================================
graph = StateGraph(AgentState)

graph.add_node("Researcher", research_node)
graph.add_node("ChartGenerator", chart_node)
graph.add_node("tools", ToolNode(tools))

graph.add_conditional_edges(
    "Researcher",
    router,
    {
        "continue": "ChartGenerator",
        "tools": "tools",
        "end": END,
    },
)

graph.add_conditional_edges(
    "ChartGenerator",
    router,
    {
        "continue": "Researcher",
        "tools": "tools",
        "end": END,
    },
)

graph.add_conditional_edges(
    "tools",
    lambda s: s["sender"],
    {
        "Researcher": "Researcher",
        "ChartGenerator": "ChartGenerator",
    },
)

graph.set_entry_point("Researcher")
app = graph.compile()

# =========================================================
# 9. RUN
# =========================================================
initial_state = {
    "messages": [
        HumanMessage(content="Explain what a multi-agent system")
    ],
    "sender": "user",
}

for step in app.stream(initial_state, {"recursion_limit": 100}):
    print(step)
    print("-" * 60)
