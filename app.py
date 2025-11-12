import streamlit as st
import os
import json
import hashlib
import random
import string
from datetime import datetime

ADMIN_FILE = "app_data/admin.json"

# Utilities
def load_json(filepath, default=None):
    if default is None:
        default = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
        else:
            return default
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
        return default

def save_json(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Error saving JSON file: {e}")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def gen_otp(n=6):
    return ''.join(random.choices(string.digits, k=n))

def record_log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} - {msg}")  # Replace with actual logging if needed

# Initialize session state keys
if "admin" not in st.session_state:
    st.session_state.admin = load_json(ADMIN_FILE, {})
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "logged_in_role" not in st.session_state:
    st.session_state.logged_in_role = None
if "show_forget_pw" not in st.session_state:
    st.session_state.show_forget_pw = False
if "otp" not in st.session_state:
    st.session_state.otp = None

# Admin registration page (only if no admin exists)
def admin_register_page():
    st.header("👤 Admin Registration (One-Time Setup)")
    st.info("Only one admin account is allowed. Please register carefully.")

    username = st.text_input("Admin Username")
    password = st.text_input("Password", type="password")
    password_confirm = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if not username or not password:
            st.warning("Please enter username and password.")
            return
        if password != password_confirm:
            st.error("Passwords do not match.")
            return
        if st.session_state.admin:
            st.error("Admin already registered. Please login.")
            return
        
        st.session_state.admin = {
            "username": username,
            "password_hash": hash_password(password)
        }
        save_json(ADMIN_FILE, st.session_state.admin)
        record_log(f"ADMIN_REGISTERED: {username}")
        st.success("Admin registered successfully. Please login.")
        st.experimental_rerun()

# Admin login page
def admin_login_page():
    st.header("🔒 Admin Login")

    username = st.text_input("Admin Username")
    password = st.text_input("Admin Password", type="password")

    if st.button("Login"):
        admin_data = st.session_state.admin
        if not admin_data:
            st.error("No admin registered. Please register first.")
            return
        
        if username == admin_data.get("username") and verify_password(password, admin_data.get("password_hash", "")):
            st.session_state.logged_in_user = username
            st.session_state.logged_in_role = "admin"
            record_log(f"ADMIN_LOGIN: {username}")
            try:
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error during app reload: {e}")
        else:
            st.error("Invalid username or password.")

    st.markdown("---")
    if st.button("Forgot Password?"):
        st.session_state.show_forget_pw = True

    if st.session_state.show_forget_pw:
        admin_forget_password_page()

# Admin forget password page (shown only when button pressed)
def admin_forget_password_page():
    st.subheader("🔑 Admin Forgot Password")
    username = st.text_input("Enter Admin Username for OTP verification")

    if st.button("Send OTP"):
        if username != st.session_state.admin.get("username"):
            st.error("Username not found.")
        else:
            otp = gen_otp()
            st.session_state.otp = otp
            # Simulate sending OTP (in production integrate SMS or email)
            st.info(f"OTP sent (simulated): {otp}")
            record_log(f"ADMIN_OTP_SENT to {username}")

    entered_otp = st.text_input("Enter OTP")
    new_password = st.text_input("New Password", type="password")
    new_password_confirm = st.text_input("Confirm New Password", type="password")

    if st.button("Reset Password"):
        if entered_otp != st.session_state.otp:
            st.error("Invalid OTP.")
        elif not new_password or new_password != new_password_confirm:
            st.error("Passwords do not match or empty.")
        else:
            st.session_state.admin["password_hash"] = hash_password(new_password)
            save_json(ADMIN_FILE, st.session_state.admin)
            st.success("Password reset successful. Please login.")
            st.session_state.show_forget_pw = False
            st.session_state.otp = None
            record_log(f"ADMIN_PASSWORD_RESET for {username}")
            st.experimental_rerun()

# Admin dashboard page (after login)
def admin_dashboard():
    st.header(f"🛠️ Admin Dashboard — {st.session_state.logged_in_user}")

    # For demo purposes, show admin info in a table (only one admin)
    admin_data = st.session_state.admin
    if not admin_data:
        st.error("No admin data found!")
        return

    st.subheader("Admin Account Info")
    st.write(f"Username: **{admin_data.get('username')}**")

    if st.button("Logout"):
        st.session_state.logged_in_user = None
        st.session_state.logged_in_role = None
        st.experimental_rerun()

# Main app routing
def main():
    st.set_page_config(page_title="Professional Lab Exam Portal", layout="centered")
    st.title("📘 Professional Lab Exam Portal")

    # Admin area
    if st.session_state.logged_in_role == "admin":
        admin_dashboard()
    else:
        if not st.session_state.admin:
            admin_register_page()
        else:
            admin_login_page()

if __name__ == "__main__":
    main()
