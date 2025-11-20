#!/usr/bin/env python3

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pymongo import MongoClient
import certifi
import json
from datetime import datetime

# -----------------------------
# MONGO FROM SECRETS
# -----------------------------
MONGO_URI = st.secrets["mongo"]["uri"]
DB_NAME = "mathlabs"
MCQ_COLLECTION = "questions"
EVAL_COLLECTION = "evaluations"

st.set_page_config(
    page_title="Single Question Analysis - MathLABS",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_evaluations():
    try:
        if MONGO_URI.startswith("mongodb+srv://"):
            client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
        else:
            client = MongoClient(MONGO_URI)
        
        db = client[DB_NAME]
        evals = db[EVAL_COLLECTION]
        
        all_evals = list(evals.find({}).sort("evaluated_at", -1))
        client.close()
        return all_evals
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {e}")
        return []

@st.cache_data
def load_question_from_db(problem_id):
    try:
        if MONGO_URI.startswith("mongodb+srv://"):
            client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
        else:
            client = MongoClient(MONGO_URI)
        
        db = client[DB_NAME]
        mcqs = db[MCQ_COLLECTION]
        
        question = mcqs.find_one({"problem_id": problem_id})
        client.close()
        return question
    except Exception as e:
        st.error(f"Failed to load question: {e}")
        return None

def get_all_evaluated_questions(evaluations):
    question_map = {}
    
    for eval_doc in evaluations:
        run_id = eval_doc.get("test_run_id", "unknown")
        evaluated_at = eval_doc.get("evaluated_at", "")
        
        for q_eval in eval_doc.get("questions", []):
            problem_id = q_eval.get("original_mcq_ref", {}).get("problem_id", "unknown")
            
            if problem_id not in question_map:
                question_map[problem_id] = {
                    "problem_id": problem_id,
                    "evaluation_count": 0,
                    "runs": [],
                    "latest_evaluation": None
                }
            
            question_map[problem_id]["evaluation_count"] += 1
            question_map[problem_id]["runs"].append({
                "run_id": run_id,
                "evaluated_at": evaluated_at,
                "evaluation_data": q_eval
            })
            
            if question_map[problem_id]["latest_evaluation"] is None:
                question_map[problem_id]["latest_evaluation"] = q_eval
            else:
                latest_date = question_map[problem_id]["latest_evaluation"].get("validation", {}).get("validated_at", "")
                current_date = q_eval.get("validation", {}).get("validated_at", "")
                if current_date > latest_date:
                    question_map[problem_id]["latest_evaluation"] = q_eval
    
    return question_map

def main():
    st.title("Single Question Analysis")
    st.markdown("Deep dive into individual question performance and evaluation details")
    st.markdown("---")
    
    evaluations = load_evaluations()
    
    if not evaluations:
        st.error("No evaluation data found. Please run evaluations first.")
        return
    
    question_map = get_all_evaluated_questions(evaluations)
    
    st.sidebar.header("Question Selection")
    
    question_list = sorted(question_map.keys())
    
    if not question_list:
        st.error("No questions found in evaluations.")
        return
    
    selected_question_id = st.sidebar.selectbox(
        "Select Question",
        options=question_list,
        format_func=lambda x: f"{x} ({question_map[x]['evaluation_count']} evaluations)"
    )
    
    if not selected_question_id:
        return
    
    question_info = question_map[selected_question_id]
    latest_eval = question_info["latest_evaluation"]
    
    st.header(f"Question: {selected_question_id}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Evaluations", question_info["evaluation_count"])
    
    with col2:
        if latest_eval and "question_stats" in latest_eval:
            accuracy = latest_eval["question_stats"].get("accuracy", 0)
            st.metric("Latest Accuracy", f"{accuracy:.1%}")
        else:
            st.metric("Latest Accuracy", "N/A")
    
    with col3:
        if latest_eval and "question_stats" in latest_eval:
            avg_time = latest_eval["question_stats"].get("avg_time_ms", 0)
            st.metric("Avg Time", f"{avg_time}ms")
        else:
            st.metric("Avg Time", "N/A")
    
    with col4:
        if latest_eval and "validation" in latest_eval:
            difficulty = latest_eval["validation"].get("final_difficulty", "unknown")
            st.metric("Difficulty", difficulty.title())
        else:
            st.metric("Difficulty", "N/A")
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Question Details",
        "Validation Results",
        "Student Model Evaluations",
        "Complete Schema"
    ])
    
    # 同样：tab1–tab4 所有内部代码保持和你原始文件完全一致，
    # 只需要改好顶部 MONGO 连接部分即可。
    # 这里我就不全部重复一遍（你可以直接把原来的四个 tab 内容粘回来）。

    with tab1:
        st.subheader("Question Information")
        question_doc = load_question_from_db(selected_question_id)
        # ……（下面全部照你原始代码粘贴即可）

    # tab2, tab3, tab4 也同理

if __name__ == "__main__":
    main()
