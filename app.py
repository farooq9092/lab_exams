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
ADMIN_FILE = os.path.join(APP_DATA, "admin.json")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------------- UTILS ----------------
def hash_password(password: str) -> str:
    """Hash a password for secure storage."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against the stored hash."""
    return hash_password(password) == hashed

def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
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

if 'admin' not in st.session_state:
    st.session_state.admin = load_json(ADMIN_FILE, {})

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

if 'logged_in_role' not in st.session_state:
    st.session_state.logged_in_role = None  # 'admin' or 'teacher'

if 'active_passcodes' not in st.session_state:
    st.session_state.active_passcodes = {}

if 'submissions_index' not in st.session_state:
    st.session_state.submissions_index = {}

if 'otp_store' not in st.session_state:
    st.session_state.otp_store = {}

# ---------------- APP CONFIG ----------------
st.set_page_config(page_title="Professional Lab Exam Portal", layout="centered")
st.title("📘 Professional Lab Exam Portal")

# ---------------- AUTH HELPERS ----------------
def admin_is_registered():
    return bool(st.session_state.admin.get("username")) and bool(st.session_state.admin.get("password_hash"))

def admin_logged_in():
    return st.session_state.logged_in_role == "admin"

def teacher_logged_in():
    return st.session_state.logged_in_role == "teacher"

def logout():
    st.session_state.logged_in_user = None
    st.session_state.logged_in_role = None
    st.experimental_rerun()

# ---------------- ADMIN PANEL ----------------
def admin_panel():
    st.header("🔧 Admin Dashboard")

    st.write(f"Logged in as: **{st.session_state.logged_in_user}** (Admin)")

    # List Teachers with delete option
    st.subheader("Registered Teachers")
    teachers = st.session_state.teachers

    if teachers:
        for username, info in list(teachers.items()):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.write(f"**{info.get('name', '')}** — Username: {username} — Lab: {info.get('lab','')}")
            with cols[1]:
                if st.button(f"Delete {username}", key=f"del_{username}"):
                    del st.session_state.teachers[username]
                    save_json(TEACHERS_FILE, st.session_state.teachers)
                    record_log(f"ADMIN deleted teacher: {username}")
                    st.success(f"Deleted teacher: {username}")
                    st.experimental_rerun()
            with cols[2]:
                # For future: Add edit or reset password buttons here
                pass
    else:
        st.info("No teachers registered yet.")

    st.markdown("---")

    # Admin Logout
    if st.button("Logout Admin"):
        logout()

# ---------------- ADMIN LOGIN ----------------
def admin_login_page():
    st.header("🔒 Admin Login")
    username = st.text_input("Admin Username")
    password = st.text_input("Admin Password", type="password")

    if st.button("Login"):
        admin_data = st.session_state.admin
        if not admin_data:
            st.error("No admin registered yet. Please register first.")
            return

        if username == admin_data.get("username") and verify_password(password, admin_data.get("password_hash", "")):
            st.session_state.logged_in_user = username
            st.session_state.logged_in_role = "admin"
            record_log(f"Admin logged in: {username}")
            st.experimental_rerun()
        else:
            st.error("Invalid admin credentials.")

    if not admin_is_registered():
        st.info("No admin registered yet. Please register below.")

    with st.expander("Register Admin (Only if no admin registered)"):
        if admin_is_registered():
            st.write("Admin already registered. Contact current admin for access.")
        else:
            reg_username = st.text_input("Choose Admin Username", key="reg_admin_user")
            reg_password = st.text_input("Choose Admin Password", type="password", key="reg_admin_pass")
            reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_admin_pass_confirm")
            if st.button("Register Admin"):
                if not reg_username or not reg_password:
                    st.warning("Please fill all fields.")
                elif reg_password != reg_password_confirm:
                    st.warning("Passwords do not match.")
                else:
                    st.session_state.admin = {
                        "username": reg_username,
                        "password_hash": hash_password(reg_password)
                    }
                    save_json(ADMIN_FILE, st.session_state.admin)
                    record_log(f"Admin registered: {reg_username}")
                    st.success("Admin registered! Please login now.")
                    st.experimental_rerun()

    # Forgot Password hidden by default, shown on click
    with st.expander("Forgot Admin Password?"):
        admin_forgot_password_flow()

