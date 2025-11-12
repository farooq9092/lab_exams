import streamlit as st
import os
import datetime
import random
import string
import socket
import shutil
import tempfile

# ----------------- Data Storage -----------------
if "teachers" not in st.session_state:
    st.session_state.teachers = {}
if "logged_in_teacher" not in st.session_state:
    st.session_state.logged_in_teacher = None
if "passcode" not in st.session_state:
    st.session_state.passcode = None
if "exam_folder" not in st.session_state:
    st.session_state.exam_folder = "Lab_Exams"
if "exam_durations" not in st.session_state:
    st.session_state.exam_durations = {}
if "submitted_data" not in st.session_state:
    st.session_state.submitted_data = {}

# ----------------- Helper Functions -----------------
def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown_IP"

def generate_serial(files):
    return len(files) + 1

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# ----------------- Signup & Login -----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
        elif not username or not password or not phone:
            st.warning("All fields are required.")
        else:
            st.session_state.teachers[username] = {"password": password, "name": name, "phone": phone}
            st.success("✅ Registered successfully! Please log in.")

def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
            st.experimental_rerun()   # ✅ directly redirect to dashboard
        else:
            st.error("Invalid username or password")

def forgot_password():
    st.title("🔑 Forgot Password (OTP Recovery)")
    username = st.text_input("Enter your registered username")

    if st.button("Send OTP"):
        if username in st.session_state.teachers:
            otp = generate_otp()
            st.session_state.teachers[username]["otp"] = otp
            # ⚠️ Simulated SMS
