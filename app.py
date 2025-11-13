import streamlit as st
import os
import json
import hashlib
import random
import string
import socket
from datetime import datetime, timedelta
import shutil
import tempfile
import zipfile
import logging

# ----------- CONFIG -----------
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")


# ----------- UTILITIES -----------
def log(msg):
    logging.info(msg)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashval: str) -> bool:
    return hash_password(password) == hashval


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


def get_client_ip():
    # Try to get IP from Streamlit or fallback to local IP
    try:
        ip = st.request.remote_addr
        if ip:
            return ip
    except Exception:
        pass
    # fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def walk_submissions(lab):
    """
    Return list of submissions for a lab:
    Each item dict: student_id, filename, filepath, submission_time
    """
    lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
    if not os.path.exists(lab_folder):
        return []

    submissions = []
    for student_id in sorted(os.listdir(lab_folder)):
        student_folder = os.path.join(lab_folder, student_id)
        if not os.path.isdir(student_folder):
            continue
        for fname in sorted(os.listdir(student_folder)):
            fpath = os.path.join(student_folder, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                submissions.append({
                    "student_id": student_id,
                    "filename": fname,
                    "filepath": fpath,
                    "submitted_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
    return submissions


def save_teacher_data(data):
    save_json(TEACHERS_FILE, data)
    st.session_state.teachers = data


# ----------- SESSION STATE INIT -----------
if "teachers" not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE, {})

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None  # dict with keys: username, role='teacher'

if "otp_store" not in st.session_state:
    st.session_state.otp_store = {}  # key: contact, value: otp string

if "active_exams" not in st.session_state:
    # key: teacher username, value: dict with keys: passcode, start_time, duration_minutes, uploads_enabled (bool)
    st.session_state.active_exams = {}


# ----------- APP UI & LOGIC -----------

st.set_page_config(page_title="Lab Exam Portal", layout="wide")
st.title("🧪 Lab Exam Portal (Teacher & Student)")


# --- OTP functions ---
def send_otp(contact: str):
    otp = generate_otp()
    st.session_state.otp_store[contact] = otp
    log(f"OTP sent to {contact} (mock): {otp}")
    st.success(f"OTP sent to {contact}. (In a real system, this would be sent via SMS/email)")


def verify_otp(contact: str, otp_input: str) -> bool:
    real_otp = st.session_state.otp_store.get(contact)
    if real_otp and otp_input == real_otp:
        del st.session_state.otp_store[contact]
        return True
    return False


# --- User Registration ---
def register_teacher():
    st.header("👩‍🏫 Teacher Registration")
    username = st.text_input("Choose a username", key="reg_username")
    full_name = st.text_input("Full name", key="reg_full_name")
    phone = st.text_input("Phone number (for OTP verification)", key="reg_phone")
    lab_name = st.text_input("Assigned Lab Name", key="reg_lab_name")
    password = st.text_input("Choose a password", type="password", key="reg_password")
    password2 = st.text_input("Confirm password", type="password", key="reg_password2")

    if st.button("Register"):
        if not all([username, full_name, phone, lab_name, password, password2]):
            st.warning("Please fill in all fields.")
            return
        if password != password2:
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
            "password_hash": hashed
        }
        save_teacher_data(st.session_state.teachers)
        log(f"Teacher registered: {username}")
        st.success("Registration successful! You can now log in.")


# --- User Login ---
def login_teacher():
    st.header("👩‍🏫 Teacher Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if username not in st.session_state.teachers:
            st.error("Username not found.")
            return
        user = st.session_state.teachers[username]
        if not verify_password(password, user.get("password_hash", "")):
            st.error("Incorrect password.")
            return
        st.session_state.logged_user = {"username": username, "role": "teacher"}
        log(f"Teacher logged in: {username}")
        st.experimental_rerun()


# --- Forgot Password ---
def forgot_password_teacher():
    st.header("🔐 Teacher Forgot Password")
    username = st.text_input("Enter your username", key="forgot_username")
    if username and username not in st.session_state.teachers:
        st.error("Username not found.")
        return

    if not username:
        return

    phone = st.session_state.teachers[username]["phone"]

    if st.button("Send OTP"):
        send_otp(phone)

    otp = st.text_input("Enter OTP", key="forgot_otp")
    new_pass = st.text_input("Enter new password", type="password", key="forgot_new_pass")
    new_pass2 = st.text_input("Confirm new password", type="password", key="forgot_new_pass2")

    if st.button("Reset Password"):
        if not all([otp, new_pass, new_pass2]):
            st.warning("Fill all fields.")
            return
        if new_pass != new_pass2:
            st.warning("Passwords do not match.")
            return
        if verify_otp(phone, otp):
            st.session_state.teachers[username]["password_hash"] = hash_password(new_pass)
            save_teacher_data(st.session_state.teachers)
            log(f"Teacher password reset: {username}")
            st.success("Password reset successful! Please log in.")
        else:
            st.error("Invalid OTP.")


# --- Teacher Dashboard ---
def teacher_dashboard():
    user = st.session_state.logged_user
    username = user["username"]

    teachers = st.session_state.teachers
    if username not in teachers:
        st.error("Your teacher record was not found. Please log in again.")
        st.session_state.logged_user = None
        st.experimental_rerun()
        return

    teacher = teachers[username]
    full_name = teacher.get("full_name", "Unknown")
    lab = teacher.get("lab_name", "Unknown Lab")

    st.header(f"👩‍🏫 Teacher Dashboard: {full_name} ({username})")
    st.markdown(f"**Lab:** {lab}")

    # Manage Exam Time & Passcode
    st.subheader("Exam Settings")

    active_exam = st.session_state.active_exams.get(username)
    if not active_exam:
        # Create new exam
        duration_minutes = st.number_input("Set exam duration (minutes)", min_value=1, max_value=360, value=60, step=5)
        if st.button("Start Exam"):
            passcode = generate_passcode()
            start_time = datetime.now()
            st.session_state.active_exams[username] = {
                "passcode": passcode,
                "start_time": start_time.isoformat(),
                "duration": duration_minutes,
                "uploads_enabled": True
            }
            st.success(f"Exam started! Passcode: **{passcode}**")
            log(f"Teacher {username} started exam for lab {lab} with passcode {passcode} duration {duration_minutes}m")
            st.experimental_rerun()
    else:
        passcode = active_exam.get("passcode")
        start_time = datetime.fromisoformat(active_exam.get("start_time"))
        duration = active_exam.get("duration")
        uploads_enabled = active_exam.get("uploads_enabled", True)

        end_time = start_time + timedelta(minutes=duration)
        now = datetime.now()
        time_left = end_time - now

        st.markdown(f"**Current Passcode:** `{passcode}`")
        st.markdown(f"**Exam Duration:** {duration} minutes")
        st.markdown(f"**Exam Start:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**Exam Ends:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**Uploads Enabled:** {'Yes' if uploads_enabled else 'No'}")

        # Toggle uploads
        if st.button("Toggle Uploads On/Off"):
            st.session_state.active_exams[username]["uploads_enabled"] = not uploads_enabled
            save_teacher_data(teachers)
            log(f"Teacher {username} toggled uploads to {'enabled' if not uploads_enabled else 'disabled'}")
            st.experimental_rerun()

        # Extend exam
        extend_minutes = st.number_input("Extend exam by (minutes)", min_value=1, max_value=120, value=10)
        if st.button("Extend Exam Duration"):
            st.session_state.active_exams[username]["duration"] += extend_minutes
            save_teacher_data(teachers)
            log(f"Teacher {username} extended exam by {extend_minutes} minutes")
            st.experimental_rerun()

        # Delete Exam
        if st.button("Delete Exam (End & Remove Passcode)"):
            del st.session_state.active_exams[username]
            st.success("Exam deleted.")
            log(f"Teacher {username} deleted exam")
            st.experimental_rerun()

    # Show submissions table
    st.subheader("Student Submissions")

    submissions = walk_submissions(lab)

    if not submissions:
        st.info("No submissions yet.")
    else:
        # Show table with details + buttons for each file
        for idx, sub in enumerate(submissions, 1):
            cols = st.columns([1, 3, 2, 2])
            with cols[0]:
                st.write(idx)
            with cols[1]:
                st.write(sub["student_id"])
            with cols[2]:
                st.write(sub["filename"])
            with cols[3]:
                if st.button(f"Download {idx}"):
                    with open(sub["filepath"], "rb") as f:
                        data = f.read()
                    st.download_button(label=f"Download {sub['filename']}", data=data, file_name=sub["filename"])

        st.markdown("---")
        st.write("To copy a submission to a folder on the server or USB drive, enter the folder path below and press 'Copy'.")

        dest_folder = st.text_input("Destination folder path (absolute):")
        if st.button("Copy Submissions"):
            if not dest_folder:
                st.warning("Please enter destination folder path.")
            else:
                ensure_dir(dest_folder)
                copied = 0
                for sub in submissions:
                    try:
                        shutil.copy2(sub["filepath"], dest_folder)
                        copied += 1
                    except Exception as e:
                        st.error(f"Error copying file {sub['filename']}: {e}")
                st.success(f"Copied {copied} files to {dest_folder}")
                log(f"Teacher {username} copied {copied} submission files to {dest_folder}")

    if st.button("Logout"):
        st.session_state.logged_user = None
        st.experimental_rerun()


# --- Student Portal ---
def student_portal():
    st.header("🎓 Student Exam Submission")

    teachers = st.session_state.teachers
    if not teachers:
        st.warning("No teachers registered yet. Contact your instructor.")
        return

    teacher_usernames = list(teachers.keys())
    teacher_choice = st.selectbox("Select your Teacher", ["-- Select --"] + teacher_usernames)

    if teacher_choice == "-- Select --":
        st.info("Please select your teacher to continue.")
        return

    # Check if exam active for this teacher
    exam_info = st.session_state.active_exams.get(teacher_choice)
    if not exam_info:
        st.warning("No active exam found for selected teacher.")
        return

    passcode_entered = st.text_input("Enter Exam Passcode")

    # Validate passcode
    if passcode_entered != exam_info.get("passcode"):
        st.warning("Invalid passcode.")
        return

    # Check time window
    start_time = datetime.fromisoformat(exam_info.get("start_time"))
    duration = exam_info.get("duration")
    end_time = start_time + timedelta(minutes=duration)
    now = datetime.now()

    if now < start_time:
        st.warning("Exam has not started yet.")
        return
    if now > end_time:
        st.warning("Exam has ended.")
        return

    time_left = end_time - now
    st.info(f"Time remaining: {str(time_left).split('.')[0]} (HH:MM:SS)")

    student_id = st.text_input("Enter your Unique Student ID")

    uploaded_file = st.file_uploader("Upload your answer file (PDF, DOCX)", type=["pdf", "docx"])

    if st.button("Submit"):
        if not student_id:
            st.warning("Student ID is required.")
            return
        if not uploaded_file:
            st.warning("Please upload your answer file.")
            return

        if not exam_info.get("uploads_enabled", True):
            st.error("Uploads are currently disabled by the teacher.")
            return

        # Check duplicate submission by student_id or IP
        lab = teachers[teacher_choice]["lab_name"]
        submissions = walk_submissions(lab)

        client_ip = get_client_ip()
        ip_submitted = False
        id_submitted = False

        for sub in submissions:
            if sub["student_id"] == student_id:
                id_submitted = True
            # To implement IP check, we could store IP per submission in metadata file.
            # Here IP check is disabled because file system has no IP record. Could add a log file.
            # ip_submitted = ... (not implemented due to file-based system limits)

        if id_submitted:
            st.error("You have already submitted your exam.")
            return

        # Save submission
        lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
        student_folder = os.path.join(lab_folder, student_id)
        ensure_dir(student_folder)
        save_path = os.path.join(student_folder, uploaded_file.name)

        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        log(f"Student {student_id} submitted file '{uploaded_file.name}' for lab '{lab}' under teacher '{teacher_choice}' from IP {client_ip}")

        st.success("Submission successful! Good luck on your exam.")


# --- Main ---
def main():
    menu = ["Teacher Login", "Register Teacher", "Forgot Password (Teacher)", "Student Portal"]
    choice = st.sidebar.selectbox("Navigate", menu)

    if st.session_state.logged_user and st.session_state.logged_user.get("role") == "teacher":
        # Logged in teacher sees dashboard unless explicitly choose register or forgot password
        if choice in ["Register Teacher", "Forgot Password (Teacher)"]:
            if choice == "Register Teacher":
                register_teacher()
            else:
                forgot_password_teacher()
        else:
            teacher_dashboard()
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
