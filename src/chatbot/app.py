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

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/ba/Flag_of_New_York_City.svg", width=80)
    st.title("NYC 311 Analytics")
    st.markdown("### Architecture Status")
    st.markdown("🟢 **Warehouse**: Supabase PostgreSQL 17")
    st.markdown("🟢 **Model**: Gemini 2.5 Flash")
    st.markdown("🔒 **Guardrail**: Triple-Layer AST Active")
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
    - Prohibits DDL/DML mutation
    - Rejects statement chaining (`;`)
    - Auto-injects `LIMIT 100` cap
    - Restricts to public schema read-only
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

# Chat History Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 View Guarded SQL"):
                st.code(msg["sql"], language="sql")
        if "data" in msg and msg["data"] is not None:
            st.dataframe(msg["data"], use_container_width=True)

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
                agent_res = ask_analytics_agent(user_input)
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

                if rows:
                    df = pd.DataFrame(rows)
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
