#!/usr/bin/env python3
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import re

# ---------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Question Inspection - MathLABS",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔍 Question Inspection")
st.write("Deep dive into individual question performance and evaluation details across *all* runs.")
st.markdown("---")

# ---------------------------------------------------------------------
# MongoDB Connection (secrets-based, same style as homepage)
# ---------------------------------------------------------------------
MONGO_URI = st.secrets["mongo"]["uri"]
client = MongoClient(MONGO_URI)
db = client["mathlabs"]
questions_col = db["questions"]
evals_col = db["evaluations"]

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def normalize_pid(pid: str):
    """Normalize pid to avoid hidden unicode/space mismatch."""
    if not isinstance(pid, str):
        return pid
    return (
        pid.strip()
           .replace("\u00A0", "")   # non-breaking space
           .replace("\u2011", "-") # unicode hyphen
           .replace("\u2013", "-")
           .replace("\u2014", "-")
           .replace("\u2212", "-") # minus symbol
    )

def pretty_topic(t: str):
    """number_theory -> Number Theory"""
    if not isinstance(t, str):
        return "Unknown"
    t = t.replace("_", " ").strip()
    return t.title()

def normalize_difficulty(d):
    if not isinstance(d, str):
        return "unknown"
    return d.strip().lower()

def wilson_ci(k, n, z=1.96):
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2/(2*n)) / denom
    half = (z * np.sqrt((p*(1-p) + z**2/(4*n)) / n)) / denom
    return p, max(0, center-half), min(1, center+half)

def safe_dt(x):
    try:
        if x is None:
            return None
        s = str(x).replace("Z", "").replace("+00:00", "")
        return pd.to_datetime(s, utc=True, errors="coerce")
    except:
        return None

# ---------------------------------------------------------------------
# Load ALL evaluations
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all_evals():
    return list(evals_col.find({}))

all_evals = load_all_evals()
if not all_evals:
    st.error("No evaluation data found.")
    st.stop()

# ---------------------------------------------------------------------
# Build evaluated problem_id set from ALL runs
# ---------------------------------------------------------------------
evaluated_records = []
evaluated_ids = set()

for doc in all_evals:
    run_id = doc.get("test_run_id", "unknown")
    evaluated_at = safe_dt(doc.get("evaluated_at"))

    for q_eval in doc.get("questions", []):
        ref = q_eval.get("original_mcq_ref", {})
        pid_raw = ref.get("problem_id")
        if not pid_raw:
            continue
        pid = normalize_pid(pid_raw)
        evaluated_ids.add(pid)

        val = q_eval.get("validation", {})
        stats = q_eval.get("question_stats", {})
        evaluated_records.append({
            "run_id": run_id,
            "evaluated_at": evaluated_at,
            "problem_id": pid,
            "accuracy": stats.get("accuracy", None),
            "avg_time_ms": stats.get("avg_time_ms", None),
            "final_difficulty": val.get("final_difficulty", None),
            "original_difficulty": val.get("original_difficulty", None),
            "final_answer": val.get("final_answer", None),
            "original_answer": val.get("original_answer", None),
            "student_evaluations": q_eval.get("student_evaluations", []),
            "validation": val,
            "raw_block": q_eval
        })

eval_df = pd.DataFrame(evaluated_records)

if eval_df.empty:
    st.error("Evaluations exist but no valid question blocks found.")
    st.stop()

# ---------------------------------------------------------------------
# Load question docs only for evaluated ids (same approach as viewer)
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_questions_for_ids(pid_list):
    return list(questions_col.find({"problem_id": {"$in": pid_list}}))

question_docs = load_questions_for_ids(list(evaluated_ids))
question_docs_map = {normalize_pid(q["problem_id"]): q for q in question_docs}

# ---------------------------------------------------------------------
# Sidebar: Search / Filters
# ---------------------------------------------------------------------
st.sidebar.header("Question Selection")

pid_keyword = st.sidebar.text_input("Search by Problem ID keyword", value="")
topic_filter = st.sidebar.multiselect(
    "Filter by Topic",
    options=sorted({
        pretty_topic(t)
        for q in question_docs
        for t in (q.get("topic", []) if isinstance(q.get("topic"), list) else [q.get("topic")])
        if t
    })
)

difficulty_filter = st.sidebar.multiselect(
    "Filter by Difficulty",
    options=["easy", "medium", "hard", "unknown"],
    default=[]
)

min_eval_cnt = st.sidebar.slider("Min #Evaluations", 1, 30, 1)
only_with_image = st.sidebar.checkbox("Only questions with diagram", value=False)

# Build pid list with metadata to filter
pid_meta_rows = []
for pid, qdoc in question_docs_map.items():
    topics = qdoc.get("topic", [])
    if isinstance(topics, str):
        topics = [topics]
    topics_pretty = [pretty_topic(t) for t in topics if t]

    diff = normalize_difficulty(qdoc.get("difficulty", "unknown"))
    has_img = bool(qdoc.get("diagram_data", {}).get("image_path"))

    eval_cnt = int((eval_df["problem_id"] == pid).sum())

    pid_meta_rows.append({
        "problem_id": pid,
        "topics_pretty": topics_pretty,
        "difficulty": diff,
        "has_image": has_img,
        "eval_count": eval_cnt
    })

