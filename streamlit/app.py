#!/usr/bin/env python3

import streamlit as st

# 导入你的 dashboard & single-page 分析文件
from multi_question_dashboard import main as multi_dashboard
from single_question_analysis import main as single_dashboard

# 全局页面设置（只能调用一次）
st.set_page_config(
    page_title="MathLABS Evaluation Dashboard",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.sidebar.title("Navigation")
    
    page = st.sidebar.radio(
        "Go to",
        ("Home", "Single Question Analysis")
    )

    # ----------------- HOME = MULTI DASHBOARD -----------------
    if page == "Home":
        st.title("MathLABS Evaluation Dashboard")
        st.markdown("### Comprehensive analysis across multiple questions and evaluation runs")
        st.markdown("---")

        # 直接调用多题 dashboard
        multi_dashboard()

    # ----------------- SINGLE QUESTION PAGE -----------------
    elif page == "Single Question Analysis":
        single_dashboard()

if __name__ == "__main__":
    main()
