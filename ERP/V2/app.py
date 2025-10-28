"""
Streamlit V2 app skeleton.

Run locally:
  streamlit run ERP/V2/app.py --server.port 8501 --server.baseUrlPath V2

Reverse proxy `/V2` to this app in production.
"""

import streamlit as st
from urllib.parse import urlencode


def bootstrap_token():
    # 1) Read token from query param `st` on initial load
    qs = st.query_params
    if "st" in qs:
        st.session_state["token"] = qs["st"]
        # Remove token from URL immediately
        st.query_params.clear()
        st.rerun()


def main():
    st.set_page_config(page_title="Himalytix V2", layout="wide")
    bootstrap_token()

    token = st.session_state.get("token")
    st.sidebar.title("Himalytix V2")
    if token:
        st.sidebar.success("Authenticated")
    else:
        st.sidebar.warning("No token – add ?st=<token> to URL or configure proxy issuance.")

    st.title("V2 Dashboard")
    st.write("This is the Streamlit V2 shell. Use the sidebar to navigate pages.")


if __name__ == "__main__":
    main()

