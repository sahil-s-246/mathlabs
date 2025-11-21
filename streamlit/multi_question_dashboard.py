#!/usr/bin/env python3
import streamlit as st
import pandas as pd
from pymongo import MongoClient
import certifi
import plotly.express as px
import plotly.graph_objects as go


# -------------------------------------------------------------
# 1. DB LOADER
# -------------------------------------------------------------
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
    evals_col, questions_col = get_mongo_collections()

    evaluations = list(evals_col.find({}).sort("evaluated_at", -1))
    questions = list(
        questions_col.find(
            {},
            {
                "problem_id": 1,
                "difficulty": 1,
                "topic": 1,
                "diagram_data.image_path": 1,
                "validation_status": 1,
            },
        )
    )
    return evaluations, questions


# -------------------------------------------------------------
# 2. DATA PARSING
# -------------------------------------------------------------
def parse_evaluation_data(evaluations):
    rows = []

    for ev in evaluations:
        run_id = ev.get("test_run_id")
        summary = ev.get("summary", {})

        for q in ev.get("questions", []):
            pid = q.get("original_mcq_ref", {}).get("problem_id")
            validation = q.get("validation", {})
            qstats = q.get("question_stats", {})

            for stu in q.get("student_evaluations", []):
                rows.append(
                    {
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
                        "overall_avg_time_ms": summary.get("avg_question_time_ms"),
                    }
                )

    return pd.DataFrame(rows)


# -------------------------------------------------------------
# 3. OVERVIEW METRICS
# -------------------------------------------------------------
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
            f"{df.groupby('run_id')['overall_accuracy'].first().mean():.1%}",
        )
    with col4:
        avg_time = df.groupby("run_id")["overall_avg_time_ms"].first().mean()
        st.metric("Avg Time/Question", f"{avg_time/1000:.1f}s")

    st.markdown("---")


# -------------------------------------------------------------
# 4. PLOTLY VISUAL TABS
# -------------------------------------------------------------
# ---- Model Comparison ----

def tab_model_perf(df):
    st.subheader("Model Performance Comparison (with 95% CI)")

    # ---- 聚合 ----
    model_perf = df.groupby("student_model").agg(
        correct_rate=("correct", "mean"),
        n_samples=("correct", "count")
    ).reset_index()

    # ---- 准确率转百分比 ----
    model_perf["Accuracy"] = model_perf["correct_rate"] * 100

    # ---- 过滤掉答题太少或准确率为 0 的模型 ----
    model_perf = model_perf[
        (model_perf["n_samples"] >= 2) &   # 至少两题
        (model_perf["correct_rate"] > 0)   # 至少有对的
    ]

    # ---- 计算 95% CI ----
    import numpy as np
    z = 1.96
    model_perf["ci"] = z * np.sqrt(
        model_perf["correct_rate"] * (1 - model_perf["correct_rate"]) / model_perf["n_samples"]
    ) * 100

    # ---- 更稳定的模型缩写 ----
    def clean_model_name(name):
        base = name.split('/')[-1]
        seg = base.split('-')
        if len(seg) >= 3:
            return f"{seg[0]}-{seg[1]}-{seg[-1]}"   # e.g. gemma-3-free
        return base

    model_perf["model_short"] = model_perf["student_model"].apply(clean_model_name)

    # ---- 排序 ----
    model_perf = model_perf.sort_values("Accuracy", ascending=True)

    # ---- 绘图 ----
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=model_perf["Accuracy"],
        y=model_perf["model_short"],
        orientation="h",
        marker=dict(color=model_perf["Accuracy"], colorscale="Blues"),
        error_x=dict(
            type="data",
            array=model_perf["ci"],
            visible=True,
            thickness=1.5,
            color="black"
        )
    ))

    fig.update_layout(
        height=600,
        xaxis_title="Accuracy (%) (95% CI)",
        yaxis_title="Model",
        margin=dict(l=120, r=30, t=30, b=30),
        showlegend=False,
        dragmode=False
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})








def tab_difficulty(df):
    st.subheader("Question Difficulty Analysis")

    # -----------------------------
    # 1. Clean difficulty categories
    # -----------------------------
    df["difficulty_clean"] = (
        df["final_difficulty"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"easy": "Easy", "medium": "Medium", "hard": "Hard"})
    )

    # Drop rows where difficulty is not recognized
    df = df.dropna(subset=["difficulty_clean"])

    # Compute accuracy per question
    qperf = (
        df.groupby(["problem_id", "difficulty_clean"])
        .agg({"correct": "mean"})
        .reset_index()
    )
    qperf["Accuracy"] = qperf["correct"] * 100

    # -----------------------------
    # 2. Violin plot
    # -----------------------------
    import plotly.express as px
    import plotly.graph_objects as go

    fig = px.violin(
        qperf,
        x="difficulty_clean",
        y="Accuracy",
        color="difficulty_clean",
        box=True,            # show IQR box inside violin
        points="all",        # show individual jitter points
        hover_data=["problem_id"],
        color_discrete_sequence=px.colors.qualitative.Set2,
    )

    # -----------------------------
    # 3. Add mean points manually
    # -----------------------------
    mean_vals = qperf.groupby("difficulty_clean")["Accuracy"].mean()

    fig.add_trace(
        go.Scatter(
            x=mean_vals.index,
            y=mean_vals.values,
            mode="markers",
            marker=dict(size=12, color="black"),
            name="Mean Accuracy",
        )
    )

    # -----------------------------
    # 4. Layout settings
    # -----------------------------
    fig.update_layout(
        title="Accuracy Distribution by Difficulty (Violin Plot)",
        xaxis_title="Difficulty Level",
        yaxis_title="Accuracy (%)",
        height=600,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)