pid_meta_df = pd.DataFrame(pid_meta_rows)

# Apply filters
filtered_meta = pid_meta_df.copy()

if pid_keyword.strip():
    kw = pid_keyword.strip().lower()
    filtered_meta = filtered_meta[filtered_meta["problem_id"].str.lower().str.contains(kw)]

if topic_filter:
    filtered_meta = filtered_meta[
        filtered_meta["topics_pretty"].apply(lambda L: any(t in L for t in topic_filter))
    ]

if difficulty_filter:
    filtered_meta = filtered_meta[filtered_meta["difficulty"].isin(difficulty_filter)]

filtered_meta = filtered_meta[filtered_meta["eval_count"] >= min_eval_cnt]

if only_with_image:
    filtered_meta = filtered_meta[filtered_meta["has_image"]]

filtered_problem_ids = filtered_meta["problem_id"].tolist()

if not filtered_problem_ids:
    st.sidebar.warning("No questions match current filters.")
    st.stop()

selected_pid = st.sidebar.selectbox(
    "Select Question",
    options=filtered_problem_ids,
    format_func=lambda x: f"{x} ({int(pid_meta_df.loc[pid_meta_df.problem_id==x, 'eval_count'].iloc[0])} evals)"
)

# ---------------------------------------------------------------------
# Load selected question + all runs
# ---------------------------------------------------------------------
qdoc = question_docs_map.get(selected_pid)
if qdoc is None:
    # robust fallback (regex ignore case)
    qdoc = questions_col.find_one({"problem_id": {"$regex": f"^{re.escape(selected_pid)}$", "$options": "i"}})

if qdoc is None:
    st.error(f"Question '{selected_pid}' not found in questions collection.")
    st.stop()

question_runs = eval_df[eval_df["problem_id"] == selected_pid].copy()
question_runs = question_runs.sort_values("evaluated_at")

if question_runs.empty:
    st.error("No evaluation data for this question.")
    st.stop()

# ---------------------------------------------------------------------
# Header Metrics (use all runs)
# ---------------------------------------------------------------------
total_evals = len(question_runs)
latest_row = question_runs.iloc[-1]
latest_acc = latest_row["accuracy"] or 0
latest_time = latest_row["avg_time_ms"] or 0
latest_diff = latest_row.get("final_difficulty") or qdoc.get("difficulty", "unknown")

st.header(f"Question: {selected_pid}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Evaluations", total_evals)

m2.metric("Latest Accuracy",
          f"{latest_acc*100:.1f}%")

m3.metric("Latest Avg Time",
          f"{latest_time:.0f} ms")

m4.metric("Difficulty",
          str(latest_diff).title())

st.markdown("---")

# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Question Details",
    "Validation Across Runs",
    "Student Models",
    "Raw Schema"
])

# ==============================================================
# TAB 1 — Question Details
# ==============================================================

with tab1:
    st.subheader("Question Information")

    st.markdown("### Statement")
    st.markdown(qdoc.get("statement", "N/A"))

    st.markdown("### Choices")

    # Sort choices like in question viewer
    sorted_choices = sorted(qdoc.get("choices", []), key=lambda c: c["id"])

    for c in sorted_choices:
        cid = c.get("id", "?")
        text = c.get("text", "")

        # Render choice with LaTeX support + HTML
        st.markdown(
            f"**{cid}.** {text}",
            unsafe_allow_html=True
        )

    st.markdown("### Correct Answer")
    ans = qdoc.get("answer", {})
    st.success(f"Correct IDs: {', '.join(ans.get('correct_ids', []))}")



