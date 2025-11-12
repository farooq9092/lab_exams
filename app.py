import streamlit as st
import os
import json
import hashlib
import random
import string
from datetime import datetime, timedelta
import shutil
import zipfile
import tempfile
import logging
import socket

# --- Constants & Paths ---
APP_DATA = "app_data"
ADMINS_FILE = os.path.join(APP_DATA, "admins.json")
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_DIR = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

# --- Logging ---
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log(msg):
    logging.info(msg)

# --- Utility functions ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def generate_passcode(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def get_client_ip():
    # Try to get local IP address of client, fallback to localhost
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

def zip_files(files, zip_path):
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for fpath in files:
            zf.write(fpath, os.path.basename(fpath))

# --- Session State Initialization ---
if 'admins' not in st.session_state:
    st.session_state.admins = load_json(ADMINS_FILE)

if 'teachers' not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE)

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

if 'logged_in_role' not in st.session_state:
    st.session_state.logged_in_role = None  # 'admin' or 'teacher'

if 'otp_store' not in st.session_state:
    st.session_state.otp_store = {}  # {username: otp}

if 'exam_passcodes' not in st.session_state:
    # exam_passcodes structure: {passcode: {teacher:..., lab:..., start_time:..., end_time:..., uploads_enabled: True/False}}
    st.session_state.exam_passcodes = {}

if 'submissions_index' not in st.session_state:
    # structure: {teacher: {student_id: {"ip":..., "files":[list_of_files], "submitted_at":...}}}
    st.session_state.submissions_index = {}

# --- Authentication functions ---
def register_user(user_type):
    st.subheader(f"Register New {user_type.capitalize()}")
    username = st.text_input(f"{user_type.capitalize()} Username", key=f"reg_{user_type}_username")
    password = st.text_input(f"{user_type.capitalize()} Password", type="password", key=f"reg_{user_type}_password")
    password_confirm = st.text_input(f"Confirm Password", type="password", key=f"reg_{user_type}_password_confirm")

    if user_type == "teacher":
        full_name = st.text_input("Full Name", key="reg_teacher_fullname")
        phone = st.text_input("Phone Number (for OTP)", key="reg_teacher_phone")
        lab = st.text_input("Assigned Lab Name", key="reg_teacher_lab")

    if st.button(f"Register {user_type.capitalize()}"):
        if not username or not password or not password_confirm:
            st.warning("Please fill all fields.")
            return
        if password != password_confirm:
            st.warning("Passwords do not match.")
            return

        store = st.session_state.admins if user_type == "admin" else st.session_state.teachers
        if username in store:
            st.error(f"{user_type.capitalize()} username already exists.")
            return

        hashed = hash_password(password)
        if user_type == "admin":
            store[username] = {"password_hash": hashed}
        else:
            if not full_name or not lab:
                st.warning("Please fill all required fields (Full Name, Lab).")
                return
            store[username] = {
                "password_hash": hashed,
                "full_name": full_name,
                "phone": phone,
                "lab": lab,
                "uploads_enabled": False,
                "exam_start": None,
                "exam_end": None,
                "passcodes": []
            }
        if user_type == "admin":
            save_json(ADMINS_FILE, store)
        else:
            save_json(TEACHERS_FILE, store)
        log(f"New {user_type} registered: {username}")
        st.success(f"{user_type.capitalize()} registered successfully! Please login.")
        st.experimental_rerun()

def login_user(user_type):
    st.subheader(f"{user_type.capitalize()} Login")
    username = st.text_input(f"{user_type.capitalize()} Username", key=f"login_{user_type}_username")
    password = st.text_input(f"{user_type.capitalize()} Password", type="password", key=f"login_{user_type}_password")

    if st.button(f"Login {user_type.capitalize()}"):
        store = st.session_state.admins if user_type == "admin" else st.session_state.teachers
        user = store.get(username)
        if not user:
            st.error(f"{user_type.capitalize()} not found.")
            return
        if verify_password(password, user["password_hash"]):
            st.session_state.logged_in_user = username
            st.session_state.logged_in_role = user_type
            log(f"{user_type.capitalize()} logged in: {username}")
            st.experimental_rerun()
        else:
            st.error("Invalid password.")

