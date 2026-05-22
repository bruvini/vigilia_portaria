import streamlit as st

def load_css(file_path):
    with open(file_path, encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )