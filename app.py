import streamlit as st
import os
import json
import hashlib
import random
import string
from datetime import datetime, timedelta
import socket
import shutil
import tempfile
import zipfile
import logging

# ----- CONFIG & PATHS -----
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_DIR = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ----- UTILITIES -----
def log_action(msg):
    logging.info(msg)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def load_json(file, default=None):
    if default is None:
        default = {}
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def get_client_ip():
    try:
        # Attempt to get client IP, fallback to localhost
        return st.request.remote_addr
    except Exception:
        return "127.0.0.1"

def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ----- SESSION STATE INITIALIZATION -----
if "teachers" not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE, {})

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "otp_store" not in st.session_state:
    st.session_state.otp_store = {}

if "active_exams" not in st.session_state:
    st.session_state.active_exams = {}  # passcode -> exam info

# ----- AUTHENTICATION & REGISTRATION -----
def register_teacher():
    st.header("Register as Teacher")
    username = st.text_input("Username", key="reg_username")
    full_name = st.text_input("Full Name", key="reg_fullname")
    phone = st.text_input("Phone Number (for OTP)", key="reg_phone")
    lab_name = st.text_input("Lab Name", key="reg_lab")
    password = st.text_input("Password", type="password", key="reg_password")
    password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm")

    if st.button("Register"):
        if not all([username, full_name, phone, lab_name, password, password_confirm]):
            st.warning("Please fill all fields.")
            return
        if password != password_confirm:
            st.warning("Passwords do not match.")
            return
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
            return

        hashed = hash_password(password)
        st.session_state.teachers[username] = {
            "full_name": full_name,
            "phone": phone,
            "lab_name": lab_name,
            "password_hash": hashed,
            "uploads_allowed": True,
            "exam_duration_mins": 0,
            "exam_passcode": None,
            "exam_start_time": None
        }
        save_json(TEACHERS_FILE, st.session_state.teachers)
        log_action(f"Teacher registered: {username}")
        st.success("Registered successfully! Please login.")

