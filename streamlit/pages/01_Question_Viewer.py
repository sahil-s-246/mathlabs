import streamlit as st
from pymongo import MongoClient
import requests
from PIL import Image
from io import BytesIO
import re


# -------------------------------------------------------------
# Streamlit Global Config
# -------------------------------------------------------------

st.title("🧠 Question Viewer")
st.write("Browse questions, diagrams, and model answers interactively.")



# -------------------------------------------------------------
# DB CONNECTION
# -------------------------------------------------------------
MONGO_URI = st.secrets["mongo"]["uri"]
client = MongoClient(MONGO_URI)
db = client["mathlabs"]
questions_col = db["questions"]
evals_col = db["evaluations"]


# -------------------------------------------------------------
# LaTeX CLEANER
# -------------------------------------------------------------
@st.cache_data
def clean_latex(text: str):

    if not isinstance(text, str):
        return text

    # ---- 1. Escape ALL known math operators outside math blocks ----
    latex_ops = [
        r"\lor", r"\neg", r"\land", r"\to", r"\leftrightarrow",
        r"\forall", r"\exists", r"\in", r"\notin",
        r"\cup", r"\cap", r"\subset", r"\subseteq"
    ]

    for op in latex_ops:
        # Replace single slash with double slash
        text = text.replace(op, op.replace("\\", "\\\\"))

    # ---- 2. Properly format inline math: $...$ ----
    def inline(m):
        content = m.group(1).replace("\\", "\\\\")
        return f"${content}$"

    text = re.sub(r"\$(.+?)\$", inline, text)

    # ---- 3. Properly format block math: $$...$$ ----
    def block(m):
        content = m.group(1).replace("\\", "\\\\")
        return f"$${content}$$"

    text = re.sub(r"\$\$(.+?)\$\$", block, text)

    # ---- 4. Escape stray $ ----
    text = text.replace(" $", " \\$")
    text = text.replace("$ ", "\\$ ")

    # ---- 5. Ensure no unmatched $ ----
    if text.count("$") % 2 == 1:
        text = text.replace("$", "\\$")

    return text



# -------------------------------------------------------------
# LOAD *ALL* EVALUATION DOCUMENTS
# -------------------------------------------------------------
all_evals = list(evals_col.find({}))

if not all_evals:
    st.error("No evaluation documents found in MongoDB.")
    st.stop()

# Extract all evaluated problem_ids from ALL evaluation docs
evaluated_ids = set()

for doc in all_evals:
    for q_eval in doc.get("questions", []):
        ref = q_eval.get("original_mcq_ref", {})
        pid = ref.get("problem_id")
        if pid:
            evaluated_ids.add(pid)

if not evaluated_ids:
    st.error("Evaluation documents found, but no valid problem IDs detected.")
    st.stop()


# -------------------------------------------------------------
# Load ALL matching questions from MongoDB
# -------------------------------------------------------------
questions = list(questions_col.find({"problem_id": {"$in": list(evaluated_ids)}}))
questions.sort(key=lambda x: x["problem_id"])
num_questions = len(questions)

if num_questions == 0:
    st.error("No questions matched evaluation problem IDs.")
    st.stop()



# -------------------------------------------------------------
# SESSION STATE ROOTS
# -------------------------------------------------------------
if "q_index" not in st.session_state:
    st.session_state.q_index = 0

if "answered" not in st.session_state:
    st.session_state.answered = False

if "user_choice" not in st.session_state:
    st.session_state.user_choice = None


def next_question():
    st.session_state.q_index = (st.session_state.q_index + 1) % num_questions
    st.session_state.answered = False
    st.session_state.user_choice = None


def prev_question():
    st.session_state.q_index = (st.session_state.q_index - 1) % num_questions
    st.session_state.answered = False
    st.session_state.user_choice = None


# -------------------------------------------------------------
# NAVIGATION HEADER
# -------------------------------------------------------------
col_prev, col_title, col_next = st.columns([1, 4, 1])

with col_prev:
    st.button("◀ Prev", on_click=prev_question)

with col_title:
    st.markdown(
        f"<h3 style='text-align:center;'>Question {st.session_state.q_index+1} / {num_questions}</h3>",
        unsafe_allow_html=True,
    )

with col_next:
    st.button("Next ▶", on_click=next_question)


# -------------------------------------------------------------
# LOAD CURRENT QUESTION + ITS EVALUATION BLOCK
# -------------------------------------------------------------
q = questions[st.session_state.q_index]
pid = q["problem_id"]

# We must find the evaluation block from ANY evaluation document
eval_block = None

for doc in all_evals:
    for ev in doc.get("questions", []):
        if ev.get("original_mcq_ref", {}).get("problem_id") == pid:
            eval_block = ev
            break
    if eval_block:
        break

if not eval_block:
    st.error(f"No evaluation found for question {pid}.")
    st.stop()


# -------------------------------------------------------------
# TWO COLUMN LAYOUT
# -------------------------------------------------------------
col_left, col_right = st.columns([2, 1])


# -------------------------------------------------------------
# LEFT: QUESTION + ANSWER INPUT
# -------------------------------------------------------------
with col_left:
    st.markdown("### 📝 Problem")
    st.markdown(q["statement"])

    sorted_choices = sorted(q["choices"], key=lambda c: c["id"])
    ids = [c["id"] for c in sorted_choices]

    st.markdown("### Choices")

    st.session_state.user_choice = st.radio(
        "Your answer:",
        ids,
        format_func=lambda cid: f"{cid}. {next(c['text'] for c in sorted_choices if c['id']==cid)}",
        index=ids.index(st.session_state.user_choice) if st.session_state.user_choice else 0,
    )

    if st.button("Submit"):
        st.session_state.answered = True

    if st.session_state.answered:
        correct = q["answer"]["correct_ids"][0]
        if st.session_state.user_choice == correct:
            st.success(f"Correct! 🎉 The correct answer is {correct}.")
            st.snow()
        else:
            st.error(f"Incorrect. The correct answer is {correct}.")


# -------------------------------------------------------------
# RIGHT: DIAGRAM
# -------------------------------------------------------------
with col_right:
    st.markdown("### 📐 Image")

    img_info = q.get("diagram_data", {})
    if img_info and img_info.get("image_path"):
        url = f"https://huggingface.co/datasets/brucezhang41/MathLABS/resolve/main/images/{img_info['image_path']}"
        try:
            img = Image.open(BytesIO(requests.get(url).content))
            st.image(img, use_container_width=True)
        except:
            st.warning("Could not load image.")
    else:
        st.info("No diagram.")


# -------------------------------------------------------------
# MODEL ANSWERS (AFTER SUBMISSION)
# -------------------------------------------------------------
if st.session_state.answered:
    st.markdown("---")
    st.markdown("## 🤖 Model Answers")

    for stu in eval_block.get("student_evaluations", []):
        ans = stu["answer"]

        if ans not in ["A", "B", "C", "D"]:
            continue

        model = stu["model"]
        reasoning = stu["reasoning"]
        time_ms = stu["time_ms"]
        correct = stu["correct"]

        with st.expander(f"{model} — Answer: {ans} {'✔️' if correct else '❌'}"):
            st.write(f"Time: {time_ms} ms")
            st.markdown(reasoning, unsafe_allow_html=True)
