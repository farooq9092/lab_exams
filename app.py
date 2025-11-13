import streamlit as st
import os
import json
import shutil
import tempfile
import logging
from datetime import datetime, timedelta
import random
import string
import hashlib
import socket
import pandas as pd

# ------------- CONFIGURATION -------------------
APP_DATA_DIR = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA_DIR, "teachers.json")
SUBMISSIONS_DIR = os.path.join(APP_DATA_DIR, "submissions")
LOG_FILE = os.path.join(APP_DATA_DIR, "activity.log")

os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")

# ------------- UTILS -------------------

def record_log(msg: str):
    logging.info(msg)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def gen_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def get_client_ip():
    # This gets local IP, replace with real client IP logic if needed (e.g. via headers)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def walk_submissions(lab_folder):
    submissions = []
    if not os.path.exists(lab_folder):
        return submissions
    for student_id in sorted(os.listdir(lab_folder)):
        student_folder = os.path.join(lab_folder, student_id)
        if os.path.isdir(student_folder):
            for fname in sorted(os.listdir(student_folder)):
                fpath = os.path.join(student_folder, fname)
                if os.path.isfile(fpath):
                    mod_time = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                    submissions.append({
                        "student_id": student_id,
                        "filename": fname,
                        "filepath": fpath,
                        "mod_time": mod_time
                    })
    return submissions

# ------------- SESSION STATE INITIALIZATION -------------

if "teachers" not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE, {})

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "rerun_flag" not in st.session_state:
    st.session_state.rerun_flag = False

# ------------- PAGE CONFIG ----------------

st.set_page_config(page_title="Lab Exam Portal", layout="wide")
st.title("📚 Lab Exam Portal")

# ------------- AUTH ---------------------

def logout():
    st.session_state.logged_in_user = None
    st.session_state.rerun_flag = True

def rerun_if_needed():
    if st.session_state.get("rerun_flag", False):
        st.session_state.rerun_flag = False
        st.experimental_rerun()

# ------------- USER MANAGEMENT -----------------

def register_teacher():
    st.header("Register as Teacher")
    username = st.text_input("Username", key="reg_username")
    password = st.text_input("Password", type="password", key="reg_password")
    password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm")
    full_name = st.text_input("Full Name", key="reg_full_name")
    phone = st.text_input("Phone (for OTP, optional)", key="reg_phone")
    lab = st.text_input("Assigned Lab Name", key="reg_lab")

    if st.button("Register"):
        if not username or not password or not password_confirm or not full_name or not lab:
            st.warning("Please fill all required fields.")
            return
        if password != password_confirm:
            st.warning("Passwords do not match.")
            return
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
            return

        hashed_pw = hash_password(password)
        st.session_state.teachers[username] = {
            "password_hash": hashed_pw,
            "full_name": full_name,
            "phone": phone,
            "lab": lab,
            "exams": {}  # store exams here
        }
        save_json(TEACHERS_FILE, st.session_state.teachers)
        record_log(f"Teacher registered: {username}")
        st.success("Registration successful! Please login.")
        st.session_state.rerun_flag = True

