import os
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from tools_lanngraph import chatbot, retrieve_all_threads
from hybrid_rag_reranker import index_uploaded_file

# Directory where uploaded files are stored
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# **************************************** Utility functions *************************

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []

def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].insert(0, thread_id)

def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    messages = state.values.get('messages', [])
    
    temp_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            if msg.content:
                temp_messages.append({'role': 'user', 'content': msg.content})
        elif isinstance(msg, AIMessage):
            if msg.content:
                temp_messages.append({'role': 'assistant', 'content': msg.content})
    return temp_messages

def get_thread_label(thread_id):
    if 'thread_labels' not in st.session_state:
        st.session_state['thread_labels'] = {}
    
    if thread_id not in st.session_state['thread_labels']:
        messages = load_conversation(thread_id)
        first_user_msg = next((m['content'] for m in messages if m['role'] == 'user'), None)
        if first_user_msg:
            title = first_user_msg[:22] + ("..." if len(first_user_msg) > 22 else "")
        else:
            title = f"{thread_id[:8]}..." if len(str(thread_id)) > 12 else str(thread_id)
        st.session_state['thread_labels'][thread_id] = title

    return st.session_state['thread_labels'][thread_id]


# **************************************** Session Setup ******************************
if 'chat_threads' not in st.session_state:
    # Load all past threads from SQLite database on application startup
    saved_threads = retrieve_all_threads()
    st.session_state['chat_threads'] = [str(t) for t in saved_threads]

if 'thread_id' not in st.session_state:
    if st.session_state['chat_threads']:
        # Default to the most recent previous thread on startup
        st.session_state['thread_id'] = st.session_state['chat_threads'][0]
    else:
        new_id = generate_thread_id()
        st.session_state['thread_id'] = new_id
        add_thread(new_id)

if 'message_history' not in st.session_state:
    st.session_state['message_history'] = load_conversation(st.session_state['thread_id'])

if 'uploaded_file_path' not in st.session_state:
    st.session_state['uploaded_file_path'] = "Atomic_Habit.pdf"


# **************************************** Sidebar UI *********************************

st.sidebar.title(' LangGraph AI Assistant')

if st.sidebar.button('New Chat', key='btn_new_chat', use_container_width=True):
    reset_chat()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header('📄 Document Upload (RAG)')

uploaded_file = st.sidebar.file_uploader("Upload PDF Document for Search", type=["pdf"])

if uploaded_file is not None:
    destination_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    
    # Save file to destination directory if not saved yet
    if st.session_state.get('uploaded_file_name') != uploaded_file.name:
        with open(destination_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.sidebar.spinner(f"Indexing '{uploaded_file.name}' into Qdrant + BM25..."):
            index_uploaded_file(destination_path)
        
        st.session_state['uploaded_file_name'] = uploaded_file.name
        st.session_state['uploaded_file_path'] = destination_path
        st.sidebar.success(f"✅ Indexed: {uploaded_file.name}")

st.sidebar.info(f"📌 Active Document: `{os.path.basename(st.session_state['uploaded_file_path'])}`")

st.sidebar.markdown("---")
st.sidebar.header('💬 My Conversations')

for thread_id in st.session_state['chat_threads']:
    is_active = (thread_id == st.session_state['thread_id'])
    prefix = "👉 " if is_active else "💬 "
    button_label = f"{prefix}{get_thread_label(thread_id)}"
    
    if st.sidebar.button(button_label, key=f"btn_{thread_id}", use_container_width=True):
        st.session_state['thread_id'] = thread_id
        st.session_state['message_history'] = load_conversation(thread_id)
        st.rerun()


# **************************************** Main UI ************************************

st.title("Hello ! How can i help you ?")

# Display conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.write(message['content'])

user_input = st.chat_input('Type your message here...')

if user_input:
    # Append user message
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.write(user_input)

    active_doc = st.session_state.get('uploaded_file_path', 'Atomic_Habit.pdf')
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    with st.chat_message("assistant"):
        status_box = st.empty()

        def ai_only_stream():
            tool_called = False
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)], "active_doc": active_doc},
                config=CONFIG,
                stream_mode="messages"
            ):
                # Detect when a tool is being called and show status
                if hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls and not tool_called:
                    tool_called = True
                    status_box.status("🔍 Searching document... please wait", state="running")
                if isinstance(message_chunk, AIMessage) and message_chunk.content:
                    status_box.empty()
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})