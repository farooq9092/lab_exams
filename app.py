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

# ----------- CONFIGURATION -----------
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

# ----------- LOGGING SETUP -----------
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ----------- UTILITY FUNCTIONS -----------

def load_teachers():
    if os.path.exists(TEACHERS_FILE):
        with open(TEACHERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_teachers(data):
    with open(TEACHERS_FILE, "w") as f:
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

def record_log(message):
    logging.info(message)

def walk_lab_files(lab_folder):
    """Return list of submissions with metadata"""
    items = []
    if not os.path.exists(lab_folder):
        return items
    serial = 1
    for student in sorted(os.listdir(lab_folder)):
        sdir = os.path.join(lab_folder, student)
        if not os.path.isdir(sdir):
            continue
        for fname in sorted(os.listdir(sdir)):
            fpath = os.path.join(sdir, fname)
            if os.path.isfile(fpath):
                display = f"{serial}. {student} → {fname}"
                items.append({"display": display, "path": fpath, "student": student, "filename": fname, "serial": serial})
                serial += 1
    return items

# ----------- SESSION STATE INITIALIZATION -----------

if "teachers" not in st.session_state:
    st.session_state.teachers = load_teachers()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None

if "active_passcodes" not in st.session_state:
    st.session_state.active_passcodes = {}  # passcode: {teacher, lab, start, end}

if "submissions_index" not in st.session_state:
    st.session_state.submissions_index = {}  # filename: {id, ip, time, lab, teacher}

if "passcode_verified" not in st.session_state:
    st.session_state.passcode_verified = False

if "verified_passcode" not in st.session_state:
    st.session_state.verified_passcode = ""

# ----------- STREAMLIT APP UI -----------

st.set_page_config(page_title="Professional Lab Exam Portal", layout="centered")
st.title("📘 Professional Lab Exam Portal")

st.sidebar.title("Navigation")
mode = st.sidebar.radio("", ["Student Portal", "Teacher Signup", "Teacher Login", "Forgot Password", "Admin"])

# ---------------- STUDENT PORTAL ----------------
if mode == "Student Portal":
    st.header("🎓 Student Exam Paper Upload")

    # Step 1: Enter Passcode + Verify
    passcode_input = st.text_input("Enter Exam Passcode (from your teacher)")
    verify_btn = st.button("Verify Passcode")

    if verify_btn:
        if passcode_input in st.session_state.active_passcodes:
            pass_info = st.session_state.active_passcodes[passcode_input]
            # Check expiry
            now = datetime.now()
            end_time = datetime.fromisoformat(pass_info["end"])
            if now > end_time:
                st.error("Passcode expired. Contact your teacher.")
                st.session_state.passcode_verified = False
                st.session_state.verified_passcode = ""
            else:
                st.session_state.passcode_verified = True
                st.session_state.verified_passcode = passcode_input
                st.success("Passcode verified! Please proceed with upload.")
        else:
            st.error("Invalid passcode.")

    if st.session_state.passcode_verified:
        pass_info = st.session_state.active_passcodes.get(st.session_state.verified_passcode)
        teacher = pass_info["teacher"]
        lab = pass_info["lab"]
        st.write(f"Teacher: **{teacher}** | Lab: **{lab}**")

        student_id = st.text_input("Enter Your Student ID (Unique)")
        uploaded_file = st.file_uploader("Upload your exam paper (PDF or DOCX)", type=["pdf", "docx"])
        server_ip = get_server_ip()

        if st.button("Submit Paper"):
            if not student_id or not uploaded_file:
                st.warning("Please enter your student ID and upload the file.")
            else:
                # Ensure directories
                lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
                ensure_dir(lab_folder)
                student_folder = os.path.join(lab_folder, student_id)
                ensure_dir(student_folder)

                # Duplicate check by student_id or IP
                duplicate = False
                for rec in st.session_state.submissions_index.values():
                    if rec["id"] == student_id or rec["ip"] == server_ip:
                        duplicate = True
                        break
                if duplicate:
                    st.error("Submission blocked: same Student ID or IP already submitted.")
                else:
                    # Count current submissions for serial number
                    total_files = 0
                    for s in os.listdir(lab_folder):
                        sf = os.path.join(lab_folder, s)
                        if os.path.isdir(sf):
                            total_files += len([x for x in os.listdir(sf) if os.path.isfile(os.path.join(sf, x))])
                    serial = total_files + 1
                    safe_name = f"{serial}_{student_id}_{server_ip}_{uploaded_file.name}"
                    dest_path = os.path.join(student_folder, safe_name)

                    # Save file
                    with open(dest_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # Record submission
                    st.session_state.submissions_index[safe_name] = {
                        "id": student_id,
                        "ip": server_ip,
                        "time": datetime.now().isoformat(),
                        "lab": lab,
                        "teacher": teacher
                    }
                    record_log(f"UPLOAD: {safe_name} by {student_id} ip={server_ip} lab={lab} teacher={teacher}")
                    st.success(f"Paper submitted successfully as {safe_name}")

                    # Reset verification to avoid multiple submits without re-verification
                    st.session_state.passcode_verified = False
                    st.session_state.verified_passcode = ""

# ---------------- TEACHER SIGNUP ----------------
elif mode == "Teacher Signup":
    st.header("👩‍🏫 Teacher Signup")

    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone (optional, for OTP SMS)")
    password = st.text_input("Password", type="password")
    lab_for = st.text_input("Assigned Lab Name (e.g., Lab1)")

    if st.button("Register"):
        if not username or not password or not lab_for:
            st.warning("Please fill username, password and lab fields.")
        elif username in st.session_state.teachers:
            st.warning("Username already exists.")
        else:
            st.session_state.teachers[username] = {
                "name": name or username,
                "password": password,
                "phone": phone,
                "lab": lab_for,
                "uploads_allowed": True
            }
            save_teachers(st.session_state.teachers)
            record_log(f"TEACHER_REGISTER: {username} lab={lab_for}")
            st.success("Registration successful! Please login.")

# ---------------- FORGOT PASSWORD ----------------
elif mode == "Forgot Password":
    st.header("🔑 Forgot Password")

    uname = st.text_input("Enter your username")
    if st.button("Send OTP"):
        teachers = st.session_state.teachers
        if uname not in teachers:
            st.error("Username not found.")
        else:
            otp = gen_otp()
            teachers[uname]["otp"] = otp
            save_teachers(teachers)
            # Simulate SMS here
            st.info(f"OTP sent (simulated): {otp}")
            record_log(f"OTP_SENT simulated for {uname}")

    entered_otp = st.text_input("Enter OTP")
    new_password = st.text_input("New Password", type="password")
    if st.button("Reset Password"):
        teachers = st.session_state.teachers
        if uname in teachers and teachers[uname].get("otp") == entered_otp:
            teachers[uname]["password"] = new_password
            teachers[uname].pop("otp", None)
            save_teachers(teachers)
            st.success("Password reset successful. You can login now.")
            record_log(f"PASSWORD_RESET for {uname}")
        else:
            st.error("Invalid OTP or username.")

# ---------------- TEACHER LOGIN & DASHBOARD ----------------
elif mode == "Teacher Login":
    if st.session_state.logged_in:
        teacher = st.session_state.user
        st.header(f"🔒 {teacher} — Dashboard")

        teachers = st.session_state.teachers
        info = teachers.get(teacher, {})
        lab = info.get("lab", "N/A")
        uploads_allowed = info.get("uploads_allowed", True)

        st.subheader(f"Lab: {lab}")

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("Generate Passcode"):
                code = gen_passcode()
                duration = st.number_input("Passcode duration (minutes)", min_value=5, max_value=720, value=60, key="passcode_duration")
                start = datetime.now()
                end = start + timedelta(minutes=duration)
                st.session_state.active_passcodes[code] = {
                    "teacher": teacher,
                    "lab": lab,
                    "start": start.isoformat(),
                    "end": end.isoformat()
                }
                st.success(f"Passcode generated: {code} (valid till {end.strftime('%Y-%m-%d %H:%M:%S')})")
                record_log(f"PASSCODE_GENERATED by {teacher} lab={lab} code={code} duration={duration}min")

        with c2:
            if st.button("Enable Uploads"):
                teachers[teacher]["uploads_allowed"] = True
                save_teachers(teachers)
                st.success("Uploads enabled.")

        with c3:
            if st.button("Disable Uploads"):
                teachers[teacher]["uploads_allowed"] = False
                save_teachers(teachers)
                st.warning("Uploads disabled.")

        st.markdown("---")
        st.subheader("Submissions")

        lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
        ensure_dir(lab_folder)
        submissions = walk_lab_files(lab_folder)

        if not submissions:
            st.info("No submissions found.")
        else:
            select_all = st.checkbox("Select All")
            display_names = [s["display"] for s in submissions]

            if select_all:
                selected_files = st.multiselect("Selected files", display_names, default=display_names)
            else:
                selected_files = st.multiselect("Selected files", display_names)

            selected_paths = [s["path"] for s in submissions if s["display"] in selected_files]

            st.markdown("**Files:**")
            for s in submissions:
                st.write(s["display"])
                with open(s["path"], "rb") as file:
                    st.download_button(label="Download", data=file, file_name=s["filename"], key=f"dl_{s['serial']}")

            st.markdown("---")
            st.subheader("Copy Selected Files to Local Folder")

            dest_folder = st.text_input("Destination folder path (absolute) on this machine")

            if st.button("Copy Selected"):
                if not selected_paths:
                    st.warning("Please select files first.")
                elif not dest_folder:
                    st.warning("Please enter destination path.")
                else:
                    try:
                        ensure_dir(dest_folder)
                        count = 0
                        for p in selected_paths:
                            shutil.copy(p, dest_folder)
                            count += 1
                        st.success(f"Copied {count} files to {dest_folder}")
                        record_log(f"COPY_SELECTED by {teacher} to {dest_folder} count={count}")
                    except Exception as e:
                        st.error(f"Error copying files: {e}")

            if st.button("Copy All to Destination"):
                if not dest_folder:
                    st.warning("Please enter destination path.")
                else:
                    try:
                        ensure_dir(dest_folder)
                        count = 0
                        for s in submissions:
                            shutil.copy(s["path"], dest_folder)
                            count += 1
                        st.success(f"Copied all {count} files to {dest_folder}")
                        record_log(f"COPY_ALL by {teacher} to {dest_folder} count={count}")
                    except Exception as e:
                        st.error(f"Error copying all files: {e}")

            if st.button("Download Selected as ZIP"):
                if not selected_paths:
                    st.warning("Please select files first.")
                else:
                    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                    with zipfile.ZipFile(tmp_zip.name, "w") as zf:
                        for p in selected_paths:
                            zf.write(p, arcname=os.path.basename(p))
                    with open(tmp_zip.name, "rb") as fzip:
                        st.download_button("Download ZIP", fzip.read(), file_name=f"submissions_{lab}.zip")
                    os.unlink(tmp_zip.name)

        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.experimental_rerun()

    else:
        st.header("👩‍🏫 Teacher Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            teachers = st.session_state.teachers
            if username in teachers and teachers[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")

# ---------------- ADMIN ----------------
elif mode == "Admin":
    st.header("🔧 Admin Panel")

    st.write("Server IP:", get_server_ip())
    st.write("Registered Teachers:", list(st.session_state.teachers.keys()))

    if st.button("Save Teachers Data"):
        save_teachers(st.session_state.teachers)
        st.success("Teachers saved.")

    if st.button("Reload Teachers Data"):
        st.session_state.teachers = load_teachers()
        st.success("Teachers reloaded.")

# ----------- SAVE TEACHERS DATA -----------

save_teachers(st.session_state.teachers)
