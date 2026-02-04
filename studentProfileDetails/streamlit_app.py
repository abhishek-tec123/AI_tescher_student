# streamlit_chat_auto_scroll.py
import streamlit as st
import requests

API_URL = "http://localhost:8000/student/intent-based-agent"

st.set_page_config(page_title="Student Learning Chat", page_icon="💬", layout="wide")
st.title("💬 Student Learning Chatbot")
st.markdown("Chat with your AI tutor. Ask questions, take quizzes, or get a study plan!")

# -----------------------------
# Session state
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "student_info" not in st.session_state:
    st.session_state.student_info = {
        "student_id": "student_001",
        "class_name": "Math101",
        "subject": "Mathematics"
    }

# -----------------------------
# Sidebar for student info
# -----------------------------
with st.sidebar:
    st.header("Student Info")
    st.session_state.student_info["student_id"] = st.text_input(
        "Student ID", st.session_state.student_info["student_id"]
    )
    st.session_state.student_info["class_name"] = st.text_input(
        "Class Name", st.session_state.student_info["class_name"]
    )
    st.session_state.student_info["subject"] = st.text_input(
        "Subject", st.session_state.student_info["subject"]
    )

# -----------------------------
# Container for chat messages
# -----------------------------
chat_container = st.container()

def display_messages():
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown(
                        f"<div style='background-color:#1E1E1E; color:white; padding:10px; border-radius:15px; text-align:right; margin-bottom:5px;'>{msg['content']}</div>",
                        unsafe_allow_html=True
                    )
            else:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(
                        f"<div style='background-color:#1E1E1E; color:white; padding:10px; border-radius:15px; text-align:right; margin-bottom:5px;'>{msg['content']}</div>",
                        unsafe_allow_html=True
                    )
        # Dummy element to force scroll to bottom
        st.markdown("<div id='bottom'></div>", unsafe_allow_html=True)

# Display current messages
display_messages()

# -----------------------------
# Input form at the bottom
# -----------------------------
st.markdown("<br><hr>", unsafe_allow_html=True)  # Separator

with st.form("chat_form", clear_on_submit=True):
    cols = st.columns([8, 1])  # Input field and send button
    query = cols[0].text_input("Type your message here...", key="chat_input")
    send = cols[1].form_submit_button("Send")

    if send and query:
        payload = {
            "student_id": st.session_state.student_info["student_id"],
            "class_name": st.session_state.student_info["class_name"],
            "subject": st.session_state.student_info["subject"],
            "query": query
        }

        try:
            response = requests.post(API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            bot_response = data.get("response", "No response from agent.")

            # Save messages
            st.session_state.messages.append({"role": "user", "content": query})
            st.session_state.messages.append({"role": "bot", "content": bot_response})

            # Redisplay messages to scroll to bottom
            display_messages()

        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with API: {e}")
