import streamlit as st


def page():
    st.header("Dashboard")
    token = st.session_state.get("token")
    if not token:
        st.info("Provide token via ?st=<token> or configure reverse proxy injection.")
        return
    st.write("Token present. Hook up API calls here.")


page()

