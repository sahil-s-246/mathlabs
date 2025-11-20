#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pymongo import MongoClient
import certifi
import json

# -----------------------------------
# 1. Database Loader
# -----------------------------------
def get_mongo_collections():
    MONGO_URI = st.secrets["mongo"]["uri"]
    DB_NAME = "mathlabs"

    if MONGO_URI.startswith("mongodb+srv://"):
        client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    else:
        client = MongoClient(MONGO_URI)

    db = client[DB_NAME]
    return db["evaluations"], db["questions"]


@st.cache_data
def load_data():
    """Load all evaluations + questions from MongoDB."""
    evals_col, questions_col = get_mongo_collections()

    evaluations = list(evals_col.find({}).sort("evaluated_at", -1))
    questions = list(questions_col.find({}, {
        "problem_id": 1,
        "difficulty": 1,
        "topic": 1,
        "diagram_data.image_path": 1,
        "validation_status": 1
    }))
    return evaluations, questions


# -----------------------------------
# 2. Preprocessing
# -----------------------------------
def parse_evaluation_data(evaluations):
    """Flatten nested evaluation JSON into a DataFrame."""

    rows = []

    for ev in evaluations:
        run_id = ev.get("test_run_id")
        summary = ev.get("summary", {})

        for q in ev.get("questions", []):
            pid = q.get("original_mcq_ref", {}).get("problem_id")
            validation = q.get("validation", {})
            qstats = q.get("question_stats", {})

            for stu in q.get("student_evaluations", []):
                rows.append({
                    "run_id": run_id,
                    "evaluated_at": ev.get("evaluated_at"),
                    "student_model": stu.get("model"),
                    "correct": stu.get("correct", False),
                    "time_ms": stu.get("time_ms", 0),
                    "problem_id": pid,
                    "final_difficulty": validation.get("final_difficulty"),
                    "original_answer": validation.get("original_answer"),
                    "final_answer": validation.get("final_answer"),
                    "question_accuracy": qstats.get("accuracy", 0),
                    "overall_accuracy": summary.get("overall_accuracy"),
                    "overall_avg_time_ms": summary.get("avg_question_time_ms")
                })

    df = pd.DataFrame(rows)
    return df


# -----------------------------------
# 3. Dashboard UI Rendering
# -----------------------------------
def render_overview(df, evaluations):
    st.header("Overview Statistics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Runs", len(evaluations))

    with col2:
        st.metric("Questions Evaluated", df["problem_id"].nunique())

    with col3:
        st.metric(
            "Average Accuracy",
            f"{df.groupby('run_id')['overall_accuracy'].first().mean():.1%}"
        )

    with col4:
        avg_time = df.groupby("run_id")["overall_avg_time_ms"].first().mean()
        st.metric("Avg Time/Question", f"{avg_time/1000:.1f}s")

    st.markdown("---")


# -----------------------------------
# 4. Tabs (Each visualization kept intact)
# -----------------------------------
def tab_accuracy(df):
    st.subheader("Accuracy Over Time")

    run_accuracy = df.groupby("run_id").agg({
        "overall_accuracy": "first",
        "evaluated_at": "first"
    }).reset_index()

    run_accuracy["evaluated_at"] = pd.to_datetime(
        run_accuracy["evaluated_at"].astype(str).str.replace("Z", ""),
        errors="coerce"
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(run_accuracy["evaluated_at"], run_accuracy["overall_accuracy"] * 100,
            marker="o", linewidth=2)
    ax.grid(True)
    ax.set_ylim(0, 100)
    plt.xticks(rotation=45)
    st.pyplot(fig)


def tab_model_perf(df):
    st.subheader("Model Performance Comparison")

    model_perf = df.groupby("student_model").agg({
        "correct": "mean",
        "time_ms": "mean"
    }).reset_index()

    model_perf["Accuracy"] = model_perf["correct"] * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(model_perf["student_model"], model_perf["Accuracy"])
    ax.set_xlabel("Accuracy (%)")
    ax.grid(True)
    st.pyplot(fig)


def tab_difficulty(df):
    st.subheader("Question Difficulty Analysis")

    qperf = df.groupby("problem_id").agg({
        "correct": "mean",
        "final_difficulty": "first"
    }).reset_index()

    qperf["Accuracy"] = qperf["correct"] * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(qperf["final_difficulty"], qperf["Accuracy"])
    ax.set_xlabel("Difficulty")
    ax.set_ylabel("Accuracy (%)")
    ax.grid(True)
    st.pyplot(fig)


def tab_time(df):
    st.subheader("Response Time Distribution")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(df["time_ms"], bins=40, edgecolor="black")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Count")
    ax.grid(True)
    st.pyplot(fig)


def tab_topic(df, questions):
    st.subheader("Topic-Based Performance")

    qdf = pd.DataFrame(questions)
    qdf["topic_flat"] = qdf["topic"].apply(
        lambda x: x[0] if isinstance(x, list) and x else (x if isinstance(x, str) else "unknown")
    )

    merged = df.merge(qdf[["problem_id", "topic_flat"]], on="problem_id", how="left")

    topic_perf = merged.groupby("topic_flat")["correct"].mean().sort_values()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(topic_perf.index, topic_perf.values * 100)
    ax.set_xlabel("Accuracy (%)")
    ax.grid(True)
    st.pyplot(fig)


def tab_details(evaluations):
    st.subheader("Detailed Evaluation Results")

    run_ids = [e["test_run_id"] for e in evaluations]
    selected = st.selectbox("Select Run", run_ids)

    run = next(e for e in evaluations if e["test_run_id"] == selected)

    st.json(run)  # Simplified: 可自行换成更漂亮的表格


# -----------------------------------
# MAIN ENTRY
# -----------------------------------
def main():
    st.title("Multi-Question Dashboard")
    st.markdown("Comprehensive analysis across evaluation runs.")
    st.markdown("---")

    evaluations, questions = load_data()

    if not evaluations:
        st.error("No evaluation data found.")
        return

    df = parse_evaluation_data(evaluations)
    if df.empty:
        st.error("No parsed data available.")
        return

    # ----- Overview -----
    render_overview(df, evaluations)

    # ----- Tabs -----
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Accuracy Trends", "Model Comparison", "Question Difficulty",
        "Time Analysis", "Topic Analysis", "Detailed Results"
    ])

    with tab1:
        tab_accuracy(df)

    with tab2:
        tab_model_perf(df)

    with tab3:
        tab_difficulty(df)

    with tab4:
        tab_time(df)

    with tab5:
        tab_topic(df, questions)

    with tab6:
        tab_details(evaluations)


if __name__ == "__main__":
    main()