def teacher_login():
    st.header("Teacher Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        user = st.session_state.teachers.get(username)
        if not user:
            st.error("User not found.")
            return
        if not verify_password(password, user["password_hash"]):
            st.error("Incorrect password.")
            return
        st.session_state.logged_in_user = username
        record_log(f"Teacher logged in: {username}")
        st.session_state.rerun_flag = True

# ------------- TEACHER DASHBOARD --------------

def teacher_dashboard():
    username = st.session_state.logged_in_user
    teacher = st.session_state.teachers[username]
    st.header(f"Teacher Dashboard - {teacher['full_name']} ({username})")

    col1, col2 = st.columns([3,1])
    with col1:
        st.subheader(f"Lab: {teacher['lab']}")
    with col2:
        if st.button("Logout"):
            logout()

    st.markdown("---")
    st.subheader("Manage Exams")

    exams = teacher.get("exams", {})

    # List existing exams
    if exams:
        st.write("Your Exams:")
        df_exams = pd.DataFrame([
            {
                "Passcode": code,
                "Lab": e["lab"],
                "Start Time": e["start_time"],
                "Duration (minutes)": e["duration"],
                "Active": e["active"]
            }
            for code, e in exams.items()
        ])
        st.dataframe(df_exams, use_container_width=True)

        delete_passcode = st.text_input("Enter Passcode of Exam to Delete", key="delete_passcode")
        if st.button("Delete Exam"):
            if delete_passcode in exams:
                del exams[delete_passcode]
                teacher["exams"] = exams
                st.session_state.teachers[username] = teacher
                save_json(TEACHERS_FILE, st.session_state.teachers)
                record_log(f"Teacher {username} deleted exam {delete_passcode}")
                st.success(f"Exam {delete_passcode} deleted.")
                st.experimental_rerun()
            else:
                st.warning("Passcode not found.")

    else:
        st.info("No exams created yet.")

    st.markdown("---")
    st.subheader("Create New Exam")

    new_duration = st.number_input("Duration (minutes)", min_value=1, max_value=180, value=30, step=1, key="new_duration")
    new_lab = teacher["lab"]  # fixed lab for teacher

    if st.button("Generate Exam Passcode and Start Exam"):
        passcode = gen_passcode()
        start_time = datetime.now().isoformat()
        new_exam = {
            "lab": new_lab,
            "start_time": start_time,
            "duration": new_duration,
            "active": True
        }
        exams[passcode] = new_exam
        teacher["exams"] = exams
        st.session_state.teachers[username] = teacher
        save_json(TEACHERS_FILE, st.session_state.teachers)
        record_log(f"Teacher {username} created new exam {passcode} with duration {new_duration} minutes")
        st.success(f"Exam created with passcode: {passcode}")
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Manage Existing Exams")

    if exams:
        selected_exam = st.selectbox("Select Exam Passcode", list(exams.keys()), key="selected_exam")
        if selected_exam:
            exam = exams[selected_exam]

            st.write(f"Passcode: **{selected_exam}**")
            st.write(f"Lab: **{exam['lab']}**")
            st.write(f"Start Time: **{exam['start_time']}**")
            st.write(f"Duration: **{exam['duration']} minutes**")
            st.write(f"Active: **{exam['active']}**")

            # Toggle active
            if st.button("Toggle Exam Active Status"):
                exam["active"] = not exam["active"]
                exams[selected_exam] = exam
                teacher["exams"] = exams
                st.session_state.teachers[username] = teacher
                save_json(TEACHERS_FILE, st.session_state.teachers)
                record_log(f"Teacher {username} toggled exam {selected_exam} active status to {exam['active']}")
                st.success(f"Exam active status is now {exam['active']}")
                st.experimental_rerun()

            # Extend duration
            extend_min = st.number_input("Extend Duration by Minutes", min_value=1, max_value=180, value=5, step=1, key="extend_min")
            if st.button("Extend Exam Duration"):
                exam["duration"] += extend_min
                exams[selected_exam] = exam
                teacher["exams"] = exams
                st.session_state.teachers[username] = teacher
                save_json(TEACHERS_FILE, st.session_state.teachers)
                record_log(f"Teacher {username} extended exam {selected_exam} duration by {extend_min} minutes")
                st.success(f"Exam duration extended by {extend_min} minutes")
                st.experimental_rerun()

            st.markdown("---")
            st.subheader("Student Submissions")

            lab_folder = os.path.join(SUBMISSIONS_DIR, exam["lab"])
            ensure_dir(lab_folder)
            submissions = walk_submissions(lab_folder)

            if not submissions:
                st.info("No submissions yet.")
            else:
                # Show full table: Student ID, Filename, Submission Time
                df_subs = pd.DataFrame(submissions)
                df_show = df_subs[["student_id", "filename", "mod_time"]]
                df_show.columns = ["Student ID", "Filename", "Submission Time"]
                st.dataframe(df_show, use_container_width=True)

                st.info("Download and individual file copy buttons disabled per requirement.")

                dest_folder = st.text_input("Copy ALL submissions to folder (absolute path)", key="copy_dest")
                if st.button("Copy All Submissions"):
                    if not dest_folder:
                        st.warning("Enter destination folder path.")
                    else:
                        try:
                            ensure_dir(dest_folder)
                            copied = 0
                            for sub in submissions:
                                shutil.copy2(sub["filepath"], dest_folder)
                                copied += 1
                            st.success(f"Copied {copied} files to {dest_folder}")
                            record_log(f"Teacher {username} copied all {copied} submissions for exam {selected_exam} to {dest_folder}")
                        except Exception as e:
                            st.error(f"Error copying files: {e}")

# ------------- STUDENT PORTAL ----------------

def student_portal():
    st.header("Student Exam Submission")
    teachers = st.session_state.teachers

    if not teachers:
        st.info("No teachers registered yet.")
        return

    teacher_list = list(teachers.keys())
    teacher_choice = st.selectbox("Select your teacher", ["-- Select --"] + teacher_list, key="student_teacher")

    if teacher_choice == "-- Select --":
        st.stop()

    passcode = st.text_input("Enter Exam Passcode", key="student_passcode").strip().upper()
    student_id = st.text_input("Enter your Unique Student ID", key="student_id")
    uploaded_file = st.file_uploader("Upload your answer file (PDF or DOCX)", type=["pdf", "docx"], key="student_file")

    if not passcode or not student_id:
        st.info("Please enter passcode and student ID to proceed.")
        st.stop()

    teacher_data = teachers.get(teacher_choice)
    if not teacher_data:
        st.error("Teacher data not found.")
        st.stop()

    exams = teacher_data.get("exams", {})
    exam = exams.get(passcode)

    if not exam:
        st.error("Invalid passcode.")
        st.stop()

    if not exam.get("active"):
        st.warning("Exam is not active yet. Please wait for teacher to start the exam.")
        st.stop()

    start_time = datetime.fromisoformat(exam["start_time"])
    duration = timedelta(minutes=exam["duration"])
    now = datetime.now()

    if now < start_time:
        st.warning("Exam has not started yet.")
        st.stop()

    elapsed = now - start_time
    remaining = duration - elapsed

    if remaining.total_seconds() <= 0:
        st.warning("Exam time is over. Submission not allowed.")
        st.stop()

    st.info(f"Time remaining: {str(remaining).split('.')[0]}")

    lab_folder = os.path.join(SUBMISSIONS_DIR, exam["lab"])
    ensure_dir(lab_folder)
    submissions = walk_submissions(lab_folder)
    client_ip = get_client_ip()

    # Load IP tracking
    ip_tracking_file = os.path.join(lab_folder, "submitted_ips.json")
    if os.path.exists(ip_tracking_file):
        submitted_ips = load_json(ip_tracking_file, {})
    else:
        submitted_ips = {}

    # Check duplicates by Student ID
    for sub in submissions:
        if sub["student_id"] == student_id:
            st.error("You have already submitted your paper with this Student ID.")
            st.stop()

    # Check duplicates by IP
    if client_ip in submitted_ips:
        st.error("A submission has already been made from your device/IP.")
        st.stop()

    if st.button("Submit Paper"):
        if not uploaded_file:
            st.warning("Please upload your answer file.")
            st.stop()

        student_folder = os.path.join(lab_folder, student_id)
        ensure_dir(student_folder)
        file_path = os.path.join(student_folder, uploaded_file.name)

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Record IP after submission
        submitted_ips[client_ip] = {
            "student_id": student_id,
            "timestamp": datetime.now().isoformat()
        }
        save_json(ip_tracking_file, submitted_ips)

        record_log(f"Student {student_id} submitted file {uploaded_file.name} for lab {exam['lab']} under teacher {teacher_choice}, IP: {client_ip}")
        st.success("Submission successful! Good luck!")

# ------------- MAIN APP ----------------

def main():
    rerun_if_needed()
    menu = ["Teacher Login", "Teacher Register", "Student Portal", "Logout"]

    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Teacher Login":
        if st.session_state.logged_in_user:
            teacher_dashboard()
        else:
            teacher_login()
    elif choice == "Teacher Register":
        register_teacher()
    elif choice == "Student Portal":
        student_portal()
    elif choice == "Logout":
        logout()
        st.info("Logged out.")
        st.experimental_rerun()

if __name__ == "__main__":
    main()