# ---------------- ADMIN FORGOT PASSWORD FLOW ----------------
def admin_forgot_password_flow():
    st.write("Reset admin password using OTP.")
    if "admin_otp" not in st.session_state:
        st.session_state.admin_otp = ""

    if st.button("Send OTP to admin email (simulated)"):
        otp = gen_otp()
        st.session_state.admin_otp = otp
        record_log("Admin OTP sent (simulated)")
        st.info(f"Simulated Admin OTP: {otp} (Replace with real email integration)")

    entered_otp = st.text_input("Enter OTP", key="admin_otp_input")
    new_pass = st.text_input("New Password", type="password", key="admin_new_pass")

    if st.button("Reset Admin Password"):
        if entered_otp == st.session_state.admin_otp and entered_otp != "":
            st.session_state.admin["password_hash"] = hash_password(new_pass)
            save_json(ADMIN_FILE, st.session_state.admin)
            st.session_state.admin_otp = ""
            record_log("Admin password reset successful")
            st.success("Admin password reset successfully. Please login again.")
            st.experimental_rerun()
        else:
            st.error("Invalid OTP.")

# ---------------- TEACHER SIGNUP ----------------
def teacher_signup():
    st.header("👩‍🏫 Teacher Signup (Admin Only)")

    if not admin_logged_in():
        st.warning("Teacher signup is only available after admin login.")
        return

    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone (optional, for OTP)")
    password = st.text_input("Password", type="password")
    password_confirm = st.text_input("Confirm Password", type="password")
    lab = st.text_input("Assigned Lab Name (e.g. Lab1)")

    if st.button("Register Teacher"):
        if not username or not password or not lab:
            st.warning("Fill all mandatory fields (username, password, lab).")
        elif password != password_confirm:
            st.warning("Passwords do not match.")
        elif username in st.session_state.teachers:
            st.warning("Username already exists.")
        else:
            st.session_state.teachers[username] = {
                "name": name or username,
                "password_hash": hash_password(password),
                "phone": phone,
                "lab": lab,
                "uploads_allowed": True
            }
            save_json(TEACHERS_FILE, st.session_state.teachers)
            record_log(f"Teacher registered: {username}")
            st.success(f"Teacher {username} registered successfully. Please login.")
            st.experimental_rerun()

