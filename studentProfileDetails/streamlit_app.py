# import streamlit as st
# import requests

# API_BASE = "http://localhost:8000"

# CHAT_ENDPOINT = f"{API_BASE}/student/intent-based-agent"
# FEEDBACK_ENDPOINT = f"{API_BASE}/student/feedback"

# st.set_page_config(page_title="Student Assistant", page_icon="🎓")
# st.title("🎓 Student Assistant Chat")

# # -----------------------------
# # Session State Initialization
# # -----------------------------
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # -----------------------------
# # Sidebar Inputs
# # -----------------------------
# with st.sidebar:
#     st.header("Student Context")

#     student_id = st.text_input("Student ID", value="student_123")
#     subject = st.text_input("Subject", value="Math")
#     class_name = st.text_input("Class", value="10-A")

# # -----------------------------
# # Render Chat History
# # -----------------------------
# for i, msg in enumerate(st.session_state.messages):
#     with st.chat_message(msg["role"]):
#         st.markdown(msg["content"])

#         # Feedback UI for each assistant response
#         if msg["role"] == "assistant":
#             conversation_id = msg.get("conversation_id")

#             if conversation_id:
#                 feedback_key = f"feedback_{conversation_id}"

#                 # Track submitted feedback
#                 if feedback_key not in st.session_state:
#                     st.session_state[feedback_key] = None

#                 col1, col2 = st.columns(2)

#                 with col1:
#                     if st.button(
#                         "👍 Like",
#                         key=f"like_{conversation_id}",
#                         disabled=st.session_state[feedback_key] is not None
#                     ):
#                         requests.post(
#                             FEEDBACK_ENDPOINT,
#                             json={
#                                 "conversation_id": conversation_id,
#                                 "feedback": "like"
#                             }
#                         )
#                         st.session_state[feedback_key] = "like"
#                         st.success("Feedback recorded")

#                 with col2:
#                     if st.button(
#                         "👎 Dislike",
#                         key=f"dislike_{conversation_id}",
#                         disabled=st.session_state[feedback_key] is not None
#                     ):
#                         requests.post(
#                             FEEDBACK_ENDPOINT,
#                             json={
#                                 "conversation_id": conversation_id,
#                                 "feedback": "dislike"
#                             }
#                         )
#                         st.session_state[feedback_key] = "dislike"
#                         st.success("Feedback recorded")

#                 # Show selected feedback
#                 if st.session_state[feedback_key]:
#                     st.caption(f"Your feedback: **{st.session_state[feedback_key]}**")

# # -----------------------------
# # Chat Input
# # -----------------------------
# user_input = st.chat_input("Ask your question...")

# if user_input:
#     # User message
#     st.session_state.messages.append({
#         "role": "user",
#         "content": user_input
#     })

#     with st.chat_message("user"):
#         st.markdown(user_input)

#     payload = {
#         "student_id": student_id,
#         "subject": subject,
#         "class_name": class_name,
#         "query": user_input
#     }

#     with st.chat_message("assistant"):
#         with st.spinner("Thinking..."):
#             response = requests.post(CHAT_ENDPOINT, json=payload)

#             if response.status_code == 200:
#                 data = response.json()

#                 answer = data.get("response", "No response received.")
#                 conversation_id = data.get("conversation_id")

#                 st.markdown(answer)

#                 # Save assistant message WITH conversation_id
#                 st.session_state.messages.append({
#                     "role": "assistant",
#                     "content": answer,
#                     "conversation_id": conversation_id
#                 })
#             else:
#                 st.error("Failed to get response from server.")


# with log---------------------------------------------------------------

import streamlit as st
import requests
import json
import os

API_BASE = "http://localhost:8000"

CHAT_ENDPOINT = f"{API_BASE}/student/intent-based-agent"
FEEDBACK_ENDPOINT = f"{API_BASE}/student/feedback"

LOG_FILE = "log.json"

st.set_page_config(page_title="Student Assistant", page_icon="🎓")
st.title("🎓 Student Assistant Chat")

# -----------------------------
# Helper: Log interactions
# -----------------------------
def log_interaction(conversation_id, student_id, subject, class_name, query, response, feedback=None):
    """Append or update interaction in log.json"""
    entry = {
        "conversation_id": conversation_id,
        "student_id": student_id,
        "subject": subject,
        "class_name": class_name,
        "query": query,
        "response": response,
        "feedback": feedback
    }

    # Load existing logs
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

            # Check if this conversation_id exists
            updated = False
            for item in data:
                if item["conversation_id"] == conversation_id:
                    # Update feedback if provided
                    if feedback is not None:
                        item["feedback"] = feedback
                    updated = True
                    break

            if not updated:
                data.append(entry)

            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
    else:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([entry], f, indent=2)

# -----------------------------
# Session State Initialization
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------
# Sidebar Inputs
# -----------------------------
with st.sidebar:
    st.header("Student Context")
    student_id = st.text_input("Student ID", value="student_123")
    subject = st.text_input("Subject", value="Math")
    class_name = st.text_input("Class", value="10-A")

# -----------------------------
# Render Chat History
# -----------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Feedback buttons for assistant messages
        if msg["role"] == "assistant":
            conversation_id = msg.get("conversation_id")

            if conversation_id:
                feedback_key = f"feedback_{conversation_id}"

                if feedback_key not in st.session_state:
                    st.session_state[feedback_key] = msg.get("feedback", None)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        "👍 Like",
                        key=f"like_{conversation_id}",
                        disabled=st.session_state[feedback_key] is not None
                    ):
                        requests.post(
                            FEEDBACK_ENDPOINT,
                            json={
                                "conversation_id": conversation_id,
                                "feedback": "like"
                            }
                        )
                        st.session_state[feedback_key] = "like"
                        st.success("Feedback recorded")
                        # Update log with feedback
                        log_interaction(
                            conversation_id,
                            student_id,
                            subject,
                            class_name,
                            msg.get("query", ""),  # store query if available
                            msg["content"],
                            feedback="like"
                        )

                with col2:
                    if st.button(
                        "👎 Dislike",
                        key=f"dislike_{conversation_id}",
                        disabled=st.session_state[feedback_key] is not None
                    ):
                        requests.post(
                            FEEDBACK_ENDPOINT,
                            json={
                                "conversation_id": conversation_id,
                                "feedback": "dislike"
                            }
                        )
                        st.session_state[feedback_key] = "dislike"
                        st.success("Feedback recorded")
                        # Update log with feedback
                        log_interaction(
                            conversation_id,
                            student_id,
                            subject,
                            class_name,
                            msg.get("query", ""),
                            msg["content"],
                            feedback="dislike"
                        )

                # Show selected feedback
                if st.session_state[feedback_key]:
                    st.caption(f"Your feedback: **{st.session_state[feedback_key]}**")

# -----------------------------
# Chat Input
# -----------------------------
user_input = st.chat_input("Ask your question...")

if user_input:
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    # Call backend
    payload = {
        "student_id": student_id,
        "subject": subject,
        "class_name": class_name,
        "query": user_input
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = requests.post(CHAT_ENDPOINT, json=payload)

            if response.status_code == 200:
                data = response.json()
                answer = data.get("response", "No response received.")
                conversation_id = data.get("conversation_id")

                st.markdown(answer)

                # Save assistant message WITH conversation_id
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "conversation_id": conversation_id,
                    "query": user_input,  # keep query for logging
                    "feedback": None
                })

                # Log the interaction
                log_interaction(
                    conversation_id,
                    student_id,
                    subject,
                    class_name,
                    user_input,
                    answer
                )
            else:
                st.error("Failed to get response from server.")
