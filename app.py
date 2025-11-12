import streamlit as st
import os
import json
import socket
import shutil
import zipfile
import tempfile
import logging
from datetime import datetime, timedelta
import random
import string
import hashlib

# ---------------- CONFIG ----------------
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------------- UTILITIES ----------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def gen_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def gen_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def record_log(msg):
    logging.info(msg)

def walk_lab_files(lab_folder):
    files_list = []
    if not os.path.exists(lab_folder):
        return files_list
    serial = 1
    for student in sorted(os.listdir(lab_folder)):
        sdir = os.path.join(lab_folder, student)
        if not os.path.isdir(sdir):
            continue
        for fname in sorted(os.listdir(sdir)):
            fpath = os.path.join(sdir, fname)
            if os.path.isfile(fpath):
                display = f"{serial}. {student} → {fname}"
                files_list.append({
                    "display": display,
                    "path": fpath,
                    "student": student,
                    "filename": fname,
                    "serial": serial
                })
                serial += 1
    return files_list

# ---------------- SESSION STATE INIT ----------------
if 'teachers' not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE, {})

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

if 'active_passcodes' not in st.session_state:
    st.session_state.active_passcodes = {}

if 'otp_store' not in st.session_state:
    st.session_state.otp_store = {}

if 'rerun_flag' not in st.session_state:
    st.session_state.rerun_flag = False

# ---------------- APP CONFIG ----------------
st.set_page_config(page_title="Lab Exam Portal", layout="centered")
st.title("📘 Lab Exam Portal")

# ---------------- AUTH HELPERS ----------------
def logout():
    st.session_state.logged_in_user = None
    st.session_state.rerun_flag = True

def log(action):
    user = st.session_state.logged_in_user or "Unknown"
    record_log(f"TEACHER {user}: {action}")

def rerun_if_flagged():
    return st.session_state.get('rerun_flag', False)

def clear_rerun_flag():
    st.session_state.rerun_flag = False

# ---------------- OTP HANDLING ----------------
def send_otp(user_contact):
    otp = gen_otp()
    st.session_state.otp_store[user_contact] = otp
    record_log(f"OTP sent to {user_contact} (simulated). OTP: {otp}")
    st.success(f"OTP sent to {user_contact}. (For demo, OTP shown here: {otp})")
    return otp

def verify_otp(user_contact, entered_otp):
    real_otp = st.session_state.otp_store.get(user_contact)
    if real_otp and entered_otp == real_otp:
        del st.session_state.otp_store[user_contact]
        return True
    return False

# ---------------- TEACHER USER MANAGEMENT ----------------
def register_teacher():
    st.header("🔑 Register New Teacher")
    username = st.text_input("Username", key="reg_teacher_username")
    password = st.text_input("Password", type="password", key="reg_teacher_password")
    password_confirm = st.text_input("Confirm Password", type="password", key="reg_teacher_password_confirm")
    name = st.text_input("Full Name", key="reg_teacher_name")
    phone = st.text_input("Phone (for OTP verification)", key="reg_teacher_phone")
    lab = st.text_input("Assigned Lab Name", key="reg_teacher_lab")

    if st.button("Register Teacher"):
        if not username or not password or not name or not lab:
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
            "password_hash": hashed,
            "name": name,
            "phone": phone,
            "lab": lab,
            "uploads_allowed": True,
            "exam_start": None,
            "exam_end": None,
        }
        save_json(TEACHERS_FILE, st.session_state.teachers)
        log(f"Registered new teacher {username}")
        st.success("Teacher registered successfully! Please login.")
        st.session_state.rerun_flag = True

def login_teacher():
    st.header("🔒 Teacher Login")
    username = st.text_input("Username", key="login_teacher_username")
    password = st.text_input("Password", type="password", key="login_teacher_password")

    if st.button("Login"):
        user = st.session_state.teachers.get(username)
        if not user:
            st.error("Teacher not found.")
            return
        if verify_password(password, user["password_hash"]):
            st.session_state.logged_in_user = username
            log("Logged in")
            st.session_state.rerun_flag = True
        else:
            st.error("Invalid password.")

def forgot_teacher_password():
    st.header("🔐 Forgot Password")
    username = st.text_input("Enter your username", key="forgot_teacher_username")
    if username and username not in st.session_state.teachers:
        st.error("Username not found.")
        return
    contact_info = st.session_state.teachers.get(username, {}).get("phone", "")
    if not contact_info and username:
        st.error("No phone number found to send OTP.")
        return
    if st.button("Send OTP"):
        send_otp(contact_info)
    otp_input = st.text_input("Enter OTP", key="forgot_teacher_otp")
    new_pass = st.text_input("New Password", type="password", key="forgot_teacher_newpass")
    confirm_pass = st.text_input("Confirm New Password", type="password", key="forgot_teacher_confirmpass")
    if st.button("Reset Password"):
        if not otp_input or not new_pass or not confirm_pass:
            st.warning("Fill all fields.")
            return
        if new_pass != confirm_pass:
            st.warning("Passwords do not match.")
            return
        if verify_otp(contact_info, otp_input):
            st.session_state.teachers[username]["password_hash"] = hash_password(new_pass)
            save_json(TEACHERS_FILE, st.session_state.teachers)
            log(f"Password reset for {username}")
            st.success("Password reset successful! Please login.")
            st.session_state.rerun_flag = True
        else:
            st.error("Invalid OTP.")

