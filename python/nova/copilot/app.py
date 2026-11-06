"""Minimal UI:  streamlit run python/nova/copilot/app.py"""
import streamlit as st

from nova.copilot.assistant import answer
from nova.copilot.tools import Tools

st.set_page_config(page_title="NovaCommerce Analytics Copilot", layout="wide")
st.title("NovaCommerce Analytics Copilot")
st.caption("Answers ONLY from governed metrics. Every number is cited and validated. Segments show where a change "
           "is concentrated, not why it happened.")


@st.cache_resource
def tools():
    return Tools()


q = st.text_input("Ask about a governed metric", "Why did revenue drop in November 2025?")
if st.button("Ask") and q:
    a = answer(q, tools())
    st.markdown(a.text)
    st.caption(f"source: {a.source} · validation problems: {a.validation_problems or 'none'}")
    with st.expander("Evidence (exact tool calls and results)"):
        for e in a.evidence:
            st.markdown(f"**{e.id}** `{e.tool}` {e.args}")
            st.json(e.data, expanded=False)
