# -----------------------------
# Progressive / Degressive: update and store ALL subject-preference keys that change from queries.
# - level, learning_style, response_length, include_example updated and persisted.
# - New subject gets defaults first; then these keys update based on query streaks.
# -----------------------------
def _print_profile(label: str, profile: dict):
    keys = ("level", "tone", "learning_style", "response_length", "include_example", "common_mistakes", "confusion_counter")
    print(f"\n--- {label} ---")
    for k in keys:
        v = profile.get(k, "<missing>")
        print(f"  {k}: {v}")
    print("---\n")


def print_profile(label: str, profile: dict):
    """Print subject preference key-value (e.g. existing from DB)."""
    _print_profile(label, profile)


def update_progress_and_regression(student_manager, student_id, subject, profile):
    # Snapshot current preference (before) so we only print if model updates it
    _keys = ("level", "tone", "learning_style", "response_length", "include_example", "common_mistakes", "confusion_counter", "quiz_score_history", "consecutive_low_scores", "consecutive_perfect_scores")
    _defaults = {"level": "basic", "tone": "friendly", "learning_style": "step-by-step", "response_length": "long", "include_example": True, "common_mistakes": [], "confusion_counter": {}, "quiz_score_history": [], "consecutive_low_scores": 0, "consecutive_perfect_scores": 0}
    before_snapshot = {k: profile.get(k, _defaults.get(k)) for k in _keys}

    history = student_manager.get_conversation_history(
        student_id, subject, limit=8
    )

    correct_streak = 0
    wrong_streak = 0
    confusion_counts = {}
    degradation_triggered = False

    for h in history:
        c = h.get("confusion_type", "NO_CONFUSION")
        if c == "NO_CONFUSION":
            if wrong_streak > 0:
                break
            correct_streak += 1
        else:
            if correct_streak > 0:
                break
            wrong_streak += 1
            confusion_counts[c] = confusion_counts.get(c, 0) + 1

    # ------------------
    # CHECK CONFUSION_COUNTER THRESHOLDS (NEW LOGIC)
    # ------------------
    confusion_counter = profile.get("confusion_counter", {})
    for confusion_type, count in confusion_counter.items():
        if confusion_type == "FORMULA_CONFUSION" and count >= 2:
            degradation_triggered = True
            print(f"📉 Formula confusion threshold reached: {count} occurrences")
            break
        elif confusion_type != "FORMULA_CONFUSION" and count >= 3:
            degradation_triggered = True
            print(f"📉 Confusion threshold reached for {confusion_type}: {count} occurrences")
            break

    # ------------------
    # CHECK QUIZ SCORE THRESHOLDS (NEW LOGIC)
    # ------------------
    consecutive_low_scores = profile.get("consecutive_low_scores", 0)
    consecutive_perfect_scores = profile.get("consecutive_perfect_scores", 0)
    
    if consecutive_low_scores >= 2:
        degradation_triggered = True
        print(f"📉 Quiz degradation triggered: {consecutive_low_scores} consecutive low scores")
    elif consecutive_perfect_scores >= 2:
        print(f"📈 Quiz progression triggered: {consecutive_perfect_scores} consecutive perfect scores")

    # ------------------
    # LEVEL (3 correct → level up; 3 wrong → level down)
    # ------------------
    level = profile.get("level", "basic")

    if correct_streak >= 3:
        if level == "basic":
            level = "intermediate"
        elif level == "intermediate":
            level = "advanced"

    if wrong_streak >= 3:
        if level == "advanced":
            level = "intermediate"
        elif level == "intermediate":
            level = "basic"

    # ------------------
    # RESPONSE_LENGTH (updated logic: quiz performance has absolute priority over confusion)
    # ------------------
    response_length = profile.get("response_length", "long")

    # PERFECT PERFORMANCE: Decrease response length (ABSOLUTE PRIORITY - overrides confusion)
    if consecutive_perfect_scores >= 2:
        if response_length == "very long":
            response_length = "long"
        elif response_length == "long":
            response_length = "short"
        print(f"📈 Perfect performance: response_length reduced to {response_length}")
    # POOR PERFORMANCE: Increase response length (ABSOLUTE PRIORITY - overrides confusion)
    elif consecutive_low_scores >= 2:
        if response_length == "short":
            response_length = "long"
        elif response_length == "long":
            response_length = "very long"
        print(f"📉 Poor performance: response_length increased to {response_length}")
        degradation_include_example = True
    # REGULAR STREAK-BASED LOGIC (only if no quiz performance)
    elif correct_streak >= 3 and not degradation_triggered:
        if response_length == "very long":
            response_length = "long"
        elif response_length == "long":
            response_length = "short"
        print(f"📈 Good performance: response_length reduced to {response_length}")
    # CONFUSION-BASED DEGRADATION (only if no quiz performance)
    elif degradation_triggered or wrong_streak >= 3:
        if response_length == "short":
            response_length = "long"
        elif response_length == "long":
            response_length = "very long"
        print(f"📉 Confusion-based degradation: response_length increased to {response_length}")
        degradation_include_example = True
    else:
        degradation_include_example = False

    # ------------------
    # LEARNING STYLE (degressive: more examples when repeatedly confused)
    # ------------------
    learning_style = profile.get("learning_style", "step-by-step")
    for k, v in confusion_counts.items():
        if v >= 3:
            learning_style = "examples"
            break

    # ------------------
    # INCLUDE_EXAMPLE (updated logic: quiz performance has absolute priority over confusion)
    # ------------------
    include_example = profile.get("include_example", True)
    
    # PERFECT PERFORMANCE: Disable examples (ABSOLUTE PRIORITY - overrides confusion)
    if consecutive_perfect_scores >= 2:
        include_example = False
        print(f"📈 Perfect performance: examples disabled")
    # POOR PERFORMANCE: Enable examples (ABSOLUTE PRIORITY - overrides confusion)
    elif consecutive_low_scores >= 2:
        include_example = True
        print(f"📉 Poor performance: examples enabled")
    # REGULAR LOGIC (only if no quiz performance)
    elif degradation_triggered or degradation_include_example:
        include_example = True
        print(f"📉 Confusion-based degradation: examples enabled")
    elif level == "advanced" and not degradation_triggered:
        include_example = False
        print(f"📈 Advanced level: examples disabled")
    elif learning_style == "examples":
        include_example = True
    else:
        include_example = True

    # Update profile in memory with all computed values
    profile["level"] = level
    profile["learning_style"] = learning_style
    profile["response_length"] = response_length
    profile["include_example"] = include_example

    # ------------------
    # STORE ALL KEYS IN DB (full subject preference with defaults/current values every time)
    # ------------------
    SUBJECT_PREFERENCE_KEYS = (
        "level", "tone", "learning_style", "response_length",
        "include_example", "common_mistakes", "confusion_counter",
        "quiz_score_history", "consecutive_low_scores", "consecutive_perfect_scores"
    )
    full_preference = {k: profile.get(k) for k in SUBJECT_PREFERENCE_KEYS if k in profile}
    # Ensure we have all keys with defaults if missing
    defaults = {
        "level": "basic", "tone": "friendly", "learning_style": "step-by-step",
        "response_length": "long", "include_example": True,
        "common_mistakes": [], "confusion_counter": {},
        "quiz_score_history": [], "consecutive_low_scores": 0, "consecutive_perfect_scores": 0
    }
    for k, v in defaults.items():
        full_preference.setdefault(k, v)

    student_manager.update_subject_preference(
        student_id, subject, full_preference
    )

    # Only print before/after if preference was actually updated (level, learning_style, response_length, include_example, or common_mistakes/confusion_counter from wrong question)
    updatable = ("level", "learning_style", "response_length", "include_example", "common_mistakes", "confusion_counter", "quiz_score_history", "consecutive_low_scores", "consecutive_perfect_scores")
    changed = any(full_preference.get(k) != before_snapshot.get(k) for k in updatable)
    if changed:
        _print_profile("BEFORE (subject preference)", before_snapshot)
        _print_profile("AFTER (subject preference)", full_preference)
        direction = "📈 progressive" if (correct_streak >= 3 and wrong_streak == 0 and not degradation_triggered) else ("📉 degressive" if degradation_triggered or wrong_streak >= 3 else "📊")
        print(f"{direction} Learning state updated (correct_streak={correct_streak}, wrong_streak={wrong_streak})")
    else:
        print("Preference not updated (no change).")

    return profile


import json

# -----------------------------
# Preference Normalizer: all subject-preference keys with defaults. New subject gets these; then updated from queries.
# -----------------------------
def normalize_student_preference(pref: dict) -> dict:
    defaults = {
        "level": "basic",
        "tone": "friendly",
        "learning_style": "step-by-step",
        "response_length": "long",
        "include_example": True,
        "common_mistakes": [],
        "confusion_counter": {},
        "quiz_score_history": [],
        "consecutive_low_scores": 0,
        "consecutive_perfect_scores": 0
    }

    for k, v in defaults.items():
        pref.setdefault(k, v)

    if isinstance(pref.get("common_mistakes"), str):
        try:
            pref["common_mistakes"] = json.loads(pref["common_mistakes"]) if pref["common_mistakes"] else []
        except Exception:
            pref["common_mistakes"] = []

    if isinstance(pref.get("confusion_counter"), str):
        try:
            pref["confusion_counter"] = json.loads(pref["confusion_counter"]) if pref["confusion_counter"] else {}
        except Exception:
            pref["confusion_counter"] = {}

    return pref