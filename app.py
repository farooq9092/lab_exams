import streamlit as st
import os
import json
import hashlib
import random
import string
import shutil
import tempfile
import zipfile
import socket
from datetime import datetime, timedelta
import logging

# -------------- CONFIG -----------------
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# -------------- UTILS ------------------

def record_log(msg):
    logging.info(msg)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def load_json(file, default=None):
    if default is None:
        default = {}
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def gen_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def gen_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def get_client_ip():
    # Attempt to get client IP (best effort)
    try:
        return st.request.remote_addr
    except:
        # fallback
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def get_teacher_exams(teacher_data):
    """Return dict of exams for teacher."""
    # teacher_data["exams"] = {passcode: {lab, duration, active, start_time}}
    return teacher_data.get("exams", {})

def walk_submissions(lab_folder):
    """Return list of dict with info of each submission file."""
    submissions = []
    if not os.path.exists(lab_folder):
        return submissions
    for student_id in sorted(os.listdir(lab_folder)):
        student_folder = os.path.join(lab_folder, student_id)
        if os.path.isdir(student_folder):
            for fname in sorted(os.listdir(student_folder)):
                fpath = os.path.join(student_folder, fname)
                if os.path.isfile(fpath):
                    submissions.append({
                        "student_id": student_id,
                        "filename": fname,
                        "filepath": fpath
                    })
    return submissions

# -------------- SESSION INIT ------------------
if "teachers" not in st.session_state:
    st.session_state.teachers = load_json(TEACHERS_FILE, {})

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "logged_in_role" not in st.session_state:
    st.session_state.logged_in_role = None  # 'teacher' only in this app

if "otp_store" not in st.session_state:
    st.session_state.otp_store = {}

# -------------- OTP FUNCTIONS ------------------
def send_otp(contact_info):
    otp = gen_otp()
    st.session_state.otp_store[contact_info] = otp
    record_log(f"OTP sent to {contact_info} (simulated): {otp}")
    st.success(f"OTP sent to {contact_info}. (In real app, it will be sent securely)")
    return otp

def verify_otp(contact_info, otp_input):
    real_otp = st.session_state.otp_store.get(contact_info)
    if real_otp == otp_input:
        del st.session_state.otp_store[contact_info]
        return True
    return False

# -------------- AUTH ------------------
def register_teacher():
    st.header("Register as Teacher")
    username = st.text_input("Username", key="reg_username")
    name = st.text_input("Full Name", key="reg_name")
    phone = st.text_input("Phone (for OTP)", key="reg_phone")
    password = st.text_input("Password", type="password", key="reg_pass")
    password_confirm = st.text_input("Confirm Password", type="password", key="reg_pass_conf")

    if st.button("Register"):
        if not username or not name or not phone or not password:
            st.warning("All fields are required.")
            return
        if password != password_confirm:
            st.warning("Passwords do not match.")
            return
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
            return
        hashed = hash_password(password)
        st.session_state.teachers[username] = {
            "name": name,
            "phone": phone,
            "password_hash": hashed,
            "exams": {}  # passcode: exam data
        }
        save_json(TEACHERS_FILE, st.session_state.teachers)
        record_log(f"Teacher registered: {username}")
        st.success("Registration successful! Please login.")

