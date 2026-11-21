"""
NYC 311 Natural Language AI Analytics Copilot (Streamlit App)
Powered by Gemini 2.5 Flash with Triple-Layer Read-Only SQL Guardrails
"""

import os
import time
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Ensure module path resolution
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.chatbot.agent import ask_analytics_agent, execute_guarded_query
from src.chatbot.guardrail import SecurityViolationError
from src.chatbot.visualizer import render_auto_visualization

load_dotenv()

st.set_page_config(
    page_title="NYC 311 AI Analytics Copilot",
    page_icon="🗽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1F497D;
    }
    .guardrail-badge {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/ba/Flag_of_New_York_City.svg", width=80)
    st.title("NYC 311 Analytics")
    st.markdown("### Architecture Status")
    st.markdown("🟢 **Warehouse**: Supabase PostgreSQL 17")
    st.markdown("🟢 **Model**: Gemini 2.5 Flash")
    st.markdown("🔒 **Guardrail**: Triple-Layer AST Active")

    # Secure Session-Isolated API Key Input
    if not st.session_state.gemini_api_key:
        user_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Enter key from Google AI Studio. Key remains isolated to your browser session."
        )
        if user_key:
            st.session_state.gemini_api_key = user_key
            st.success("API key loaded for this session.")
        else:
            st.info("💡 Set GEMINI_API_KEY in .env or enter above to enable natural language translation.")
    else:
        st.caption("🔑 Active Gemini API Key configured.")

    st.divider()

    st.markdown("### Suggested Analytical Inquiries")
    sample_queries = [
        "What are the top 5 complaint types across NYC?",
        "Which agency has the longest average resolution hours?",
        "Compare complaint volume across all 5 boroughs",
        "How many complaints were quarantined and why?",
        "What is the average resolution time for Noise complaints in Manhattan?"
    ]

    selected_sample = None
    for q in sample_queries:
        if st.button(q, key=f"btn_{hash(q)}", use_container_width=True):
            selected_sample = q

    st.divider()
    st.markdown("""
    **Security Guardrail Enforcement**:
    - Whitelist table access (NYC 311 only)
    - Prohibits DDL/DML & administrative routines
    - Rejects statement chaining (`;`) & recursive CTEs
    - Auto-injects `LIMIT 100` cap & 5s statement timeout
    """)

# Header & KPIs
st.title("🗽 NYC 311 Analytics Copilot")
st.caption("Ask natural language analytical questions across 50,000 service requests, SLA durations, and pipeline quarantine logs.")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Clean Warehouse Records", "49,930", delta="0 Rows Lost")
with col2:
    st.metric("Avg Resolution Time", "11.17 hrs", delta="Closed Tickets")
with col3:
    st.metric("Quarantined Records", "70", delta="0.14% Anomaly Rate")
with col4:
    st.metric("Pipeline Data Pass Rate", "99.86%", delta="Enterprise Grade")

st.divider()

# Display past messages with isolated widget keys
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 View Guarded SQL"):
                st.code(msg["sql"], language="sql")
        if "data" in msg and msg["data"] is not None:
            df = msg["data"]
            if len(df) == 1:
                render_auto_visualization(df, key_prefix=f"hist_{i}")
            else:
                tab_chart, tab_table = st.tabs(["📊 Visualization", "📋 Data Table"])
                with tab_chart:
                    render_auto_visualization(df, key_prefix=f"hist_{i}")
                with tab_table:
                    st.dataframe(df, use_container_width=True)

# Input handling
user_input = st.chat_input("Enter analytical question (e.g. 'Show average resolution time by borough')...")
if selected_sample:
    user_input = selected_sample

if user_input:
    # Append user prompt
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process through Agent & Guardrail
    with st.chat_message("assistant"):
        with st.spinner("Analyzing schema and generating guarded SQL query..."):
            try:
                # 1. Text-to-SQL + Guardrail
                session_key = st.session_state.gemini_api_key or os.getenv("GEMINI_API_KEY")
                agent_res = ask_analytics_agent(user_input, api_key=session_key)
                guarded_sql = agent_res["guarded_sql"]

                # 2. Execute via Supabase Read-Only RPC
                exec_res = execute_guarded_query(guarded_sql)
                rows = exec_res["rows"]
                row_count = exec_res["row_count"]
                elapsed_ms = exec_res["execution_time_ms"]

                # 3. Present Results
                response_text = f"Retrieved **{row_count} record(s)** from warehouse in **{elapsed_ms} ms**."
                st.markdown(response_text)

                with st.expander("🔍 Inspect Verified Read-Only SQL Query", expanded=False):
                    st.code(guarded_sql, language="sql")

                current_msg_idx = len(st.session_state.messages)
                if rows:
                    df = pd.DataFrame(rows)
                    if len(df) == 1:
                        render_auto_visualization(df, key_prefix=f"live_{current_msg_idx}")
                    else:
                        tab_chart, tab_table = st.tabs(["📊 Visualization", "📋 Data Table"])
                        with tab_chart:
                            render_auto_visualization(df, key_prefix=f"live_{current_msg_idx}")
                        with tab_table:
                            st.dataframe(df, use_container_width=True)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sql": guarded_sql,
                        "data": df
                    })
                else:
                    st.info("Query executed successfully, but returned zero matching rows.")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sql": guarded_sql,
                        "data": None
                    })

            except SecurityViolationError as sec_err:
                err_msg = f"🛡️ **Security Guardrail Blocked Query**: {sec_err}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except Exception as e:
                err_msg = f"⚠️ **Execution Error**: {e}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
