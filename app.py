import streamlit as st
import google.generativeai as genai
import os
import re
import json
import time
import random
from datetime import datetime

# === Gemini API Setup ===
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")

# === Streamlit Setup ===
st.set_page_config(page_title="Y6 Mental Math Hero", page_icon="🧠", layout="wide")
st.title("🧠 Year 6 Mental Math Hero")
st.markdown("Practice your mental math skills with 20 quick questions!")

# === Topic chooser ===
topics = [
    "Addition", "Subtraction", "Multiplication", "Division",
    "Fractions", "Decimals", "Percentages", "Mixed"
]
selected_topic = st.selectbox("📚 Choose your topic:", topics)

# === Difficulty + Format in Sidebar ===
difficulty_labels = {
    1: "Level 1 — Normal",
    2: "Level 2 — Intermediate",
    3: "Level 3 — Advanced",
    4: "Level 4 — Very Challenging",
}
with st.sidebar:
    st.header("⚙️ Settings")
    selected_level = st.radio(
        "🎯 Difficulty",
        [1, 2, 3, 4],
        index=0,
        format_func=lambda x: difficulty_labels[x],
        key="difficulty_level",
    )
    st.caption("Pick a level: 1 = easiest, 4 = toughest.")

    # NEW: Question format option
    question_format = st.radio(
        "📝 Question Format",
        ["Fill in Blank", "Multiple Choice"],
        index=0,
        key="question_format"
    )

# === Prompt Builder ===
def build_prompt(topic: str, level: int, format: str) -> str:
    level_rules = {
        1: """
Level 1 (Normal):
- Single-step questions.
- Friendly numbers; small integers up to 100.
- Simple halves/quarters, tenths; 1–2 digit ×/÷.
- Percentages like 10%, 20%, 50%.
""",
        2: """
Level 2 (Intermediate):
- One to two steps.
- Integers up to 1,000; decimals to 1 dp.
- Proper/improper fractions; short division; 2-digit × 2-digit.
- Percentages like 25%, 12.5%, 5%; rounding/estimation may help.
""",
        3: """
Level 3 (Advanced):
- Multi-step reasoning (2–3 steps).
- Integers to 10,000; decimals to 2 dp; mixed numbers.
- Percentage increase/decrease; simple ratios/rates; order of operations.
- Non-friendly numbers but still mental within ~30s.
- Mixed deciaml and fraction operations. e.g. 10.5 * 22/7.
""",
        4: """
Level 4 (Very Challenging):
- Three-step mental chains.
- Decimals to 2–3 dp; fraction/decimal/percent conversions.
- 3-digit × 2-digit using mental strategies (answers exact).
- Ratio/proportion, remainders, divisibility; trickier combinations.
"""
    }

    if format == "Fill in Blank":
        return f"""
You're a friendly math tutor for a 10–12 year old Australian student (Year 6).
Topic: {topic}
Difficulty: {difficulty_labels[level].split(" — ")[0]}.

Follow the difficulty guidance:
{level_rules[level]}

Generate exactly 20 **mental math** questions on the topic (or a balanced mix if "Mixed").
The questions must be:
- short and solvable mentally (no calculators or long written methods)
- varied in structure and difficulty within the level
- age-appropriate and unambiguous
- answers should be **exact** (simplified fractions or exact decimals)

Output ONLY a JSON list (no explanation or intro), like:
[
  {{
    "question": "What is 25% of 60?",
    "answer": "15"
  }},
  ...
]
Wrap the JSON in a ```json code block.
"""
    else:  # Multiple Choice
        return f"""
You're a friendly math tutor for a 10–12 year old Australian student (Year 6).
Topic: {topic}
Difficulty: {difficulty_labels[level].split(" — ")[0]}.

Follow the difficulty guidance:
{level_rules[level]}

Generate exactly 20 **mental math multiple choice (MCQ)** questions.
Each must have:
- A "question" string.
- An "options" list with exactly 5 choices (A–E).
- An "answer" string matching exactly one of the options.
- Distractors should be reasonable mistakes (not random nonsense).

Output ONLY a JSON list (no explanation or intro), like:
[
  {{
    "question": "What is 25% of 60?",
    "options": ["10", "12", "15", "18", "20"],
    "answer": "15"
  }},
  ...
]
Wrap the JSON in a ```json code block.
"""