# ==============================================================
# TAB 2 — Validation Across Runs
# ==============================================================
with tab2:
    st.subheader("Validation Results Across Runs")

    val_rows = []
    for _, r in question_runs.iterrows():
        val = r["validation"] or {}
        acc = r["accuracy"] if r["accuracy"] is not None else 0
        n_models = len(r["student_evaluations"] or [])
        # approximate CI using n_models as n
        k = int(round(acc * n_models))
        p, lo, hi = wilson_ci(k, n_models)

        val_rows.append({
            "Run ID": r["run_id"],
            "Evaluated At": r["evaluated_at"],
            "Accuracy (%)": acc * 100,
            "CI Low (%)": lo * 100,
            "CI High (%)": hi * 100,
            "Avg Time (ms)": r["avg_time_ms"],
            "Original Answer": val.get("original_answer"),
            "Final Answer": val.get("final_answer"),
            "Original Difficulty": val.get("original_difficulty"),
            "Final Difficulty": val.get("final_difficulty"),
            "#Student Models": n_models
        })

    val_df = pd.DataFrame(val_rows)
    val_df["Evaluated At"] = pd.to_datetime(val_df["Evaluated At"], utc=True, errors="coerce")
    val_df = val_df.sort_values("Evaluated At")

    # Plot accuracy trend with CI
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=val_df["Evaluated At"],
        y=val_df["Accuracy (%)"],
        mode="lines+markers",
        name="Accuracy"
    ))

    fig.add_trace(go.Scatter(
        x=pd.concat([val_df["Evaluated At"], val_df["Evaluated At"][::-1]]),
        y=pd.concat([val_df["CI High (%)"], val_df["CI Low (%)"][::-1]]),
        fill="toself",
        name="95% CI",
        opacity=0.2,
        line=dict(width=0),
        hoverinfo="skip"
    ))

    fig.update_layout(
        height=420,
        xaxis_title="Run Time",
        yaxis_title="Accuracy (%)",
        margin=dict(l=40, r=30, t=30, b=30),
        dragmode=False,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Run-by-Run Table")
    show_cols = [
        "Run ID", "Evaluated At", "Accuracy (%)", "CI Low (%)", "CI High (%)",
        "Avg Time (ms)", "#Student Models",
        "Original Answer", "Final Answer",
        "Original Difficulty", "Final Difficulty"
    ]
    val_table = val_df[show_cols].copy()
    val_table["Accuracy (%)"] = val_table["Accuracy (%)"].round(2).astype(str) + "%"
    val_table["CI Low (%)"] = val_table["CI Low (%)"].round(2).astype(str) + "%"
    val_table["CI High (%)"] = val_table["CI High (%)"].round(2).astype(str) + "%"
    val_table["Avg Time (ms)"] = val_table["Avg Time (ms)"].round(0)

    st.dataframe(val_table, use_container_width=True, hide_index=True)

# ==============================================================
# TAB 3 — Student Models
# ==============================================================
with tab3:
    st.subheader("Student Model Performance Across Runs")

    stu_rows = []
    for _, r in question_runs.iterrows():
        run_id = r["run_id"]
        t = r["evaluated_at"]
        for se in (r["student_evaluations"] or []):
            stu_rows.append({
                "Run ID": run_id,
                "Evaluated At": t,
                "Model": se.get("model", "unknown"),
                "Answer": se.get("answer"),
                "Correct": se.get("correct", False),
                "Time (ms)": se.get("time_ms", 0)
            })

    stu_df = pd.DataFrame(stu_rows)
    if stu_df.empty:
        st.info("No student evaluations for this question.")
    else:
        # model-level summary
        summary = stu_df.groupby("Model").agg(
            n=("Correct", "size"),
            acc=("Correct", "mean"),
            avg_time=("Time (ms)", "mean")
        ).reset_index()

        summary["Accuracy (%)"] = (summary["acc"] * 100).round(2)
        summary["Avg Time (ms)"] = summary["avg_time"].round(0)

        summary = summary.sort_values("Accuracy (%)", ascending=False)

        colA, colB = st.columns([1, 1], gap="large")

        with colA:
            st.markdown("### Accuracy by Model")
            fig_acc = px.bar(
                summary,
                x="Accuracy (%)",
                y="Model",
                orientation="h",
                color="Accuracy (%)",
                color_continuous_scale="Blues",
                height=500
            )
            fig_acc.update_layout(
                margin=dict(l=160, r=40, t=40, b=30),
                xaxis_title="Accuracy (%)",
                yaxis_title="Model",
                dragmode=False
            )
            st.plotly_chart(fig_acc, use_container_width=True, config={"displayModeBar": False})

        with colB:
            st.markdown("### Response Time Distribution by Model")
            # violin plot to show distribution
            fig_time = px.violin(
                stu_df,
                x="Time (ms)",
                y="Model",
                color="Correct",
                orientation="h",
                points="all",
                height=520
            )
            fig_time.update_layout(
                margin=dict(l=160, r=40, t=40, b=30),
                xaxis_title="Time (ms)",
                yaxis_title="Model",
                dragmode=False,
                showlegend=True
            )
            st.plotly_chart(fig_time, use_container_width=True, config={"displayModeBar": False})

        st.markdown("### Raw Student Evaluations Table")
        stu_table = stu_df.copy()
        stu_table["Evaluated At"] = pd.to_datetime(stu_table["Evaluated At"], utc=True, errors="coerce")
        stu_table = stu_table.sort_values(["Evaluated At", "Run ID", "Model"])
        st.dataframe(stu_table, use_container_width=True, hide_index=True)

# ==============================================================
# TAB 4 — Raw Schema
# ==============================================================
with tab4:
    st.subheader("Raw Evaluation Blocks (All Runs)")

    for _, r in question_runs.iterrows():
        run_id = r["run_id"]
        t = r["evaluated_at"]
        with st.expander(f"{run_id} — {t}"):
            st.json(json.loads(json.dumps(r["raw_block"], default=str)))
