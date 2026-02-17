# -----------------------------
# Quiz Helpers
# -----------------------------
quiz_sessions: dict[str, dict] = {}

def create_quiz_session(student_id: str, quiz_data: dict):
    quiz_sessions[student_id] = {
        "current_index": 0,
        "score": 0,
        "quiz": quiz_data["quiz"],
        "answers": []
    }


def get_current_question(student_id: str):
    session = quiz_sessions.get(student_id)
    if not session:
        return None

    idx = session["current_index"]
    quiz = session["quiz"]

    if idx >= len(quiz):
        return None

    q = quiz[idx]
    return {
        "question_number": idx + 1,
        "total_questions": len(quiz),
        "question": q["question"],
        "options": q["options"],
        "answer": q["answer"]
    }


def submit_quiz_answer(student_id: str, user_input: str):
    session = quiz_sessions.get(student_id)
    if not session:
        return {"error": "No active quiz"}

    idx = session["current_index"]
    quiz = session["quiz"]

    if idx >= len(quiz):
        return {"error": "Quiz already finished"}

    choice = user_input.upper().strip()
    if choice not in ["A", "B", "C", "D"]:
        return {"error": "Invalid option"}

    q = quiz[idx]
    selected = q["options"][ord(choice) - 65]
    correct = q["answer"]
    is_correct = selected == correct

    if is_correct:
        session["score"] += 1

    session["answers"].append({
        "question": q["question"],
        "selected": selected,
        "correct": correct,
        "is_correct": is_correct
    })

    session["current_index"] += 1

    return {
        "is_correct": is_correct,
        "correct_answer": correct,
        "quiz_completed": session["current_index"] >= len(quiz)
    }


def get_final_quiz_result(student_id: str):
    session = quiz_sessions.get(student_id)
    if not session:
        return None

    return {
        "score": session["score"],
        "total": len(session["quiz"]),
        "answers": session["answers"]
    }

from fastapi.responses import JSONResponse

def handle_quiz_mode(student_id: str, query: str, student_manager=None):
    """
    Handles quiz flow if the student is currently in quiz mode.
    Returns a JSONResponse if quiz mode is active, otherwise None.
    """

    # Ensure consistent student_id type
    student_id = str(student_id)

    # Not in quiz mode → let normal flow continue
    if student_id not in quiz_sessions:
        return None

    # Normalize input
    normalized_query = query.strip().upper()

    # Exit quiz
    if normalized_query in {"EXIT", "QUIT", "STOP QUIZ"}:
        session = quiz_sessions.get(student_id)

        if session and student_manager:
            try:
                student_manager.add_conversation(
                    student_id=student_id,
                    subject="quiz",
                    query=query,
                    response="Quiz cancelled by user",
                    additional_data={"quiz_action": "cancelled"}
                )
            except Exception:
                pass

        quiz_sessions.pop(student_id, None)

        return JSONResponse(content={
            "intent": "QUIZ",
            "response": {
                "message": "Quiz cancelled. Back to normal chat 🙂"
            }
        })

    # Submit answer
    result = submit_quiz_answer(student_id, normalized_query)

    if not result or "error" in result:
        return JSONResponse(content={
            "intent": "QUIZ",
            "response": {
                "message": "Please reply with A, B, C, or D."
            }
        })

    # ----------------------------
    # Quiz finished
    # ----------------------------
    if result["quiz_completed"]:
        final = get_final_quiz_result(student_id)

        # Prepare final feedback safely
        if result["is_correct"]:
            last_feedback = "✅ Correct!"
        else:
            correct = result["correct_answer"]
            last_feedback = f"❌ Incorrect. Correct answer: {correct}"

        # Record completion
        if student_manager:
            try:
                student_manager.add_conversation(
                    student_id=student_id,
                    subject="quiz",
                    query=query,
                    response=f"Quiz completed! Score: {final['score']}/{final['total']}",
                    additional_data={
                        "quiz_action": "completed",
                        "final_score": final["score"],
                        "total_questions": final["total"],
                        "answers": final["answers"]
                    }
                )
            except Exception:
                pass

        # Remove session AFTER computing everything
        quiz_sessions.pop(student_id, None)

        return JSONResponse(content={
            "intent": "QUIZ",
            "response": {
                # Keep structure simple to avoid frontend breaking
                "message": (
                    f"{last_feedback}\n\n"
                    f"🎉 Quiz Complete!\n"
                    f"Final Score: {final['score']} / {final['total']}"
                )
            }
        })

    # ----------------------------
    # Continue quiz
    # ----------------------------
    next_question = get_current_question(student_id)

    if result["is_correct"]:
        feedback = "✅ Correct!"
    else:
        feedback = f"❌ Incorrect. Correct answer: {result['correct_answer']}"

    return JSONResponse(content={
        "intent": "QUIZ",
        "response": {
            "feedback": feedback,
            "question": next_question
        }
    })
