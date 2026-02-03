# agents.py
import functools
import operator
from typing import Sequence, TypedDict, Annotated

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import ToolNode

from tools import google_search_tool, find_nearby_places

# ----------------------------
# Agent State
# ----------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sender: str

# ----------------------------
# LLM
# ----------------------------
llm = ChatGroq(
    api_key = "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",
    model="llama-3.1-8b-instant",
    temperature=0,
)

# ----------------------------
# Agent factory
# ----------------------------
def create_agent(system_prompt: str, tools=None):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    return prompt | llm.bind_tools(tools or [])

# ----------------------------
# Nodes
# ----------------------------
def agent_node(state: AgentState, agent, name: str):
    response = agent.invoke(state)
    return {"messages": [response], "sender": name}

# ----------------------------
# News Agent
# ----------------------------
news_agent = create_agent(
    """
    Respond concisely (50-100 words)
    You are a travel news agent.
    Use web search to find current travel events and news.
    Always return bullet points.
    """,
    tools=[google_search_tool],
)

news_node = functools.partial(agent_node, agent=news_agent, name="news")

# ----------------------------
# Places Agent
# ----------------------------
places_agent = create_agent(
    """
    Respond concisely (50-100 words)
    You are a places recommendation agent.
    Suggest nearby places with name and address.
    """,
    tools=[find_nearby_places],
)

places_node = functools.partial(agent_node, agent=places_agent, name="places")

# ----------------------------
# Inspiration Agent
# ----------------------------
inspiration_agent = create_agent(
    """
    Respond concisely (50-100 words)
    You are a travel inspiration agent.
    You MUST NOT call tools directly.

    Decide whether the user needs:
    - news / web info → pass to news agent
    - nearby places → pass to places agent

    When ready to answer, summarize clearly and finish with:
    FINAL ANSWER
    """,
    tools=[google_search_tool, find_nearby_places],
)

inspiration_node = functools.partial(
    agent_node, agent=inspiration_agent, name="inspiration"
)

# ----------------------------
# Tool Node
# ----------------------------
tool_node = ToolNode([google_search_tool, find_nearby_places])
