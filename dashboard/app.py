"""
dashboard/app.py
Streamlit dashboard for Agent-X pipeline analytics.

Run with:
    python -m streamlit run dashboard/app.py

Shows:
  1. Run summary — accepted / rejected / abstained / structural counts
  2. Thompson scores — per arm win rate, alpha, beta, trials
  3. Cost saved — LLM calls bypassed via memory reuse + gateway
  4. Rejection breakdown — why runs failed
  5. Category breakdown — which error types are most common
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# Allow running from repo root or dashboard/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.data import (
    load_entries,
    load_thompson_state,
    run_summary,
    category_breakdown,
    cost_saved_summary,
    thompson_table,
    rejection_breakdown,
    acceptance_rate,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Agent-X Dashboard",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Agent-X Pipeline Dashboard")
st.caption("Live stats from memory/memory.jsonl + memory/thompson_state.json")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

entries = load_entries()
state = load_thompson_state()

if not entries:
    st.warning("No data yet — memory/memory.jsonl is empty or missing.")
    st.stop()

summary = run_summary(entries)
cats = category_breakdown(entries)
cost = cost_saved_summary(entries)
t_table = thompson_table(state)
rejections = rejection_breakdown(entries)
acc_rate = acceptance_rate(summary)

# ---------------------------------------------------------------------------
# Section 1 — Run Summary (top metrics row)
# ---------------------------------------------------------------------------

st.header("Run Summary")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total Runs", summary["total"])
col2.metric("Accepted", summary["accepted"], f"{acc_rate}%")
col3.metric("Rejected", summary["rejected"])
col4.metric("Abstained", summary["abstained"])
col5.metric("Structural", summary["structural"])
col6.metric("Acceptance Rate", f"{acc_rate}%")

# Decision breakdown bar chart
st.subheader("Decision Breakdown")
decision_df = pd.DataFrame(
    {
        "Decision": ["Accepted", "Rejected", "Abstained", "Structural"],
        "Count": [
            summary["accepted"],
            summary["rejected"],
            summary["abstained"],
            summary["structural"],
        ],
    }
)
st.bar_chart(decision_df.set_index("Decision"))

# ---------------------------------------------------------------------------
# Section 2 — Category Breakdown
# ---------------------------------------------------------------------------

st.header("Error Category Breakdown")

cat_df = pd.DataFrame(
    [{"Category": k, "Runs": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])]
)
col_chart, col_table = st.columns([2, 1])
with col_chart:
    st.bar_chart(cat_df.set_index("Category"))
with col_table:
    st.dataframe(cat_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Section 3 — Thompson Sampling Scores
# ---------------------------------------------------------------------------

st.header("Thompson Sampling — Arm Scores")
st.caption(
    "win_rate = (alpha − 1) / trials — Beta(1,1) baseline subtracted. "
    "Higher is better. Arms with more trials have more reliable estimates."
)

if t_table:
    t_df = pd.DataFrame(t_table)
    t_df["win_rate_pct"] = (t_df["win_rate"] * 100).round(1).astype(str) + "%"
    display_df = t_df[["arm", "win_rate_pct", "alpha", "beta", "trials"]].rename(
        columns={
            "arm": "Arm (Category_Ecosystem)",
            "win_rate_pct": "Win Rate",
            "alpha": "α (wins+1)",
            "beta": "β (losses+1)",
            "trials": "Trials",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Win rate bar chart
    win_df = t_df[["arm", "win_rate"]].copy()
    win_df["win_rate"] = (win_df["win_rate"] * 100).round(1)
    st.bar_chart(win_df.set_index("arm").rename(columns={"win_rate": "Win Rate (%)"}))
else:
    st.info("No Thompson state data found.")

# ---------------------------------------------------------------------------
# Section 4 — Cost Saved
# ---------------------------------------------------------------------------

st.header("LLM Cost Savings")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DeepSeek Calls Made", cost["deepseek_calls"])
c2.metric("Memory Reuse Bypasses", cost["memory_reuse"])
c3.metric("Gateway Bypasses", cost["gateway_hits"])
c4.metric("Total LLM Calls Saved", cost["bypassed_total"])

st.metric(
    "Estimated Cost Saved",
    f"${cost['cost_saved_usd']:.4f}",
    help="Based on DeepSeek-chat ~$0.28/1M tokens × ~1000 tokens/call",
)

# Bypass breakdown
bypass_df = pd.DataFrame(
    {
        "Source": ["Memory Reuse", "Gateway Rule", "DeepSeek (paid)"],
        "Runs": [cost["memory_reuse"], cost["gateway_hits"], cost["deepseek_calls"]],
    }
)
st.bar_chart(bypass_df.set_index("Source"))

# ---------------------------------------------------------------------------
# Section 5 — Rejection Reasons
# ---------------------------------------------------------------------------

st.header("Rejection / Failure Reasons")
st.caption("Only rejected, abstained, and structural decisions are included.")

if rejections:
    rej_df = pd.DataFrame(
        [
            {"Reason": k, "Count": v}
            for k, v in sorted(rejections.items(), key=lambda x: -x[1])
        ]
    )
    col_r_chart, col_r_table = st.columns([2, 1])
    with col_r_chart:
        st.bar_chart(rej_df.set_index("Reason"))
    with col_r_table:
        st.dataframe(rej_df, use_container_width=True, hide_index=True)
else:
    st.info("No rejection data available yet.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    f"Data: {summary['total']} runs loaded from memory.jsonl  |  "
    f"Thompson arms: {len(t_table)}  |  "
    "Refresh page to reload latest data."
)
