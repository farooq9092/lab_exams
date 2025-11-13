import streamlit as st
import os
import json
import hashlib
import random
import string
from datetime import datetime, timedelta
import socket

# --- Constants ---
DATA_DIR = "data"
TEACHERS_FILE = os.path.join(DATA_DIR, "teachers.json")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

# --- Utils ---

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_password(pw, hashed):
    return hash_password(pw) == hashed

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return default
    else:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_client_ip():
    # Attempt to get client IP, fallback to localhost
    try:
        ip = st.runtime.scriptrunner.get_request().remote_addr
        if ip:
            return ip
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# --- Load data ---
teachers = load_json(TEACHERS_FILE, {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None  # username

if "active_exams" not in st.session_state:
    # Structure: {username: {passcode, start_time, duration, enabled, lab_name}}
    st.session_state.active_exams = {}

# --- Pages ---

def register_teacher():
    st.title("Teacher Registration")
    username = st.text_input("Username")
    fullname = st.text_input("Full Name")
    labname = st.text_input("Lab Name")
    password = st.text_input("Password", type="password")
    password2 = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if not username or not fullname or not labname or not password or not password2:
            st.error("Please fill all fields")
            return
        if password != password2:
            st.error("Passwords do not match")
            return
        if username in teachers:
            st.error("Username already exists")
            return
        teachers[username] = {
            "fullname": fullname,
            "labname": labname,
            "password_hash": hash_password(password)
        }
        save_json(TEACHERS_FILE, teachers)
        st.success("Registered successfully. You can login now.")

def login_teacher():
    st.title("Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username not in teachers:
            st.error("Username not found")
            return
        if not verify_password(password, teachers[username]["password_hash"]):
            st.error("Incorrect password")
            return
        st.session_state.logged_in = True
        st.session_state.user = username
        st.success(f"Welcome {teachers[username]['fullname']}!")
        st.experimental_rerun()

def teacher_dashboard():
    username = st.session_state.user
    teacher = teachers.get(username, None)
    if not teacher:
        st.error("Teacher info missing! Please login again.")
        st.session_state.logged_in = False
        st.session_state.user = None
        st.experimental_rerun()
        return

    st.title(f"Teacher Dashboard - {teacher['fullname']}")

    labname = teacher.get("labname", "")
    st.write(f"Lab: **{labname}**")

    # Exam control
    exam = st.session_state.active_exams.get(username)
    if exam is None:
        st.subheader("Create New Exam")
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=180, value=30)
        if st.button("Start Exam"):
            passcode = generate_passcode()
            st.session_state.active_exams[username] = {
                "passcode": passcode,
                "start_time": datetime.now().isoformat(),
                "duration": duration,
                "enabled": True,
                "labname": labname
            }
            st.success(f"Exam started! Passcode: **{passcode}**")
            st.experimental_rerun()
    else:
        st.subheader("Active Exam Details")
        st.write(f"Passcode: `{exam['passcode']}`")
        start_time = datetime.fromisoformat(exam["start_time"])
        duration = exam["duration"]
        enabled = exam["enabled"]
        end_time = start_time + timedelta(minutes=duration)
        now = datetime.now()
        remaining = end_time - now
        if remaining.total_seconds() < 0:
            st.warning("Exam has ended.")
        else:
            st.info(f"Time remaining: {str(remaining).split('.')[0]}")

        st.write(f"Uploads Enabled: {'✅' if enabled else '❌'}")
        if st.button("Toggle Uploads"):
            st.session_state.active_exams[username]["enabled"] = not enabled
            st.experimental_rerun()

        extend = st.number_input("Extend exam by minutes", min_value=1, max_value=120, value=5)
        if st.button("Extend Exam"):
            st.session_state.active_exams[username]["duration"] += extend
            st.success(f"Extended by {extend} minutes")
            st.experimental_rerun()

        if st.button("Delete Exam"):
            del st.session_state.active_exams[username]
            st.success("Exam deleted")
            st.experimental_rerun()

    # Show submissions
    st.subheader("Student Submissions")
    submissions_path = os.path.join(SUBMISSIONS_DIR, labname)
    if not os.path.exists(submissions_path):
        st.info("No submissions yet.")
    else:
        submissions = []
        for student_id in sorted(os.listdir(submissions_path)):
            student_folder = os.path.join(submissions_path, student_id)
            if os.path.isdir(student_folder):
                for fname in os.listdir(student_folder):
                    fpath = os.path.join(student_folder, fname)
                    timestamp = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                    submissions.append((student_id, fname, fpath, timestamp))

        if len(submissions) == 0:
            st.info("No submissions yet.")
        else:
            for i, (sid, fname, fpath, ts) in enumerate(submissions, 1):
                st.write(f"{i}. Student ID: {sid} | File: {fname} | Submitted at: {ts}")
                # Show download button without exposing path, disable copy by not showing raw file contents
                with open(fpath, "rb") as f:
                    file_bytes = f.read()
                st.download_button(label=f"Download File #{i}", data=file_bytes, file_name=fname)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.experimental_rerun()

def student_portal():
    st.title("Student Exam Portal")

    if len(teachers) == 0:
        st.warning("No teachers registered. Contact your instructor.")
        return

    teacher_list = list(teachers.keys())
    selected_teacher = st.selectbox("Select your Teacher", ["--Select--"] + teacher_list)
    if selected_teacher == "--Select--" or selected_teacher == "":
        st.info("Please select your teacher")
        return

    exam = st.session_state.active_exams.get(selected_teacher)
    if not exam:
        st.warning("No active exam for this teacher.")
        return

    start_time = datetime.fromisoformat(exam["start_time"])
    duration = exam["duration"]
    enabled = exam["enabled"]
    end_time = start_time + timedelta(minutes=duration)
    now = datetime.now()

    # Passcode check
    passcode_input = st.text_input("Enter Exam Passcode")
    if passcode_input != exam["passcode"]:
        if passcode_input != "":
            st.error("Invalid passcode.")
        return

    if now < start_time:
        st.warning("Exam has not started yet.")
        return
    if now > end_time:
        st.warning("Exam has ended.")
        return
    if not enabled:
        st.warning("Uploads are currently disabled.")
        return

    st.info(f"Time remaining: {str(end_time - now).split('.')[0]}")

    student_id = st.text_input("Enter your Student ID")
    uploaded_file = st.file_uploader("Upload your file (PDF, DOCX)", type=["pdf", "docx"])

    if st.button("Submit"):
        if not student_id.strip():
            st.error("Student ID is required")
            return
        if uploaded_file is None:
            st.error("Please upload a file")
            return

        labname = teachers[selected_teacher]["labname"]
        # Check duplicate submission by student id
        lab_sub_dir = os.path.join(SUBMISSIONS_DIR, labname)
        ensure_dir(lab_sub_dir)
        # Check student folder existence
        student_folder = os.path.join(lab_sub_dir, student_id)
        if os.path.exists(student_folder):
            st.error("You have already submitted.")
            return

        # Check duplicate IP submission
        ip = get_client_ip()
        ip_record_file = os.path.join(lab_sub_dir, "ip_submissions.json")
        ip_records = load_json(ip_record_file, {})
        if ip in ip_records:
            st.error("A submission from your IP address has already been recorded.")
            return

        # Save file
        ensure_dir(student_folder)
        save_path = os.path.join(student_folder, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Save IP record
        ip_records[ip] = {
            "student_id": student_id,
            "filename": uploaded_file.name,
            "submitted_at": now.isoformat()
        }
        save_json(ip_record_file, ip_records)

        st.success("Submission successful. Best of luck!")
        st.experimental_rerun()

# --- Main ---

def main():
    st.sidebar.title("SZABIST Lab Exam")
    menu = st.sidebar.selectbox("Navigate", ["Teacher Login", "Register Teacher", "Student Portal"])

    if st.session_state.logged_in:
        if menu == "Teacher Login" or menu == "Register Teacher":
            # If logged in teacher tries to access login/register, show dashboard instead
            teacher_dashboard()
        else:
            student_portal()
    else:
        if menu == "Teacher Login":
            login_teacher()
        elif menu == "Register Teacher":
            register_teacher()
        elif menu == "Student Portal":
            student_portal()

if __name__ == "__main__":
    main()