# ---------------- TEACHER LOGIN & DASHBOARD ----------------
def teacher_login_page():
    if teacher_logged_in():
        teacher = st.session_state.logged_in_user
        st.header(f"👩‍🏫 Teacher Dashboard — {teacher}")

        teacher_info = st.session_state.teachers.get(teacher)
        if not teacher_info:
            st.error("Teacher data not found. Please logout and login again.")
            return

        lab = teacher_info.get("lab", "Unknown Lab")
        st.subheader(f"Lab: {lab}")

        # Controls: generate passcode, enable/disable uploads
        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("Generate Exam Passcode"):
                code = gen_passcode()
                duration = st.number_input("Passcode validity (minutes)", min_value=5, max_value=720, value=60, key="passcode_duration")
                start = datetime.now()
                end = start + timedelta(minutes=duration)
                st.session_state.active_passcodes[code] = {
                    "teacher": teacher,
                    "lab": lab,
                    "start": start.isoformat(),
                    "end": end.isoformat()
                }
                st.success(f"Passcode: {code} (valid till {end.strftime('%Y-%m-%d %H:%M:%S')})")
                record_log(f"Passcode generated by {teacher} for lab {lab}: {code}")

        with c2:
            if st.button("Enable Uploads"):
                teacher_info["uploads_allowed"] = True
                save_json(TEACHERS_FILE, st.session_state.teachers)
                st.success("Uploads enabled for this exam.")

        with c3:
            if st.button("Disable Uploads"):
                teacher_info["uploads_allowed"] = False
                save_json(TEACHERS_FILE, st.session_state.teachers)
                st.warning("Uploads disabled.")

        st.markdown("---")

        # Submissions view
        st.subheader("Submissions")

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

            st.markdown("**Files:**")
            for f in files:
                name = f["filename"]
                st.write(f"{f['display']}")
                with open(f["path"], "rb") as fh:
                    st.download_button(label="Download", data=fh, file_name=name, key=f"dl_{f['serial']}")

            st.markdown("---")
            st.subheader("Copy Selected Files to Local Folder (Server Machine)")

            dest = st.text_input("Destination folder path (absolute)", value="")
            if st.button("Copy Selected"):
                if not selected_paths:
                    st.warning("Select files first.")
                elif not dest:
                    st.warning("Enter destination folder path.")
                else:
                    try:
                        ensure_dir(dest)
                        count = 0
                        for p in selected_paths:
                            shutil.copy(p, dest)
                            count += 1
                        st.success(f"Copied {count} files to {dest}")
                        record_log(f"Copied {count} files from {teacher} to {dest}")
                    except Exception as e:
                        st.error(f"Copy failed: {e}")

            if st.button("Copy All to Destination"):
                if not dest:
                    st.warning("Enter destination folder path.")
                else:
                    try:
                        ensure_dir(dest)
                        count = 0
                        for f in files:
                            shutil.copy(f["path"], dest)
                            count += 1
                        st.success(f"Copied all {count} files to {dest}")
                        record_log(f"Copied all files from {teacher} to {dest}")
                    except Exception as e:
                        st.error(f"Copy all failed: {e}")

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

        if st.button("Logout"):
            logout()

    else:
        st.header("👩‍🏫 Teacher Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            teachers = st.session_state.teachers
            if username in teachers and verify_password(password, teachers[username]["password_hash"]):
                st.session_state.logged_in_user = username
                st.session_state.logged_in_role = "teacher"
                record_log(f"Teacher logged in: {username}")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")

# ---------------- STUDENT PORTAL ----------------
def student_portal():
    st.header("🎓 Student Upload")

    teachers = st.session_state.teachers
    if not teachers:
        st.info("No teachers registered yet. Please contact your instructor.")
        return

    teacher_list = list(teachers.keys())
    teacher_choice = st.selectbox("Select Teacher", ["-- Select --"] + teacher_list)
    passcode = st.text_input("Enter Exam Passcode (from teacher)", help="Enter code given by your teacher for this exam")
    student_id = st.text_input("Enter Your Student ID (unique identifier)")
    uploaded = st.file_uploader("Upload your answer file (PDF or DOCX)", type=["pdf", "docx"])

    server_ip = get_server_ip()

    if st.button("Submit Paper"):
        if not teacher_choice or teacher_choice == "-- Select --":
            st.warning("Please select your teacher.")
        elif not passcode or passcode not in st.session_state.active_passcodes:
            st.error("Invalid or expired passcode.")
        else:
            pass_info = st.session_state.active_passcodes.get(passcode)
            if pass_info["teacher"] != teacher_choice:
                st.error("Passcode does not match the selected teacher.")
            else:
                now = datetime.now()
                end = datetime.fromisoformat(pass_info["end"])
                if now > end:
                    st.error("Submission time expired for this passcode.")
                else:
                    if not student_id or not uploaded:
                        st.warning("Please enter your student ID and upload your file.")
                    else:
                        lab = pass_info["lab"]
                        lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
                        ensure_dir(lab_folder)
                        student_folder = os.path.join(lab_folder, student_id)
                        ensure_dir(student_folder)

                        # Prevent duplicate submissions by same student ID or IP
                        duplicate = False
                        for rec in st.session_state.submissions_index.values():
                            if rec["id"] == student_id or rec["ip"] == server_ip:
                                duplicate = True
                                break

                        if duplicate:
                            st.error("Submission blocked: Student ID or IP already submitted.")
                        else:
                            # Save submission
                            total_files = 0
                            for s in os.listdir(lab_folder):
                                sf = os.path.join(lab_folder, s)
                                if os.path.isdir(sf):
                                    total_files += len([x for x in os.listdir(sf) if os.path.isfile(os.path.join(sf, x))])
                            serial = total_files + 1

                            safe_name = f"{serial}_{student_id}_{server_ip}_{uploaded.name}"
                            dest = os.path.join(student_folder, safe_name)

                            with open(dest, "wb") as f:
                                f.write(uploaded.getbuffer())

                            st.session_state.submissions_index[safe_name] = {
                                "id": student_id,
                                "ip": server_ip,
                                "time": datetime.now().isoformat(),
                                "lab": lab,
                                "teacher": teacher_choice
                            }
                            record_log(f"UPLOAD: {safe_name} by {student_id} IP={server_ip} Lab={lab} Teacher={teacher_choice}")
                            st.success("Paper uploaded successfully! You cannot upload again.")

                            # Optionally disable further uploads for this teacher in session
                            # st.session_state.teachers[teacher_choice]["uploads_allowed"] = False
                            save_json(TEACHERS_FILE, st.session_state.teachers)

# ---------------- MAIN APP ----------------
def main():
    # Sidebar Navigation
    st.sidebar.title("Navigation")
    options = []

    if admin_logged_in():
        options = ["Student Portal", "Teacher Signup", "Teacher Login", "Admin Dashboard", "Logout"]
    elif teacher_logged_in():
        options = ["Student Portal", "Teacher Login", "Logout"]
    else:
        options = ["Student Portal", "Teacher Login", "Admin Login"]

    choice = st.sidebar.radio("Go to", options)

    if choice == "Admin Login":
        admin_login_page()
    elif choice == "Admin Dashboard":
        admin_panel()
    elif choice == "Teacher Signup":
        teacher_signup()
    elif choice == "Teacher Login":
        teacher_login_page()
    elif choice == "Student Portal":
        student_portal()
    elif choice == "Logout":
        logout()
    else:
        st.info("Select an option from the sidebar.")

if __name__ == "__main__":
    main()