def login_teacher():
    st.header("Teacher Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        teachers = st.session_state.teachers
        if username not in teachers:
            st.error("Invalid username.")
            return
        if verify_password(password, teachers[username]["password_hash"]):
            st.session_state.logged_user = {"role": "teacher", "username": username}
            log_action(f"Teacher logged in: {username}")
            st.experimental_rerun()
        else:
            st.error("Invalid password.")

def forgot_password_teacher():
    st.header("Forgot Password (Teacher)")
    username = st.text_input("Enter your username", key="fp_username")
    teachers = st.session_state.teachers

    if username not in teachers:
        if username:
            st.error("Username not found.")
        return

    phone = teachers[username]["phone"]
    if st.button("Send OTP"):
        otp = generate_otp()
        st.session_state.otp_store[phone] = otp
        log_action(f"OTP sent to {phone} (simulated): {otp}")
        st.success("OTP sent (simulated). Check logs for OTP.")

    otp_input = st.text_input("Enter OTP", key="fp_otp")
    new_password = st.text_input("New Password", type="password", key="fp_new_pass")
    confirm_password = st.text_input("Confirm Password", type="password", key="fp_confirm_pass")

    if st.button("Reset Password"):
        if not otp_input or not new_password or not confirm_password:
            st.warning("Fill all fields.")
            return
        if new_password != confirm_password:
            st.warning("Passwords do not match.")
            return
        if phone not in st.session_state.otp_store or st.session_state.otp_store[phone] != otp_input:
            st.error("Invalid OTP.")
            return
        teachers[username]["password_hash"] = hash_password(new_password)
        save_json(TEACHERS_FILE, teachers)
        del st.session_state.otp_store[phone]
        log_action(f"Password reset for teacher: {username}")
        st.success("Password reset successful! Please login.")

# ----- TEACHER DASHBOARD -----
def teacher_dashboard():
    user = st.session_state.logged_user
    username = user["username"]
    teacher = st.session_state.teachers[username]
    st.header(f"Teacher Dashboard: {teacher['full_name']} ({username})")
    st.write(f"Lab: {teacher['lab_name']}")

    # Exam setup: duration and passcode
    col1, col2 = st.columns(2)
    with col1:
        duration = st.number_input("Set Exam Duration (minutes)", min_value=1, max_value=180, value=teacher.get("exam_duration_mins", 0))
    with col2:
        if st.button("Start/Restart Exam"):
            passcode = generate_passcode()
            teacher["exam_passcode"] = passcode
            teacher["exam_duration_mins"] = duration
            teacher["exam_start_time"] = datetime.now().isoformat()
            save_json(TEACHERS_FILE, st.session_state.teachers)
            st.session_state.active_exams[passcode] = {
                "lab_name": teacher["lab_name"],
                "start_time": teacher["exam_start_time"],
                "duration_mins": duration,
                "teacher": username,
                "uploads_allowed": True
            }
            log_action(f"Teacher {username} started exam with passcode {passcode}")
            st.success(f"Exam started! Passcode: {passcode}")

    # Toggle uploads
    uploads_allowed = teacher.get("uploads_allowed", True)
    if st.button(f"Toggle Uploads (Currently {'Enabled' if uploads_allowed else 'Disabled'})"):
        teacher["uploads_allowed"] = not uploads_allowed
        save_json(TEACHERS_FILE, st.session_state.teachers)
        st.experimental_rerun()

    # End exam
    if st.button("End Exam"):
        passcode = teacher.get("exam_passcode")
        if passcode and passcode in st.session_state.active_exams:
            del st.session_state.active_exams[passcode]
        teacher["exam_passcode"] = None
        teacher["exam_duration_mins"] = 0
        teacher["exam_start_time"] = None
        save_json(TEACHERS_FILE, st.session_state.teachers)
        st.success("Exam ended.")
        log_action(f"Teacher {username} ended exam.")
        st.experimental_rerun()

    st.markdown("---")

    # Show submissions table
    st.subheader("Student Submissions")
    lab_sub_dir = os.path.join(SUBMISSIONS_DIR, teacher["lab_name"])
    os.makedirs(lab_sub_dir, exist_ok=True)

    submissions = []
    for student_folder in os.listdir(lab_sub_dir):
        student_path = os.path.join(lab_sub_dir, student_folder)
        if os.path.isdir(student_path):
            for filename in os.listdir(student_path):
                filepath = os.path.join(student_path, filename)
                submissions.append({
                    "student_id": student_folder,
                    "filename": filename,
                    "filepath": filepath
                })

    if submissions:
        # Display table
        for i, sub in enumerate(submissions, 1):
            st.write(f"{i}. Student: {sub['student_id']} | File: {sub['filename']}")
            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button(f"Copy File #{i}"):
                    dest = st.text_input(f"Enter destination folder path to copy file #{i}:", key=f"copy_dest_{i}")
                    if dest:
                        try:
                            os.makedirs(dest, exist_ok=True)
                            shutil.copy(sub['filepath'], dest)
                            st.success(f"Copied {sub['filename']} to {dest}")
                            log_action(f"Teacher {username} copied {sub['filename']} to {dest}")
                        except Exception as e:
                            st.error(f"Failed to copy: {e}")
            with col2:
                st.write("Download disabled per requirements.")
    else:
        st.info("No submissions yet.")

    if st.button("Logout"):
        st.session_state.logged_user = None
        st.experimental_rerun()

# ----- STUDENT PORTAL -----
def student_portal():
    st.header("Student Exam Submission Portal")

    if not st.session_state.teachers:
        st.warning("No teachers registered yet.")
        return

    teachers_list = list(st.session_state.teachers.keys())
    teacher_choice = st.selectbox("Select Teacher", ["--Select--"] + teachers_list)
    if teacher_choice == "--Select--":
        return

    passcode_input = st.text_input("Enter Exam Passcode")
    student_id = st.text_input("Enter Your Unique Student ID")
    uploaded_file = st.file_uploader("Upload your answer file (pdf, docx)", type=["pdf", "docx"])

    if st.button("Submit"):
        if teacher_choice == "--Select--" or not passcode_input or not student_id or not uploaded_file:
            st.warning("All fields are required.")
            return

        # Validate passcode
        active_exams = st.session_state.active_exams
        if passcode_input not in active_exams:
            st.error("Invalid or expired passcode.")
            return

        exam = active_exams[passcode_input]
        teacher = st.session_state.teachers[exam["teacher"]]

        # Check exam time
        start_time = datetime.fromisoformat(exam["start_time"])
        now = datetime.now()
        if now > start_time + timedelta(minutes=exam["duration_mins"]):
            st.error("Exam time has ended.")
            return

        # Check uploads allowed
        if not exam.get("uploads_allowed", True):
            st.error("Uploads are disabled by the teacher.")
            return

        # Check duplicate submission by student_id or IP
        lab_dir = os.path.join(SUBMISSIONS_DIR, exam["lab_name"])
        os.makedirs(lab_dir, exist_ok=True)

        # Load all previous submissions student ids and ips from saved metadata (simulate by folder name & ip stored in a file)
        submissions = {}
        for student_folder in os.listdir(lab_dir):
            student_path = os.path.join(lab_dir, student_folder)
            if os.path.isdir(student_path):
                ip_file = os.path.join(student_path, "ip.txt")
                ip_val = None
                if os.path.exists(ip_file):
                    with open(ip_file, "r") as f:
                        ip_val = f.read().strip()
                submissions[student_folder] = ip_val

        client_ip = get_client_ip()
        # For demo, fallback if IP not available
        if client_ip == "127.0.0.1":
            client_ip = st.text_input("Enter your device IP (for duplicate check)")

        if student_id in submissions:
            st.error("You have already submitted.")
            return
        if client_ip and client_ip in submissions.values():
            st.error("A submission from this device IP has already been received.")
            return

        # Save file
        student_dir = os.path.join(lab_dir, student_id)
        os.makedirs(student_dir, exist_ok=True)
        file_path = os.path.join(student_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Save IP
        if client_ip:
            with open(os.path.join(student_dir, "ip.txt"), "w") as f:
                f.write(client_ip)

        log_action(f"Student {student_id} submitted file {uploaded_file.name} for lab {exam['lab_name']}")

        st.success("Submission successful! Good luck.")

# ----- MAIN APP -----
def main():
    st.set_page_config(page_title="Lab Exam Portal", layout="centered")
    st.title("📚 Lab Exam Portal")

    menu = ["Teacher Login", "Register Teacher", "Forgot Password (Teacher)", "Student Portal"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if st.session_state.logged_user and st.session_state.logged_user.get("role") == "teacher":
        if choice in ["Teacher Login", "Register Teacher", "Forgot Password (Teacher)"]:
            st.info("You are already logged in.")
            teacher_dashboard()
        else:
            if choice == "Student Portal":
                student_portal()
    else:
        if choice == "Teacher Login":
            login_teacher()
        elif choice == "Register Teacher":
            register_teacher()
        elif choice == "Forgot Password (Teacher)":
            forgot_password_teacher()
        elif choice == "Student Portal":
            student_portal()

if __name__ == "__main__":
    main()