def tab_time(df):
    import numpy as np
    import plotly.graph_objects as go

    st.subheader("Model Response Time Comparison (with 95% CI)")

    # 1. 清理模型名（不合并同名不同版本）
    df["model_short"] = df["student_model"].apply(lambda x: x.split("/")[-1])

    # 2. 计算每个模型的均值、样本量、标准差
    stats = (
        df.groupby("model_short")
        .agg(
            mean_time=("time_ms", "mean"),
            std=("time_ms", "std"),
            n=("time_ms", "count"),
        )
        .reset_index()
    )

    # 3. 计算 95% 置信区间
    stats["ci95"] = 1.96 * stats["std"] / np.sqrt(stats["n"])

    # 4. 排序（从慢到快或快到慢都行，这里从快到慢）
    stats = stats.sort_values("mean_time", ascending=True)

    # 5. 画图
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=stats["mean_time"],
            y=stats["model_short"],
            orientation="h",
            error_x=dict(
                type="data",
                array=stats["ci95"],
                visible=True
            ),
            marker=dict(
                color=stats["mean_time"],
                colorscale="Blues",
                showscale=True,
                colorbar=dict(title="Mean Time (ms)")
            ),
        )
    )


    fig.add_vline(
    x=df["time_ms"].mean(),
    line_width=2,
    line_dash="dash",
    line_color="red",
    annotation_text="Overall Avg",
    annotation_position="top"
    )

    fig.update_layout(
        xaxis_title="Response Time (ms)",
        yaxis_title="Model",
        margin=dict(l=140, r=40, t=40, b=40),
        showlegend=False,
        height=700,
    )

    st.plotly_chart(fig, use_container_width=True)



# ---- Topic Analysis (Plotly Version) ----
def tab_topic(df, questions):
    import plotly.express as px
    import plotly.graph_objects as go

    st.subheader("Topic-Based Performance Analysis")

    question_df = pd.DataFrame(questions)

    if question_df.empty or "topic" not in question_df.columns:
        st.info("Topic information not available in questions collection")
        return

    # --- Flatten topic field ---
    question_df["topic_flat"] = question_df["topic"].apply(
        lambda x: x[0] if isinstance(x, list) and len(x) > 0 
        else (x if isinstance(x, str) else "unknown")
    )

    # --- NEW: Convert to Title Case (e.g., number_theory → Number Theory) ---
    question_df["topic_clean"] = (
        question_df["topic_flat"]
        .astype(str)
        .str.replace("_", " ")
        .str.title()
    )

    # --- Merge evaluation records with topics ---
    merged_df = df.merge(question_df[["problem_id", "topic_clean"]],
                         on="problem_id", how="left")

    if merged_df.empty:
        st.info("Topic data not available in merged dataset")
        return

    # --- Aggregate topic performance ---
    topic_perf = merged_df.groupby("topic_clean").agg({
        "correct": "mean",
        "time_ms": "mean",
        "problem_id": "nunique"
    }).reset_index()

    topic_perf.columns = ["Topic", "Accuracy", "Avg Time (ms)", "Question Count"]

    # Convert accuracy to %
    topic_perf["Accuracy"] = topic_perf["Accuracy"] * 100

    # Filter by sample count
    topic_perf = topic_perf[topic_perf["Question Count"] >= 3]

    if topic_perf.empty:
        st.info("No topic has at least 3 questions")
        return

    # --- NEW: Round numeric columns ---
    topic_perf["Accuracy"] = topic_perf["Accuracy"].round(2)
    topic_perf["Avg Time (ms)"] = topic_perf["Avg Time (ms)"].round(2)

    # Sorting
    topic_perf = topic_perf.sort_values("Accuracy", ascending=True)

    # ---------------------------------------------------
    #  Plot 1: Accuracy by Topic
    # ---------------------------------------------------
    fig_acc = px.bar(
        topic_perf,
        x="Accuracy",
        y="Topic",
        orientation="h",
        color="Accuracy",
        color_continuous_scale="Blues",
        title="Accuracy by Topic (min 3 questions)"
    )

    fig_acc.update_layout(
        height=500,
        xaxis_title="Accuracy (%)",
        yaxis_title="Topic",
        margin=dict(l=140, r=40, t=50, b=40),
    )

    # ---------------------------------------------------
    #  Plot 2: Avg Response Time by Topic
    # ---------------------------------------------------
    fig_time = px.bar(
        topic_perf.sort_values("Avg Time (ms)", ascending=True),
        x="Avg Time (ms)",
        y="Topic",
        orientation="h",
        color="Avg Time (ms)",
        color_continuous_scale="Reds",
        title="Average Response Time by Topic"
    )

    fig_time.update_layout(
        height=500,
        xaxis_title="Avg Time (ms)",
        yaxis_title="Topic",
        margin=dict(l=140, r=40, t=50, b=40),
    )

    # Plot side-by-side
    col1, col2 = st.columns(2)

    with col1:
        st.plotly_chart(fig_acc, use_container_width=True)

    with col2:
        st.plotly_chart(fig_time, use_container_width=True)

    # ---------------------------------------------------
    #  Performance Table
    # ---------------------------------------------------
    st.subheader("Topic Performance Table")

    # --- NEW: Add % sign for table display ---
    display_df = topic_perf.copy()
    display_df["Accuracy"] = display_df["Accuracy"].map(lambda x: f"{x:.2f}%")

    st.dataframe(
        display_df.sort_values("Accuracy", ascending=False),
        use_container_width=True
    )




