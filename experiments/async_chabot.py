from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core import messages
from langgraph.graph import StateGraph,START,END
from typing import TypedDict,Annotated
from langchain_core.messages import HumanMessage,BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
# from langchain_mcp_adapters.client import MultiServerMCPClient
import sqlite3
import requests
import os
import asyncio
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
)

# client = MultiServerMCPClient(
#     {
#   "mcpServers": {
#     "github": {
#       "command": "python",
#       "args": ["github_mcp_server.py"]
#     }
#   }
# }
# )

search_tool = DuckDuckGoSearchRun(region="us-en")






tools = [search_tool]
llm_with_tools = llm.bind_tools(tools)


class ChatState(TypedDict):
   messages : Annotated[list[BaseMessage],add_messages]


def built_graph():
  

    async def chat_node(state:ChatState):

       messages = state['messages']
       response = await llm_with_tools.ainvoke(messages)
       return {'messages': [response]}


    tool_node = ToolNode(tools)



    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "chat_node")

    graph.add_conditional_edges("chat_node",tools_condition,END)
    graph.add_edge('tools', 'chat_node')

    chatbot = graph.compile()

    return chatbot



async def main():

    chatbot = built_graph()

    result = await chatbot.ainvoke({'messages':HumanMessage(content='what is mutiplication of 2 and 3')})

    print(result['messages'][-1].content)


if __name__ == "__main__":
    asyncio.run(main())













# print(response)

# print(chatbot.get_graph().draw_ascii())

# # -------------------
# # 7. Helper
# # -------------------
# # def retrieve_all_threads():
# #     all_threads = set()
# #     for checkpoint in checkpointer.list(None):
# #         all_threads.add(checkpoint.config["configurable"]["thread_id"])
# #     return list(all_threads)


# # print("Messages:", result['messages'])

# # for message_chunk,metadata in chatbot.stream(
# #   { 'messages':[HumanMessage(content="give me 70 line on ipl")]},
# #   config={"configurable": {"thread_id": "1"}},
# #   stream_mode="messages"
# # ):
# #    if message_chunk.content :
# #       print(message_chunk.content, end=" ", flush=True)