"""Streamlit UI for the Facts-Only MF Assistant. Run: streamlit run app.py"""
import os

import streamlit as st

from assistant import DISCLAIMER, Assistant

st.set_page_config(page_title="Facts-Only MF Assistant", page_icon="📘", layout="centered")

# Streamlit Cloud: read the key from secrets; locally it can come from the environment.
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass


@st.cache_resource
def load_assistant():
    return Assistant()


bot = load_assistant()

st.title("📘 Facts-Only MF Assistant")
st.write(
    "Hi! I answer factual questions about three PPFAS Mutual Fund schemes "
    "(Parag Parikh Flexi Cap, ELSS Tax Saver and Large Cap), using only official AMC, SEBI and AMFI pages."
)
st.info(f"**{DISCLAIMER}** Please don't enter PAN, Aadhaar, account numbers, OTPs, email or phone numbers.")

EXAMPLES = [
    "What is the expense ratio of Parag Parikh Flexi Cap Fund?",
    "What is the lock-in period of the ELSS Tax Saver Fund?",
    "How do I download my capital gains statement?",
]

if "history" not in st.session_state:
    st.session_state.history = []  # kept only in this browser session, never written to disk

st.caption("Try one of these:")
cols = st.columns(3)
clicked = None
for col, q in zip(cols, EXAMPLES):
    if col.button(q, use_container_width=True):
        clicked = q

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

question = st.chat_input("Ask a factual question, e.g. 'Exit load of the Flexi Cap Fund?'") or clicked

if question:
    ans = bot.ask(question)
    with st.chat_message("user"):
        st.markdown(question if ans.kind != "pii" else "_(message hidden: contained personal details)_")
    lines = [ans.text, "", f"Source: [{ans.url}]({ans.url})"]
    if ans.updated:
        lines.append(f"\n_Last updated from sources: {ans.updated}_")
    reply = "\n".join(lines)
    with st.chat_message("assistant"):
        st.markdown(reply)
    # Store the reply only. PII-blocked questions are not stored at all.
    if ans.kind != "pii":
        st.session_state.history.append({"role": "user", "content": question})
    else:
        st.session_state.history.append({"role": "user", "content": "_(message hidden: contained personal details)_"})
    st.session_state.history.append({"role": "assistant", "content": reply})

st.divider()
st.caption(
    "Disclaimer: This assistant shares factual information from official public documents only. "
    "It does not provide investment advice, recommendations or return comparisons. Mutual fund investments "
    "are subject to market risks; read all scheme-related documents carefully. Figures can change, so always "
    "confirm on the linked official page."
)
