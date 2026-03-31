# Template source: pathwaycom/pathway | Difficulty: hard | Niche: data
import streamlit as st
import pandas as pd
from config import WEBSOCKET_PORT

st.set_page_config(page_title="{{DASHBOARD_TITLE}}", layout="wide")
st.title("{{DASHBOARD_TITLE}}")

@st.cache_data(ttl=5)
def fetch_latest() -> pd.DataFrame:
    # {{FETCH_FROM_WEBSOCKET_OR_DB}}
    return pd.DataFrame()

col1, col2 = st.columns(2)
with col1:
    st.metric("{{METRIC_1_LABEL}}", "{{METRIC_1_VALUE}}")
with col2:
    st.metric("{{METRIC_2_LABEL}}", "{{METRIC_2_VALUE}}")

df = fetch_latest()
if not df.empty:
    st.line_chart(df)
    # {{ADD_MORE_CHARTS}}