# ---------------- TEACHER DASHBOARD ----------------
def teacher_dashboard():
    st.header(f"👩‍🏫 Teacher Dashboard - {st.session_state.logged_in_user}")
    teacher = st.session_state.logged_in_user
    teacher_data = st.session_state.teachers.get(teacher)

    if not teacher_data:
        st.error("Teacher data missing, please logout and login again.")
        return

    lab = teacher_data.get("lab")
    st.subheader(f"Lab: {lab}")

    # Exam timing management
    col1, col2, col3 = st.columns(3)
    with col1:
        exam_start = st.date_input("Exam Start Date", value=datetime.now().date(), key="exam_start_date")
        exam_start_time = st.time_input("Start Time", value=datetime.now().time(), key="exam_start_time")
    with col2:
        exam_end = st.date_input("Exam End Date", value=datetime.now().date(), key="exam_end_date")
        exam_end_time = st.time_input("End Time", value=(datetime.now() + timedelta(hours=1)).time(), key="exam_end_time")
    with col3:
        if st.button("Set Exam Time"):
            start_dt = datetime.combine(exam_start, exam_start_time)
            end_dt = datetime.combine(exam_end, exam_end_time)
            if end_dt <= start_dt:
                st.warning("End time must be after start time.")
            else:
                teacher_data['exam_start'] = start_dt.isoformat()
                teacher_data['exam_end'] = end_dt.isoformat()
                save_json(TEACHERS_FILE, st.session_state.teachers)
                st.success(f"Exam time set: {start_dt} to {end_dt}")
                log(f"Set exam time: {start_dt} - {end_dt}")
                st.session_state.rerun_flag = True

    # Extend exam duration
    st.markdown("---")
    st.subheader("Extend Exam Duration")
    extend_minutes = st.number_input("Add minutes to exam end time", min_value=1, max_value=1440, step=10)
    if st.button("Extend Exam"):
        if not teacher_data.get('exam_end'):
            st.warning("Set exam time first.")
        else:
            current_end = datetime.fromisoformat(teacher_data['exam_end'])
            new_end = current_end + timedelta(minutes=extend_minutes)
            teacher_data['exam_end'] = new_end.isoformat()
            save_json(TEACHERS_FILE, st.session_state.teachers)
            st.success(f"Exam extended till {new_end}")
            log(f"Extended exam till {new_end}")
            st.session_state.rerun_flag = True

    # Passcode management
    st.markdown("---")
    st.subheader("Exam Passcode")
    if st.button("Generate New Passcode"):
        code = gen_passcode()
        now = datetime.now()
        start = datetime.fromisoformat(teacher_data.get('exam_start')) if teacher_data.get('exam_start') else now
        end = datetime.fromisoformat(teacher_data.get('exam_end')) if teacher_data.get('exam_end') else now + timedelta(hours=1)
        st.session_state.active_passcodes[code] = {
            "teacher": teacher,
            "lab": lab,
            "start": start.isoformat(),
            "end": end.isoformat()
        }
        st.success(f"New Passcode: {code}")
        log(f"Generated passcode {code}")

    st.write("Active Passcodes:")
    for code, info in st.session_state.active_passcodes.items():
        if info["teacher"] == teacher:
            st.write(f"- {code}: Valid from {info['start']} to {info['end']}")

    # Upload enable/disable
    uploads_allowed = teacher_data.get("uploads_allowed", True)
    if st.button("Toggle Uploads (Currently: {})".format("Enabled" if uploads_allowed else "Disabled")):
        teacher_data["uploads_allowed"] = not uploads_allowed
        save_json(TEACHERS_FILE, st.session_state.teachers)
        st.success(f"Uploads {'enabled' if not uploads_allowed else 'disabled'}.")
        st.session_state.rerun_flag = True

    # Submissions management
    st.markdown("---")
    st.subheader("Student Submissions")

    lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
    ensure_dir(lab_folder)
    files = walk_lab_files(lab_folder)

    if not files:
        st.info("No submissions yet.")
    else:
        sel_all = st.checkbox("Select All Submissions")
        display_list = [f["display"] for f in files]
        if sel_all:
            selected = st.multiselect("Selected Files", display_list, default=display_list)
        else:
            selected = st.multiselect("Selected Files", display_list)

        selected_paths = [f["path"] for f in files if f["display"] in selected]

        for f in files:
            with st.expander(f["display"]):
                with open(f["path"], "rb") as fh:
                    st.download_button(label="Download File", data=fh, file_name=f["filename"])

        # Copy to folder on server or USB (path must be accessible)
        st.markdown("### Copy Selected Submissions")
        dest = st.text_input("Destination Folder Path (absolute)")
        if st.button("Copy Selected Files"):
            if not selected_paths:
                st.warning("Select files first.")
            elif not dest:
                st.warning("Enter destination path.")
            else:
                try:
                    ensure_dir(dest)
                    count = 0
                    for p in selected_paths:
                        shutil.copy(p, dest)
                        count += 1
                    st.success(f"Copied {count} files to {dest}")
                    log(f"Copied {count} files to {dest}")
                except Exception as e:
                    st.error(f"Copy failed: {e}")

        # Download selected as ZIP
        if st.button("Download Selected as ZIP"):
            if not selected_paths:
                st.warning("Select files first.")
            else:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                with zipfile.ZipFile(tmp.name, "w") as zf:
                    for p in selected_paths:
                        zf.write(p, arcname=os.path.basename(p))
                with open(tmp.name, "rb") as zf:
                    st.download_button("Download ZIP", zf.read(), file_name=f"submissions_{lab}.zip")
                os.unlink(tmp.name)

    # Logout button
    if st.button("Logout"):
        logout()