def logout():
    if st.session_state.logged_in_user:
        log(f"User logged out: {st.session_state.logged_in_user} ({st.session_state.logged_in_role})")
    st.session_state.logged_in_user = None
    st.session_state.logged_in_role = None
    st.experimental_rerun()

def forgot_password_flow(user_type):
    st.subheader(f"{user_type.capitalize()} Password Reset")

    username = st.text_input(f"{user_type.capitalize()} Username", key=f"fp_{user_type}_username")
    if username and username not in (st.session_state.admins if user_type == "admin" else st.session_state.teachers):
        st.error(f"{user_type.capitalize()} username not found.")

    if st.button("Send OTP"):
        otp = generate_otp()
        st.session_state.otp_store[username] = otp
        # In production, send OTP via email/SMS here instead of showing
        st.info(f"OTP for {username} (for demo only): {otp}")
        log(f"OTP generated for {user_type} '{username}'")

    otp_input = st.text_input("Enter OTP", key=f"fp_{user_type}_otp")
    new_password = st.text_input("New Password", type="password", key=f"fp_{user_type}_newpass")
    confirm_password = st.text_input("Confirm New Password", type="password", key=f"fp_{user_type}_confnewpass")

    if st.button("Reset Password"):
        if not username or not otp_input or not new_password or not confirm_password:
            st.warning("Fill all fields.")
            return
        if otp_input != st.session_state.otp_store.get(username, ""):
            st.error("Invalid OTP.")
            return
        if new_password != confirm_password:
            st.error("Passwords do not match.")
            return

        store = st.session_state.admins if user_type == "admin" else st.session_state.teachers
        if username not in store:
            st.error(f"{user_type.capitalize()} not found.")
            return

        store[username]["password_hash"] = hash_password(new_password)
        if user_type == "admin":
            save_json(ADMINS_FILE, store)
        else:
            save_json(TEACHERS_FILE, store)
        log(f"{user_type.capitalize()} '{username}' reset password.")
        st.success("Password reset successful. Please login.")
        st.session_state.otp_store.pop(username, None)
        st.experimental_rerun()

# --- Admin Panel ---
def admin_panel():
    st.header("Admin Dashboard")
    st.write(f"Logged in as Admin: **{st.session_state.logged_in_user}**")

    # Manage Admins
    st.subheader("Manage Admin Users")
    admins = st.session_state.admins
    for admin_username in admins:
        cols = st.columns([3, 1])
        cols[0].write(admin_username)
        if cols[1].button(f"Delete Admin: {admin_username}", key=f"del_admin_{admin_username}"):
            if admin_username == st.session_state.logged_in_user:
                st.error("You cannot delete yourself!")
            else:
                del st.session_state.admins[admin_username]
                save_json(ADMINS_FILE, st.session_state.admins)
                log(f"Admin '{st.session_state.logged_in_user}' deleted admin '{admin_username}'")
                st.success(f"Admin {admin_username} deleted.")
                st.experimental_rerun()

    # Manage Teachers
    st.subheader("Manage Teachers")
    teachers = st.session_state.teachers
    for username, t in teachers.items():
        cols = st.columns([3, 1])
        cols[0].write(f"{t.get('full_name','')} ({username}) - Lab: {t.get('lab','')}")
        if cols[1].button(f"Delete Teacher: {username}", key=f"del_teacher_{username}"):
            del st.session_state.teachers[username]
            save_json(TEACHERS_FILE, st.session_state.teachers)
            log(f"Admin '{st.session_state.logged_in_user}' deleted teacher '{username}'")
            st.success(f"Teacher {username} deleted.")
            st.experimental_rerun()

    st.markdown("---")
    if st.button("Logout"):
        logout()

