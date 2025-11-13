import streamlit as st
import os
import json
import hashlib
import random
import string
from datetime import datetime, timedelta
import socket
import logging

# --- CONFIG ---
DATA_DIR = "app_data"
TEACHERS_FILE = os.path.join(DATA_DIR, "teachers.json")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
LOG_FILE = os.path.join(DATA_DIR, "activity.log")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

# --- Logging setup ---
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(message)s")


def log(message):
    logging.info(message)


# --- Utility functions ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def get_client_ip():
    # Best effort IP detection fallback
    try:
        return st.runtime.scriptrunner.get_request().remote_addr
    except:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_teacher_data():
    return load_json(TEACHERS_FILE, {})


def save_teacher_data(data):
    save_json(TEACHERS_FILE, data)


def get_submissions(lab_name):
    lab_path = os.path.join(SUBMISSIONS_DIR, lab_name)
    if not os.path.exists(lab_path):
        return []

    submissions = []
    for student_id in sorted(os.listdir(lab_path)):
        student_folder = os.path.join(lab_path, student_id)
        if os.path.isdir(student_folder):
            for fname in sorted(os.listdir(student_folder)):
                fpath = os.path.join(student_folder, fname)
                if os.path.isfile(fpath):
                    timestamp = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                    submissions.append({
                        "student_id": student_id,
                        "filename": fname,
                        "filepath": fpath,
                        "submitted_at": timestamp
                    })
    return submissions


# --- Session State Initialization ---
if "teachers" not in st.session_state:
    st.session_state.teachers = get_teacher_data()

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None  # {"username": ..., "role": "teacher"}

if "active_exams" not in st.session_state:
    # Structure: {username: {"passcode": str, "start_time": ISO str, "duration": int, "uploads_enabled": bool, "lab_name": str}}
    st.session_state.active_exams = {}


# --- Teacher Register ---
def register_teacher():
    st.header("👩‍🏫 Teacher Registration")

    username = st.text_input("Choose username", key="reg_username")
    full_name = st.text_input("Full Name", key="reg_fullname")
    lab_name = st.text_input("Lab Name", key="reg_labname")
    password = st.text_input("Password", type="password", key="reg_pass")
    password_confirm = st.text_input("Confirm Password", type="password", key="reg_pass_confirm")

    if st.button("Register"):
        if not all([username, full_name, lab_name, password, password_confirm]):
            st.warning("All fields are required.")
            return

        if password != password_confirm:
            st.warning("Passwords do not match.")
            return

        if username in st.session_state.teachers:
            st.warning("Username already exists.")
            return

        hashed_pw = hash_password(password)
        st.session_state.teachers[username] = {
            "full_name": full_name,
            "lab_name": lab_name,
            "password_hash": hashed_pw
        }
        save_teacher_data(st.session_state.teachers)
        log(f"Teacher registered: {username}")
        st.success("Registration successful. You can now login.")


