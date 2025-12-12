import streamlit as st

try:
    import imghdr
    st.write("imghdr module is available.")
except ModuleNotFoundError:
    st.error("imghdr module is missing!")