def teacher_login():
    st.header("Teacher Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        teacher = st.session_state.teachers.get(username)
        if not teacher:
            st.error("User not found.")
            return
        if not verify_password(password, teacher["password_hash"]):
            st.error("Incorrect password.")
            return
        st.session_state.logged_in_user = username
        st.session_state.logged_in_role = "teacher"
        record_log(f"Teacher logged in: {username}")
        st.success(f"Welcome {teacher['name']}!")
        st.experimental_rerun()

def forgot_password_teacher():
    st.header("Forgot Password - Teacher")
    username = st.text_input("Enter your username", key="fp_username")
    if not username:
        return
    teacher = st.session_state.teachers.get(username)
    if not teacher:
        st.error("User not found.")
        return
    contact = teacher.get("phone")
    if not contact:
        st.error("No phone registered, cannot send OTP.")
        return

    if st.button("Send OTP"):
        send_otp(contact)

    otp_input = st.text_input("Enter OTP", key="fp_otp")
    new_pass = st.text_input("New Password", type="password", key="fp_new_pass")
    new_pass_confirm = st.text_input("Confirm New Password", type="password", key="fp_new_pass_conf")

    if st.button("Reset Password"):
        if not otp_input or not new_pass or not new_pass_confirm:
            st.warning("All fields required.")
            return
        if new_pass != new_pass_confirm:
            st.warning("Passwords do not match.")
            return
        if verify_otp(contact, otp_input):
            teacher["password_hash"] = hash_password(new_pass)
            save_json(TEACHERS_FILE, st.session_state.teachers)
            record_log(f"Teacher password reset: {username}")
            st.success("Password reset successful! Please login.")
        else:
            st.error("Invalid OTP.")

def logout():
    record_log(f"User logged out: {st.session_state.logged_in_user}")
    st.session_state.logged_in_user = None
    st.session_state.logged_in_role = None
    st.experimental_rerun()

# -------------- TEACHER DASHBOARD ------------------
def teacher_dashboard():
    username = st.session_state.logged_in_user
    teacher = st.session_state.teachers.get(username)
    st.header(f"Teacher Dashboard - {teacher['name']} ({username})")

    exams = get_teacher_exams(teacher)

    st.subheader("Create New Exam")
    with st.form("create_exam_form"):
        lab_name = st.text_input("Lab Name", key="lab_name")
        passcode_input = st.text_input("Passcode (leave empty to auto-generate)", max_chars=10, key="passcode_input")
        duration_mins = st.number_input("Duration (minutes)", min_value=1, max_value=180, value=60, step=1, key="duration_mins")
        submitted = st.form_submit_button("Create Exam")

        if submitted:
            # Validate passcode
            passcode = passcode_input.strip().upper() if passcode_input.strip() else gen_passcode()
            if passcode in exams:
                st.warning("Passcode already exists, choose another or leave empty to auto-generate.")
            elif not lab_name.strip():
                st.warning("Lab name is required.")
            else:
                exams[passcode] = {
                    "lab": lab_name.strip(),
                    "duration": int(duration_mins),
                    "active": False,
                    "start_time": None
                }
                teacher["exams"] = exams
                save_json(TEACHERS_FILE, st.session_state.teachers)
                record_log(f"Teacher {username} created exam {passcode} for lab {lab_name}")
                st.success(f"Exam created with passcode: {passcode}")

    st.markdown("---")
    st.subheader("Manage Exams")

    if not exams:
        st.info("No exams created yet.")
        return

    to_delete = None
    for pcode, edata in exams.items():
        col1, col2, col3, col4, col5 = st.columns([3,2,2,2,1])
        with col1:
            st.markdown(f"**Lab:** {edata['lab']}  \n**Passcode:** `{pcode}`")
            active_str = "Active" if edata['active'] else "Inactive"
            st.markdown(f"**Duration:** {edata['duration']} mins  \n**Status:** {active_str}")
            if edata['active'] and edata['start_time']:
                start_dt = datetime.fromisoformat(edata['start_time'])
                now = datetime.now()
                elapsed = now - start_dt
                rem = timedelta(minutes=edata['duration']) - elapsed
                if rem.total_seconds() < 0:
                    rem = timedelta(seconds=0)
                st.markdown(f"**Time Remaining:** {str(rem).split('.')[0]}")

        with col2:
            if not edata['active']:
                if st.button(f"Start Exam\n({pcode})", key=f"start_{pcode}"):
                    edata['active'] = True
                    edata['start_time'] = datetime.now().isoformat()
                    save_json(TEACHERS_FILE, st.session_state.teachers)
                    record_log(f"Teacher {username} started exam {pcode}")
                    st.experimental_rerun()
            else:
                st.write("Exam Running")

        with col3:
            if edata['active']:
                if st.button(f"Stop Exam\n({pcode})", key=f"stop_{pcode}"):
                    edata['active'] = False
                    edata['start_time'] = None
                    save_json(TEACHERS_FILE, st.session_state.teachers)
                    record_log(f"Teacher {username} stopped exam {pcode}")
                    st.experimental_rerun()
            else:
                st.write("Exam Stopped")

        with col4:
            if st.button(f"View Submissions\n({pcode})", key=f"viewsubs_{pcode}"):
                show_submissions(teacher, pcode, edata)

        with col5:
            if st.button(f"Delete Exam\n({pcode})", key=f"del_{pcode}"):
                to_delete = pcode

    if to_delete:
        # Delete exam data and submissions
        lab = exams[to_delete]["lab"]
        del exams[to_delete]
        teacher["exams"] = exams
        save_json(TEACHERS_FILE, st.session_state.teachers)
        # Delete submissions folder if exists
        lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
        if os.path.exists(lab_folder):
            try:
                shutil.rmtree(lab_folder)
            except Exception as e:
                st.error(f"Error deleting submissions folder: {e}")
        record_log(f"Teacher {username} deleted exam {to_delete} and submissions for lab {lab}")
        st.success(f"Exam {to_delete} and submissions deleted.")
        st.experimental_rerun()

    if st.button("Logout"):
        logout()

def show_submissions(teacher, passcode, exam_data):
    st.subheader(f"Submissions for Exam {passcode} (Lab: {exam_data['lab']})")
    lab_folder = os.path.join(SUBMISSIONS_ROOT, exam_data['lab'])
    ensure_dir(lab_folder)
    submissions = walk_submissions(lab_folder)

    if not submissions:
        st.info("No submissions yet.")
        return

    select_all = st.checkbox("Select All", key=f"selectall_{passcode}")

    file_display_names = [f"{s['student_id']} - {s['filename']}" for s in submissions]
    default_selected = file_display_names if select_all else []
    selected_files = st.multiselect("Select submissions", file_display_names, default=default_selected, key=f"multiselect_{passcode}")

    selected_paths = [submissions[file_display_names.index(f)]["filepath"] for f in selected_files]

    for f in submissions:
        st.markdown(f"**{f['student_id']}** submitted: {f['filename']}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Download Selected as ZIP", key=f"zip_{passcode}"):
            if not selected_paths:
                st.warning("Select files to download.")
            else:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                with zipfile.ZipFile(tmp.name, 'w') as zipf:
                    for p in selected_paths:
                        zipf.write(p, os.path.basename(p))
                with open(tmp.name, "rb") as f:
                    st.download_button("Download ZIP", f.read(), file_name=f"submissions_{passcode}.zip")
                os.unlink(tmp.name)

    with col2:
        dest = st.text_input("Copy Selected to Folder (absolute path)", key=f"copydest_{passcode}")
        if st.button("Copy Selected Files", key=f"copy_{passcode}"):
            if not selected_paths:
                st.warning("Select files to copy.")
            elif not dest:
                st.warning("Enter destination folder path.")
            else:
                try:
                    ensure_dir(dest)
                    for p in selected_paths:
                        shutil.copy2(p, dest)
                    st.success(f"Copied {len(selected_paths)} files to {dest}")
                    record_log(f"Teacher {teacher} copied {len(selected_paths)} files for exam {passcode} to {dest}")
                except Exception as e:
                    st.error(f"Error copying files: {e}")

# -------------- STUDENT PORTAL -----------------
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
    uploaded_file = st.file_uploader("Upload your answer file (PDF/DOCX)", type=["pdf", "docx"], key="student_file")

    if not passcode or not student_id:
        st.info("Please enter passcode and student ID to proceed.")
        st.stop()

    teacher_data = teachers.get(teacher_choice)
    if not teacher_data:
        st.error("Teacher data not found.")
        st.stop()

    exams = get_teacher_exams(teacher_data)
    exam = exams.get(passcode)

    if not exam:
        st.error("Invalid passcode.")
        st.stop()

    # Check exam active & timing
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

    # Prevent duplicate submissions by student ID or IP
    lab_folder = os.path.join(SUBMISSIONS_ROOT, exam["lab"])
    ensure_dir(lab_folder)
    submissions = walk_submissions(lab_folder)
    client_ip = get_client_ip()

    for sub in submissions:
        if sub["student_id"] == student_id:
            st.error("You have already submitted your paper.")
            st.stop()

    # Note: IP based blocking could be added here if you store IP per submission

    if st.button("Submit Paper"):
        if not uploaded_file:
            st.warning("Please upload your answer file.")
            st.stop()

        student_folder = os.path.join(lab_folder, student_id)
        ensure_dir(student_folder)
        file_path = os.path.join(student_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        record_log(f"Student {student_id} submitted file {uploaded_file.name} for lab {exam['lab']} under teacher {teacher_choice}")
        st.success("Submission successful! Good luck on your exam.")

# -------------- MAIN -------------------
def main():
    st.title("📚 Professional Lab Exam Portal")
    menu = ["Teacher Login", "Register Teacher", "Forgot Password", "Student Submission"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if st.session_state.logged_in_role == "teacher":
        teacher_dashboard()
    else:
        if choice == "Teacher Login":
            teacher_login()
        elif choice == "Register Teacher":
            register_teacher()
        elif choice == "Forgot Password":
            forgot_password_teacher()
        elif choice == "Student Submission":
            student_portal()

if __name__ == "__main__":
    main()
