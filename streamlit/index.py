#!/usr/bin/env python3
import streamlit as st

# -------------------------------------------------------------
# Global Streamlit Config (must appear once)
# -------------------------------------------------------------
st.set_page_config(
    page_title="MathLABS Evaluation Dashboard",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded"
)




# -------------------------------------------------------------
# Import Home Dashboard Modules
# -------------------------------------------------------------
from multi_question_dashboard import main as multi_dashboard


# -------------------------------------------------------------
# HOME PAGE CONTENT (Main Findings)
# -------------------------------------------------------------
st.set_page_config(page_title="Index")
st.title("📊 MathLABS Evaluation Dashboard")
st.markdown("### Comprehensive analysis across multiple questions and evaluation runs")
st.markdown("---")

# Render Multi-Question Dashboard (your main homepage)
multi_dashboard()
