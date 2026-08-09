# ============================================================
# tools_lanngraph.py — LangGraph Agentic Pipeline
# ============================================================
# Sections:
#   1. Imports
#   2. Environment & LLM Setup
#   3. Tool Definitions
#   4. Graph State
#   5. System Prompt
#   6. Graph Nodes & Edges
#   7. Persistence (SQLite Checkpointer)
#   8. Helper Functions
# ============================================================


# ------------------------------------------------------------
# 1. Imports
# ------------------------------------------------------------
import os
import sqlite3
import requests

from dotenv import load_dotenv
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition

from hybrid_rag_reranker import hybrid_rag_tool
from sandbox_tool import sandbox_file_tool


load_dotenv()


# ------------------------------------------------------------
# 2. Environment & LLM Setup
# ------------------------------------------------------------
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.1-8b-instant",
)


# ------------------------------------------------------------
# 3. Tool Definitions
# ------------------------------------------------------------

_ddg = DuckDuckGoSearchRun(region="us-en")

@tool
def web_search(query: str) -> str:
    """Search the web for real-time information, news, current events, or any topic not in the document."""
    try:
        return _ddg.run(query)
    except Exception as e:
        return f"Error found this is not working: {e}"


@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    r = requests.get(url)
    return r.json()


# All registered tools
tools = [web_search, get_stock_price, calculator, hybrid_rag_tool, sandbox_file_tool]

# Bind tools to LLM for function calling
llm_with_tools = llm.bind_tools(tools)

# ToolNode handles tool execution within the graph
tool_node = ToolNode(tools)


# ------------------------------------------------------------
# 4. Graph State
# ------------------------------------------------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    active_doc: str


# ------------------------------------------------------------
# 5. System Prompt
# ------------------------------------------------------------
def build_system_prompt(active_doc: str) -> SystemMessage:
    return SystemMessage(
        content=(
            "You are a helpful, multipurpose AI assistant with access to several tools:\n"
            "1. `calculator`: Use for mathematical calculations.\n"
            "2. `get_stock_price`: Use for financial stock price inquiries.\n"
            "3. `web_search`: Use for real-time web searches and news.\n"
            "4. `hybrid_rag_tool`: Use ONLY when the user asks a question specifically about the uploaded document, "
            "book contents, summary of a file, domain-specific technical documents, or PDF analysis.\n"
            f"   The current uploaded document path is: '{active_doc}'. Always pass this exact path as `file_path` when calling `hybrid_rag_tool`.\n"
            "5. `sandbox_file_tool`: Use when the user asks to CREATE, EDIT, or MODIFY any file (Word .docx, Excel .xlsx, "
            "PowerPoint .pptx, or plain text). All operations run in an isolated sandbox at /tmp/bot_sandboxes/ and "
            "NEVER modify real workspace files. Supported operations: 'write_text', 'officecli', 'read'.\n\n"
            "Do NOT call `hybrid_rag_tool` for general conversation (e.g., 'hi', 'how are you'), math problems, "
            "or general knowledge queries that do not require document context."
        )
    )


# ------------------------------------------------------------
# 6. Graph Nodes & Edges
# ------------------------------------------------------------
def chat_node(state: ChatState):
    """LLM node: responds directly or routes to a tool via function calling."""
    active_doc = state.get("active_doc", "Atomic_Habit.pdf")
    system_prompt = build_system_prompt(active_doc)
    messages = [system_prompt] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition, END)
graph.add_edge("tools", "chat_node")


# ------------------------------------------------------------
# 7. Persistence (SQLite Checkpointer)
# ------------------------------------------------------------
conn = sqlite3.connect(database="chatbot.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

chatbot = graph.compile(checkpointer=checkpointer)


# ------------------------------------------------------------
# 8. Helper Functions
# ------------------------------------------------------------
def retrieve_all_threads() -> list[str]:
    """Returns all unique thread IDs stored in the SQLite checkpoint database."""
    all_threads = []
    seen = set()
    for checkpoint in checkpointer.list(None):
        tid = checkpoint.config.get("configurable", {}).get("thread_id")
        if tid and tid not in seen:
            seen.add(tid)
            all_threads.append(tid)
    return all_threads


def clear_all_history():
    """Wipes all conversation history from the SQLite checkpoint database."""
    with sqlite3.connect("chatbot.db", check_same_thread=False) as c:
        c.execute("DELETE FROM checkpoints;")
        c.execute("DELETE FROM writes;")
        c.commit()


# ------------------------------------------------------------
# Quick test (run directly: python tools_lanngraph.py)
# ------------------------------------------------------------
if __name__ == "__main__":
    response = chatbot.invoke(
        {"messages": [HumanMessage(content="give me your model name")]},
        config={"configurable": {"thread_id": "thread-test"}},
    )
    print(response["messages"][-1].content)