# ---- Raw JSON ----
# ---- Detailed Results (Full Replication) ----
def tab_details(evaluations, df):
    import json

    st.subheader("Detailed Evaluation Results")

    # Available run IDs
    selected_runs = [e.get("test_run_id") for e in evaluations]
    selected_run = st.selectbox("Select Run", options=selected_runs)

    # Find run data
    run_data = next(e for e in evaluations if e.get("test_run_id") == selected_run)

    # -----------------------
    # Run-level Summary
    # -----------------------
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Validation Model", run_data.get("validation_model", "N/A"))
        st.metric("Student Models", len(run_data.get("student_models", [])))
        st.metric("Mode", run_data.get("mode", "N/A"))
        st.metric("Sampler", run_data.get("sampler", "N/A"))

    with col2:
        summary = run_data.get("summary", {})
        st.metric("Overall Accuracy", f"{summary.get('overall_accuracy', 0):.1%}")
        st.metric("Avg Time/Question", f"{summary.get('avg_question_time_ms', 0)/1000:.2f}s")
        st.metric("Questions Evaluated", len(run_data.get("questions", [])))
        st.metric("Shuffle Enabled", "Yes" if run_data.get("shuffle_enabled") else "No")

    # -----------------------
    # Question-Level Details
    # -----------------------
    st.subheader("Question-Level Results")

    questions_data = []

    for q_eval in run_data.get("questions", []):
        pid = q_eval.get("original_mcq_ref", {}).get("problem_id", "unknown")
        validation = q_eval.get("validation", {})
        stats = q_eval.get("question_stats", {})

        # Collect student model outputs
        student_results = []
        for se in q_eval.get("student_evaluations", []):
            student_results.append({
                "Model": se.get("model", "unknown"),
                "Answer": se.get("answer", "N/A"),
                "Correct": "✓" if se.get("correct") else "✗",
                "Time (ms)": se.get("time_ms", 0)
            })

        # Store full record
        questions_data.append({
            "Problem ID": pid,
            "Original Answer": validation.get("original_answer", "N/A"),
            "Final Answer": validation.get("final_answer", "N/A"),
            "Original Difficulty": validation.get("original_difficulty", "N/A"),
            "Final Difficulty": validation.get("final_difficulty", "N/A"),
            "Accuracy": f"{stats.get('accuracy', 0):.1%}",
            "Avg Time (ms)": stats.get("avg_time_ms", 0),
            "Student Results": pd.DataFrame(student_results)
        })

    # -----------------------
    # Expanders for each question
    # -----------------------
    for i, q in enumerate(questions_data, 1):
        with st.expander(f"Question {i}: {q['Problem ID']}"):
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Accuracy", q["Accuracy"])
            col2.metric("Avg Time", f"{q['Avg Time (ms)']}ms")
            col3.metric("Original Answer", q["Original Answer"])
            col4.metric("Final Answer", q["Final Answer"])

            if q["Original Answer"] != q["Final Answer"]:
                st.warning(f"Answer corrected: {q['Original Answer']} → {q['Final Answer']}")

            if q["Original Difficulty"] != q["Final Difficulty"]:
                st.info(f"Difficulty updated: {q['Original Difficulty']} → {q['Final Difficulty']}")

            st.dataframe(q["Student Results"], use_container_width=True)

    # -----------------------
    # Raw Data Section
    # -----------------------
    st.markdown("---")
    st.header("Raw Data")

    if st.checkbox("Show Raw Evaluation Data"):
        st.json(json.dumps(run_data, indent=2, default=str))

    if st.checkbox("Show Parsed DataFrame"):
        st.dataframe(df, use_container_width=True)



# -------------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------------
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

    render_overview(df, evaluations)

    # ---- TABS (Plotly Version) ----
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Model Comparison",
            "Question Difficulty",
            "Time Analysis",
            "Topic Analysis",
            "Detailed Results",
        ]
    )

    with tab1:
        tab_model_perf(df)
    with tab2:
        tab_difficulty(df)
    with tab3:
        tab_time(df)
    with tab4:
        tab_topic(df, questions)
    with tab5:
        tab_details(evaluations, df)


if __name__ == "__main__":
    main()
