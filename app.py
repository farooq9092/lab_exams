import streamlit as st

try:
    import sqlalchemy
    st.write("SQLAlchemy imported successfully!")
except ModuleNotFoundError:
    st.write("SQLAlchemy import failed!")