# ---------------- STUDENT PORTAL ----------------
def student_portal():
    st.header("🎓 Student Exam Submission")

    teachers = st.session_state.teachers
    if not teachers:
        st.info("No teachers registered yet. Please contact your instructor.")
        return

    teacher_list = list(teachers.keys())
    teacher_choice = st.selectbox("Select Teacher", ["-- Select --"] + teacher_list)
    passcode = st.text_input("Enter Exam Passcode (provided by teacher)")
    student_id = st.text_input("Enter Your Unique Student ID")
    uploaded = st.file_uploader("Upload Your Answer File (PDF or DOCX)", type=["pdf", "docx"])

    server_ip = get_server_ip()

    # Show countdown timer if passcode valid and exam active
    if passcode in st.session_state.active_passcodes:
        pass_info = st.session_state.active_passcodes[passcode]
        now = datetime.now()
        start = datetime.fromisoformat(pass_info['start'])
        end = datetime.fromisoformat(pass_info['end'])
        if start <= now <= end:
            remaining = end - now
            st.info(f"Time Remaining: {str(remaining).split('.')[0]} (HH:MM:SS)")
        else:
            st.warning("Exam is not active at this time for this passcode.")

    if st.button("Submit Paper"):
        if teacher_choice == "-- Select --" or not teacher_choice:
            st.warning("Please select your teacher.")
            return
        if passcode not in st.session_state.active_passcodes:
            st.error("Invalid or expired passcode.")
            return
        pass_info = st.session_state.active_passcodes[passcode]
        if pass_info["teacher"] != teacher_choice:
            st.error("Passcode does not match selected teacher.")
            return

        if not student_id.strip():
            st.warning("Enter your student ID.")
            return

        if uploaded is None:
            st.warning("Upload your answer file.")
            return

        # Check exam active timing
        now = datetime.now()
        start = datetime.fromisoformat(pass_info['start'])
        end = datetime.fromisoformat(pass_info['end'])
        if not (start <= now <= end):
            st.error("Exam time has ended or not started.")
            return

        # Check if uploads allowed for teacher
        teacher_data = st.session_state.teachers.get(teacher_choice)
        if not teacher_data or not teacher_data.get("uploads_allowed", True):
            st.error("Uploads are currently disabled by the teacher.")
            return

        # Prevent duplicate submission by student ID or IP for this teacher and lab
        lab = teacher_data.get("lab")
        submission_dir = os.path.join(SUBMISSIONS_ROOT, lab, student_id.strip())
        ensure_dir(submission_dir)

        # Check existing submissions by student ID
        existing_files = os.listdir(submission_dir) if os.path.exists(submission_dir) else []

        ip_file = os.path.join(SUBMISSIONS_ROOT, lab, "ip_submissions.json")
        ip_subs = load_json(ip_file, {})

        if student_id.strip() in ip_subs and ip_subs[student_id.strip()] == server_ip:
            st.warning("You have already submitted for this exam from this IP.")
            return

        if existing_files:
            st.warning("You have already submitted your paper.")
            return

        # Save file
        file_path = os.path.join(submission_dir, uploaded.name)
        with open(file_path, "wb") as f:
            f.write(uploaded.getbuffer())

        # Save IP record
        ip_subs[student_id.strip()] = server_ip
        save_json(ip_file, ip_subs)

        st.success(f"Submission received. Thank you!")
        record_log(f"Student {student_id.strip()} submitted exam for lab {lab} via teacher {teacher_choice}")

        st.session_state.rerun_flag = True

# ---------------- MAIN APP ----------------
def main():
    if rerun_if_flagged():
        clear_rerun_flag()
        st.experimental_rerun()

    if st.session_state.logged_in_user:
        teacher_dashboard()
    else:
        menu = st.sidebar.selectbox("Choose Action", [
            "Student Portal",
            "Teacher Login",
            "Register Teacher",
            "Forgot Teacher Password",
        ])

        if menu == "Student Portal":
            student_portal()
        elif menu == "Teacher Login":
            login_teacher()
        elif menu == "Register Teacher":
            register_teacher()
        elif menu == "Forgot Teacher Password":
            forgot_teacher_password()

if __name__ == "__main__":
    main()