# --- Teacher Panel ---
def teacher_panel():
    username = st.session_state.logged_in_user
    teachers = st.session_state.teachers
    teacher = teachers.get(username)

    st.header(f"Teacher Dashboard — {teacher.get('full_name','')} ({username})")
    st.write(f"Lab: **{teacher.get('lab')}**")

    # Exam time settings
    col1, col2, col3 = st.columns(3)
    with col1:
        exam_start = st.time_input("Exam Start Time", value=datetime.now().time(), key="exam_start")
    with col2:
        exam_end = st.time_input("Exam End Time", value=(datetime.now() + timedelta(hours=1)).time(), key="exam_end")
    with col3:
        if st.button("Set Exam Time"):
            start_dt = datetime.combine(datetime.today(), exam_start)
            end_dt = datetime.combine(datetime.today(), exam_end)
            if end_dt <= start_dt:
                st.error("End time must be after start time.")
            else:
                teacher["exam_start"] = start_dt.isoformat()
                teacher["exam_end"] = end_dt.isoformat()
                save_json(TEACHERS_FILE, st.session_state.teachers)
                st.success(f"Exam time set: {start_dt.strftime('%H:%M')} to {end_dt.strftime('%H:%M')}")
                log(f"Teacher '{username}' set exam time {start_dt} to {end_dt}")

    st.markdown("---")

    # Upload enable toggle
    uploads_enabled = teacher.get("uploads_enabled", False)
    if st.checkbox("Enable Uploads for Exam", value=uploads_enabled):
        teacher["uploads_enabled"] = True
    else:
        teacher["uploads_enabled"] = False
    save_json(TEACHERS_FILE, st.session_state.teachers)

    # Generate Passcode
    st.subheader("Generate Exam Passcode")
    if st.button("Generate New Passcode"):
        code = generate_passcode()
        # Save passcode with timing info
        start_time = datetime.fromisoformat(teacher.get("exam_start")) if teacher.get("exam_start") else datetime.now()
        end_time = datetime.fromisoformat(teacher.get("exam_end")) if teacher.get("exam_end") else (datetime.now() + timedelta(hours=1))
        st.session_state.exam_passcodes[code] = {
            "teacher": username,
            "lab": teacher["lab"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "uploads_enabled": True
        }
        teacher.setdefault("passcodes", []).append(code)
        save_json(TEACHERS_FILE, st.session_state.teachers)
        st.success(f"Generated passcode: {code} (valid from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')})")
        log(f"Teacher '{username}' generated passcode '{code}'")

    # List existing passcodes
    st.subheader("Existing Exam Passcodes")
    passcodes = teacher.get("passcodes", [])
    for pc in passcodes:
        info = st.session_state.exam_passcodes.get(pc)
        if not info:
            continue
        st.write(f"Passcode: {pc} | Valid from {datetime.fromisoformat(info['start_time']).strftime('%H:%M')} to {datetime.fromisoformat(info['end_time']).strftime('%H:%M')}")

    st.markdown("---")
    # View submissions
    st.subheader("Student Submissions")

    lab_folder = os.path.join(SUBMISSIONS_DIR, teacher["lab"])
    ensure_dir(lab_folder)

    # Build submissions list
    submissions = []
    if teacher["lab"] in st.session_state.submissions_index:
        for student_id, data in st.session_state.submissions_index[teacher["lab"]].items():
            for fpath in data.get("files", []):
                filename = os.path.basename(fpath)
                submissions.append((student_id, filename, fpath))

    if not submissions:
        st.info("No submissions yet.")
    else:
        selected_files = st.multiselect("Select submissions", [f"{sid} - {fname}" for sid, fname, _ in submissions])
        selected_paths = [fpath for sid, fname, fpath in submissions if f"{sid} - {fname}" in selected_files]

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Download Selected"):
                for path in selected_paths:
                    with open(path, "rb") as file:
                        st.download_button(f"Download {os.path.basename(path)}", file.read(), file_name=os.path.basename(path))
        with col2:
            if st.button("Download Selected as ZIP"):
                if selected_paths:
                    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                    zip_files(selected_paths, tmp_zip.name)
                    with open(tmp_zip.name, "rb") as fzip:
                        st.download_button("Download ZIP", fzip.read(), file_name=f"{teacher['lab']}_submissions.zip")
                    os.unlink(tmp_zip.name)
                else:
                    st.warning("Select files first.")
        with col3:
            dest_folder = st.text_input("Copy to folder (absolute path)")
            if st.button("Copy Selected to Folder"):
                if not selected_paths:
                    st.warning("Select files first.")
                elif not dest_folder:
                    st.warning("Enter destination folder path.")
                else:
                    try:
                        ensure_dir(dest_folder)
                        for fpath in selected_paths:
                            shutil.copy(fpath, dest_folder)
                        st.success(f"Copied {len(selected_paths)} files to {dest_folder}")
                        log(f"Teacher '{username}' copied {len(selected_paths)} files to {dest_folder}")
                    except Exception as e:
                        st.error(f"Copy failed: {e}")

    st.markdown("---")
    if st.button("Logout"):
        logout()

# --- Student Portal ---
def student_portal():
    st.header("Student Exam Submission")

    teachers = st.session_state.teachers
    if not teachers:
        st.warning("No teachers registered. Contact your instructor.")
        return

    teacher_usernames = list(teachers.keys())
    selected_teacher = st.selectbox("Select your Teacher", ["-- Select --"] + teacher_usernames)
    if selected_teacher == "-- Select --":
        st.stop()

    passcode = st.text_input("Enter Exam Passcode", max_chars=8)
    student_id = st.text_input("Enter your Student ID (Unique)")
    uploaded_file = st.file_uploader("Upload your Answer File (PDF or DOCX)", type=["pdf", "docx"])

    # Show exam timer countdown if passcode valid
    now = datetime.now()
    passcode_info = st.session_state.exam_passcodes.get(passcode)

    if passcode_info:
        start_time = datetime.fromisoformat(passcode_info["start_time"])
        end_time = datetime.fromisoformat(passcode_info["end_time"])
        if start_time <= now <= end_time:
            remaining = end_time - now
            st.info(f"Exam Time Remaining: {str(remaining).split('.')[0]}")
        else:
            st.error("Exam is not active for this passcode.")
            return
    else:
        if passcode:
            st.error("Invalid passcode.")
        return

    # Submit button
    if st.button("Submit Paper"):
        if selected_teacher not in teachers:
            st.error("Invalid teacher selection.")
            return
        if not passcode or not student_id or not uploaded_file:
            st.error("Please fill all fields and upload your file.")
            return

        teacher_obj = teachers[selected_teacher]
        lab = teacher_obj.get("lab")

        # Check if uploads enabled
        if not teacher_obj.get("uploads_enabled", False):
            st.error("Uploads are not enabled by the teacher at this time.")
            return

        # Check passcode matches teacher and exam is active
        if passcode not in teacher_obj.get("passcodes", []):
            st.error("Passcode does not belong to the selected teacher.")
            return

        # Duplicate submission check by student ID or IP
        student_lab_subs = st.session_state.submissions_index.setdefault(lab, {})
        existing = student_lab_subs.get(student_id)
        ip = get_client_ip()

        if existing:
            st.error("You have already submitted your exam.")
            return

        # Check if IP already submitted
        for sid, data in student_lab_subs.items():
            if data.get("ip") == ip:
                st.error("This device/IP has already submitted an exam.")
                return

        # Save file
        lab_folder = os.path.join(SUBMISSIONS_DIR, lab)
        ensure_dir(lab_folder)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{student_id}_{timestamp}_{uploaded_file.name}"
        save_path = os.path.join(lab_folder, safe_filename)

        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Save submission index
        student_lab_subs[student_id] = {
            "ip": ip,
            "files": [save_path],
            "submitted_at": datetime.now().isoformat()
        }

        st.session_state.submissions_index[lab] = student_lab_subs
        log(f"Student {student_id} submitted exam for lab '{lab}' (Teacher: {selected_teacher}) from IP {ip}")
        st.success("Submission successful!")
        st.experimental_rerun()

# --- Main App Navigation ---
def main():
    st.title("Professional Lab Exam Portal")

    if st.session_state.logged_in_user:
        role = st.session_state.logged_in_role
        if role == "admin":
            admin_panel()
        elif role == "teacher":
            teacher_panel()
    else:
        menu = ["Student Portal", "Admin Login", "Teacher Login", "Admin Register", "Teacher Register", "Forgot Password"]
        choice = st.sidebar.selectbox("Menu", menu)

        if choice == "Student Portal":
            student_portal()

        elif choice == "Admin Login":
            login_user("admin")

        elif choice == "Teacher Login":
            login_user("teacher")

        elif choice == "Admin Register":
            register_user("admin")

        elif choice == "Teacher Register":
            register_user("teacher")

        elif choice == "Forgot Password":
            user_type = st.selectbox("Select user type", ["admin", "teacher"])
            forgot_password_flow(user_type)

if __name__ == "__main__":
    main()