# --- Teacher Login ---
def login_teacher():
    st.header("👩‍🏫 Teacher Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if username not in st.session_state.teachers:
            st.error("Username not found.")
            return

        teacher = st.session_state.teachers[username]
        if not verify_password(password, teacher.get("password_hash", "")):
            st.error("Incorrect password.")
            return

        st.session_state.logged_user = {"username": username, "role": "teacher"}
        log(f"Teacher logged in: {username}")
        st.experimental_rerun()


# --- Teacher Password Reset ---
def reset_password():
    st.header("🔐 Teacher Password Reset")
    username = st.text_input("Enter your username", key="reset_username")
    if not username:
        return
    if username not in st.session_state.teachers:
        st.error("Username not found.")
        return

    new_pass = st.text_input("New Password", type="password", key="reset_new_pass")
    new_pass_confirm = st.text_input("Confirm New Password", type="password", key="reset_new_pass_confirm")

    if st.button("Reset Password"):
        if not all([new_pass, new_pass_confirm]):
            st.warning("Please fill all fields.")
            return
        if new_pass != new_pass_confirm:
            st.warning("Passwords do not match.")
            return
        st.session_state.teachers[username]["password_hash"] = hash_password(new_pass)
        save_teacher_data(st.session_state.teachers)
        log(f"Teacher password reset: {username}")
        st.success("Password reset successful. You can login now.")


# --- Teacher Dashboard ---
def teacher_dashboard():
    user = st.session_state.logged_user
    username = user["username"]
    teacher = st.session_state.teachers.get(username)

    if teacher is None:
        st.error("Teacher data not found. Please login again.")
        st.session_state.logged_user = None
        st.experimental_rerun()
        return

    lab_name = teacher.get("lab_name", None)
    if not lab_name:
        st.error("Lab name missing in your profile. Contact admin.")
        return

    st.header(f"👩‍🏫 Teacher Dashboard: {teacher['full_name']} ({username})")
    st.write(f"**Lab:** {lab_name}")

    # Active exam info for this teacher
    exam = st.session_state.active_exams.get(username)

    # Start exam section
    st.subheader("Exam Settings")
    if exam is None:
        duration = st.number_input("Set exam duration (minutes)", min_value=1, max_value=180, value=30, step=5)
        if st.button("Start Exam"):
            passcode = generate_passcode()
            start_time = datetime.now()
            st.session_state.active_exams[username] = {
                "passcode": passcode,
                "start_time": start_time.isoformat(),
                "duration": duration,
                "uploads_enabled": True,
                "lab_name": lab_name
            }
            log(f"Teacher {username} started exam for lab {lab_name} with passcode {passcode}")
            st.success(f"Exam started! Passcode: **{passcode}**")
            st.experimental_rerun()
    else:
        start_time = datetime.fromisoformat(exam["start_time"])
        duration = exam["duration"]
        uploads_enabled = exam["uploads_enabled"]
        passcode = exam["passcode"]
        end_time = start_time + timedelta(minutes=duration)
        now = datetime.now()
        time_left = end_time - now

        st.markdown(f"**Current Passcode:** `{passcode}`")
        st.markdown(f"**Exam Duration:** {duration} minutes")
        st.markdown(f"**Exam Start Time:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**Exam End Time:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**Uploads Enabled:** {'✅' if uploads_enabled else '❌'}")

        if time_left.total_seconds() > 0:
            st.info(f"Time remaining: {str(time_left).split('.')[0]} (HH:MM:SS)")
        else:
            st.warning("Exam time has ended.")

        if st.button("Toggle Uploads Enable/Disable"):
            st.session_state.active_exams[username]["uploads_enabled"] = not uploads_enabled
            st.experimental_rerun()

        extend = st.number_input("Extend exam by (minutes)", min_value=1, max_value=120, value=10)
        if st.button("Extend Exam Duration"):
            st.session_state.active_exams[username]["duration"] += extend
            log(f"Teacher {username} extended exam by {extend} minutes")
            st.experimental_rerun()

        if st.button("Delete Exam"):
            del st.session_state.active_exams[username]
            st.success("Exam deleted.")
            log(f"Teacher {username} deleted exam")
            st.experimental_rerun()

    # Show student submissions
    st.subheader("Student Submissions")
    submissions = get_submissions(lab_name)

    if not submissions:
        st.info("No submissions yet.")
    else:
        st.dataframe(
            [
                {
                    "Index": i+1,
                    "Student ID": s["student_id"],
                    "Filename": s["filename"],
                    "Submitted At": s["submitted_at"]
                } for i, s in enumerate(submissions)
            ], width=900, height=300
        )

        # Download buttons
        for idx, sub in enumerate(submissions):
            with open(sub["filepath"], "rb") as f:
                file_bytes = f.read()
            st.download_button(
                label=f"Download File #{idx+1}: {sub['filename']}",
                data=file_bytes,
                file_name=sub["filename"],
                key=f"dl_{idx}"
            )

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

    teacher_list = list(teachers.keys())
    selected_teacher = st.selectbox("Select your teacher", ["--Select--"] + teacher_list)

    if selected_teacher == "--Select--":
        st.info("Please select your teacher to continue.")
        return

    # Check if active exam for this teacher
    exam = st.session_state.active_exams.get(selected_teacher)
    if not exam:
        st.warning("No active exam for this teacher.")
        return

    # Check exam time validity
    start_time = datetime.fromisoformat(exam["start_time"])
    duration = exam["duration"]
    uploads_enabled = exam["uploads_enabled"]
    end_time = start_time + timedelta(minutes=duration)
    now = datetime.now()

    # Enter passcode
    passcode_entered = st.text_input("Enter exam passcode", key="student_passcode")

    if not passcode_entered:
        st.info("Enter exam passcode to proceed.")
        return

    if passcode_entered != exam["passcode"]:
        st.error("Incorrect passcode.")
        return

    # Check exam timing
    if now < start_time:
        st.warning("Exam has not started yet.")
        return

    if now > end_time:
        st.warning("Exam has ended.")
        return

    if not uploads_enabled:
        st.warning("Uploads are currently disabled by the teacher. Try again later.")
        return

    time_left = end_time - now
    st.info(f"Time remaining: {str(time_left).split('.')[0]} (HH:MM:SS)")

    # Upload form
    student_id = st.text_input("Enter your Student ID")
    uploaded_file = st.file_uploader("Upload your answer file (PDF, DOCX)", type=["pdf", "docx"])

    if st.button("Submit"):
        if not student_id:
            st.warning("Student ID is required.")
            return
        if not uploaded_file:
            st.warning("Please upload your answer file.")
            return

        # Check duplicates by Student ID and IP
        lab_name = teachers[selected_teacher]["lab_name"]
        submissions = get_submissions(lab_name)
        client_ip = get_client_ip()

        for sub in submissions:
            if sub["student_id"] == student_id:
                st.error("You have already submitted.")
                return

        # Also check if IP has already submitted for this lab (single submission per IP)
        ip_submissions_file = os.path.join(SUBMISSIONS_DIR, lab_name, "ip_submissions.json")
        ip_submissions = load_json(ip_submissions_file, {})

        if client_ip in ip_submissions:
            st.error("A submission from your network IP has already been received.")
            return

        # Save submission
        student_folder = os.path.join(SUBMISSIONS_DIR, lab_name, student_id)
        ensure_dir(student_folder)
        save_path = os.path.join(student_folder, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Register IP submission to block duplicates
        ip_submissions[client_ip] = {
            "student_id": student_id,
            "filename": uploaded_file.name,
            "submitted_at": datetime.now().isoformat()
        }
        save_json(ip_submissions_file, ip_submissions)

        log(f"Student {student_id} submitted '{uploaded_file.name}' for lab {lab_name} under teacher {selected_teacher} from IP {client_ip}")

        st.success("Submission successful! Good luck.")
        st.experimental_rerun()


# --- Main Application ---
def main():
    st.sidebar.title("Navigation")
    menu_options = ["Teacher Login", "Register Teacher", "Reset Password", "Student Portal"]
    choice = st.sidebar.selectbox("Go to", menu_options)

    if st.session_state.logged_user and st.session_state.logged_user.get("role") == "teacher":
        # Logged-in teacher only sees dashboard except if register or reset requested
        if choice == "Register Teacher":
            register_teacher()
        elif choice == "Reset Password":
            reset_password()
        else:
            teacher_dashboard()
    else:
        if choice == "Teacher Login":
            login_teacher()
        elif choice == "Register Teacher":
            register_teacher()
        elif choice == "Reset Password":
            reset_password()
        elif choice == "Student Portal":
            student_portal()


if __name__ == "__main__":
    main()
