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
    _keys = ("level", "tone", "learning_style", "response_length", "include_example", "common_mistakes", "confusion_counter")
    _defaults = {"level": "basic", "tone": "friendly", "learning_style": "step-by-step", "response_length": "long", "include_example": True, "common_mistakes": [], "confusion_counter": {}}
    before_snapshot = {k: profile.get(k, _defaults.get(k)) for k in _keys}

    history = student_manager.get_conversation_history(
        student_id, subject, limit=8
    )

    correct_streak = 0
    wrong_streak = 0
    confusion_counts = {}

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
    # RESPONSE_LENGTH (from streaks; stored in DB)
    # ------------------
    response_length = profile.get("response_length", "long")

    if correct_streak >= 5:
        response_length = "very short"
    elif correct_streak >= 3:
        response_length = "short"

    if wrong_streak >= 5:
        response_length = "long"
    elif wrong_streak >= 3:
        response_length = "short"

    # ------------------
    # LEARNING STYLE (degressive: more examples when repeatedly confused)
    # ------------------
    learning_style = profile.get("learning_style", "step-by-step")
    for k, v in confusion_counts.items():
        if v >= 3:
            learning_style = "examples"
            break

    # ------------------
    # INCLUDE_EXAMPLE (advanced → False for shorter; else True; examples style → True)
    # ------------------
    include_example = profile.get("include_example", True)
    if level == "advanced":
        include_example = False
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
        "include_example", "common_mistakes", "confusion_counter"
    )
    full_preference = {k: profile.get(k) for k in SUBJECT_PREFERENCE_KEYS if k in profile}
    # Ensure we have all keys with defaults if missing
    defaults = {
        "level": "basic", "tone": "friendly", "learning_style": "step-by-step",
        "response_length": "long", "include_example": True,
        "common_mistakes": [], "confusion_counter": {},
    }
    for k, v in defaults.items():
        full_preference.setdefault(k, v)

    student_manager.update_subject_preference(
        student_id, subject, full_preference
    )

    # Only print before/after if preference was actually updated (level, learning_style, response_length, include_example, or common_mistakes/confusion_counter from wrong question)
    updatable = ("level", "learning_style", "response_length", "include_example", "common_mistakes", "confusion_counter")
    changed = any(full_preference.get(k) != before_snapshot.get(k) for k in updatable)
    if changed:
        _print_profile("BEFORE (subject preference)", before_snapshot)
        _print_profile("AFTER (subject preference)", full_preference)
        direction = "📈 progressive" if (correct_streak >= 3 and wrong_streak == 0) else ("📉 degressive" if wrong_streak >= 3 else "📊")
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