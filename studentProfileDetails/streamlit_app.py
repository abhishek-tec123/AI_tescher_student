import streamlit as st
import requests
import hashlib

# -----------------------------
# API endpoints
# -----------------------------
API_CHAT = "http://localhost:8000/student/intent-based-agent"
API_FEEDBACK = "http://localhost:8000/student/feedback"

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Student Learning Chat", page_icon="💬", layout="wide")
st.title("💬 Student Learning Chatbot")

# -----------------------------
# Session state initialization
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "student_info" not in st.session_state:
    st.session_state.student_info = {
        "student_id": "student_001",
        "class_name": "10th",
        "subject": "Science"
    }

if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = {}  # message_idx -> feedback

if "render_counter" not in st.session_state:
    st.session_state.render_counter = 0  # for unique button keys

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
# Feedback function
# -----------------------------
def send_feedback(msg_idx, fb_type):
    # Save feedback in session state immediately
    st.session_state.feedbacks[msg_idx] = fb_type

    # Get previous user query
    user_query = ""
    for prev_idx in range(msg_idx - 1, -1, -1):
        if st.session_state.messages[prev_idx]["role"] == "user":
            user_query = st.session_state.messages[prev_idx]["content"]
            break

    bot_msg = st.session_state.messages[msg_idx]["content"]

    # Send to backend API
    payload = {
        "student_id": st.session_state.student_info["student_id"],
        "subject": st.session_state.student_info["subject"],
        "query": user_query,
        "response": bot_msg,
        "feedback": fb_type,
        "comment": None
    }

    try:
        res = requests.post(API_FEEDBACK, json=payload)
        res.raise_for_status()
        st.success(f"Feedback '{fb_type}' saved ✅")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to send feedback: {e}")

# -----------------------------
# Container for chat messages
# -----------------------------
chat_container = st.container()

# -----------------------------
# Display chat messages
# -----------------------------
def display_messages():
    with chat_container:
        for idx, msg in enumerate(st.session_state.messages):
            msg_hash = hashlib.md5(msg['content'].encode()).hexdigest()[:8]

            if msg["role"] == "user":
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown(
                        f"<div style='background-color:#1E1E1E; color:white; padding:10px; "
                        f"border-radius:15px; text-align:right; margin-bottom:5px;'>{msg['content']}</div>",
                        unsafe_allow_html=True
                    )
            else:  # Bot message
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(
                        f"<div style='background-color:#1E1E1E; color:white; padding:10px; "
                        f"border-radius:15px; text-align:left; margin-bottom:5px;'>{msg['content']}</div>",
                        unsafe_allow_html=True
                    )

                    # Feedback buttons: like 👍 and dislike 👎 only
                    fcol1, fcol2 = st.columns(2)
                    for i, (fcol, fb_type, emoji) in enumerate(zip(
                        [fcol1, fcol2],
                        ["like", "dislike"],
                        ["👍", "👎"]
                    )):
                        # Unique key including render counter
                        button_key = f"{fb_type}_{idx}_{i}_{msg_hash}_{msg['role']}_{st.session_state.render_counter}"

                        # Highlight selected feedback in green
                        if st.session_state.feedbacks.get(idx) == fb_type:
                            st.markdown(
                                f"<span style='background-color:green; color:white; padding:5px 10px; border-radius:10px;'>{emoji}</span>",
                                unsafe_allow_html=True
                            )
                        else:
                            if fcol.button(emoji, key=button_key, help=f"Give {fb_type} feedback"):
                                send_feedback(idx, fb_type)

                    # Default to neutral if no feedback exists
                    if idx not in st.session_state.feedbacks:
                        st.session_state.feedbacks[idx] = "neutral"

    # Increment render counter for next render to avoid duplicate keys
    st.session_state.render_counter += 1

# -----------------------------
# Display existing messages
# -----------------------------
display_messages()
st.markdown("<hr>")

# -----------------------------
# Input form for sending messages
# -----------------------------
with st.form("chat_form", clear_on_submit=True):
    cols = st.columns([8, 1])
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
            response = requests.post(API_CHAT, json=payload)
            response.raise_for_status()
            data = response.json()
            bot_response = data.get("response", "No response from agent.")

            # Save messages
            user_idx = len(st.session_state.messages)
            st.session_state.messages.append({"role": "user", "content": query})
            bot_idx = len(st.session_state.messages)
            st.session_state.messages.append({"role": "bot", "content": bot_response})

            # Default feedback for new bot message is neutral
            st.session_state.feedbacks[bot_idx] = "neutral"

            # Redisplay messages
            display_messages()

        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with API: {e}")