# === Save to JSON File ===
def save_to_json(qna_list, topic, level, format):
    os.makedirs("MentalMath", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = topic.replace(" ", "_").lower()
    safe_format = format.replace(" ", "_")
    filename = f"MentalMath/questions_{safe_topic}_L{level}_{safe_format}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(qna_list, f, indent=2, ensure_ascii=False)
    return filename

# === Session State Init ===
for key, default in {
    "qna": None, "start_time": None, "submitted": False,
    "user_answers": [], "end_time": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# === Generate Questions ===
if st.button("🎲 Generate My Questions"):
    with st.spinner("Thinking..."):
        prompt = build_prompt(selected_topic, selected_level, question_format)
        response = model.generate_content(prompt)
        content = (response.text or "").strip()

        try:
            match = re.search(r"```json\s*(\[\s*{.*?}\s*])\s*```", content, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1)
            else:
                start = content.find("[")
                end = content.rfind("]") + 1
                if start == -1 or end <= 0:
                    raise ValueError("No JSON array found in model output.")
                json_str = content[start:end]

            qna = json.loads(re.sub(r",\s*([}\]])", r"\1", json_str))

            if isinstance(qna, list) and len(qna) == 20:
                filename = save_to_json(qna, selected_topic, selected_level, question_format)
                st.success(f"✅ Questions saved to: `{filename}`")
                st.session_state.qna = qna
                st.session_state.start_time = time.time()
                st.session_state.submitted = False
                st.session_state.user_answers = []
                st.rerun()
            else:
                st.error("⚠️ Couldn't parse a valid set of 20 Q&A items. Try again.")
                st.code(content, language="markdown")
        except Exception as e:
            st.error(f"Parsing error: {e}")
            st.code(content, language="markdown")

# === Display Questions ===
import copy

# === After generating questions ===
if st.session_state.qna and not st.session_state.submitted:
    elapsed = int(time.time() - st.session_state.start_time)
    m, s = divmod(elapsed, 60)
    st.info(f"⏱️ Timer: **{m}m {s}s**")

    # Initialize fixed shuffled options if not already done
    if "shuffled_options" not in st.session_state:
        st.session_state.shuffled_options = []

        for qa in st.session_state.qna:
            if "options" in qa:  # MCQ type
                shuffled = copy.deepcopy(qa["options"])
                random.shuffle(shuffled)
                st.session_state.shuffled_options.append(shuffled)
            else:
                st.session_state.shuffled_options.append(None)

    user_answers = []
    st.markdown("### ✍️ Answer the following:")

    for i, qa in enumerate(st.session_state.qna):
        st.markdown(f"**{i+1}. {qa['question']}**")

        if question_format == "Fill in Blank":
            ans = st.text_input(f"Answer for Q{i+1}", key=f"q{i}", label_visibility="collapsed")
            user_answers.append((qa['question'], qa['answer'], (ans or "").strip()))
        else:  # Multiple Choice
            options = st.session_state.shuffled_options[i]  # fixed order
            labeled_options = [f"{chr(65+j)}. {opt}" for j, opt in enumerate(options)]
            ans = st.radio(
                f"Select answer for Q{i+1}",
                labeled_options,
                index=None,
                key=f"q{i}_mcq"
            )
            ans_clean = ans.split(". ", 1)[1] if ans else ""
            user_answers.append((qa['question'], qa['answer'], ans_clean))

    if st.button("✅ Submit Answers"):
        st.session_state.submitted = True
        st.session_state.end_time = time.time()
        st.session_state.user_answers = user_answers
        st.rerun()

    # Timer auto-refresh
    time.sleep(1)
    st.rerun()

# === Results ===
if st.session_state.submitted and st.session_state.end_time:
    elapsed = int(st.session_state.end_time - st.session_state.start_time)
    m, s = divmod(elapsed, 60)
    st.success(f"⏱️ You completed the quiz in **{m} minutes {s} seconds**!")

    correct = 0
    for q, correct_ans, user_ans in st.session_state.user_answers:
        if user_ans == correct_ans:
            st.markdown(f"✅ **{q}** → Your answer: {user_ans}")
            correct += 1
        else:
            st.markdown(f"❌ **{q}** → Your answer: {user_ans or '—'} | Correct: {correct_ans}")

    total = len(st.session_state.user_answers) or 20
    st.markdown(f"### 🏆 You got **{correct} / {total}** correct!")

    if correct >= 16:
        st.success("🎉 Amazing work! You're a Math Hero!")
    elif correct >= 10:
        st.info("👍 Good job! Keep practicing!")
    else:
        st.warning("📚 Don’t give up! Try another round to improve!")

    if st.button("🔁 Try Another Set"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
