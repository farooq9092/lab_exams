# app.py
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

# ---------- CONFIG ----------
APP_DATA = "app_data"                 # all persistent files/folders inside project
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

# initialize logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------- UTILITIES ----------
def load_teachers():
    if os.path.exists(TEACHERS_FILE):
        with open(TEACHERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_teachers(data):
    with open(TEACHERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_server_ip():
    # best-effort local IP detection
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def gen_passcode(n=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def gen_otp(n=6):
    return ''.join(random.choices(string.digits, k=n))

def walk_lab_files(lab_folder):
    """
    return list of dicts: {display, abs_path, student_id, filename, serial}
    files enumerated in stable order
    """
    items = []
    if not os.path.exists(lab_folder):
        return items
    serial = 1
    for student in sorted(os.listdir(lab_folder)):
        sdir = os.path.join(lab_folder, student)
        if not os.path.isdir(sdir): continue
        for fname in sorted(os.listdir(sdir)):
            fpath = os.path.join(sdir, fname)
            if os.path.isfile(fpath):
                display = f"{serial}. {student} → {fname}"
                items.append({"display": display, "path": fpath, "student": student, "filename": fname, "serial": serial})
                serial += 1
    return items

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def record_log(msg):
    logging.info(msg)

# ---------- SESSION STATE DEFAULTS ----------
if "teachers" not in st.session_state:
    st.session_state.teachers = load_teachers()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "active_passcodes" not in st.session_state:
    st.session_state.active_passcodes = {}  # {code: {teacher, lab, start, end}}
if "submissions_index" not in st.session_state:
    st.session_state.submissions_index = {}  # record submitted (filename -> {id, ip, time})

# ---------- APP UI ----------
st.set_page_config(page_title="Exam Portal", layout="centered")
st.title("📘 Professional Lab Exam Portal")

st.sidebar.title("Navigation")
mode = st.sidebar.radio("", ["Student Portal", "Teacher Login", "Teacher Signup", "Forgot Password", "Admin"])

# ---------------- STUDENT PORTAL ----------------
if mode == "Student Portal":
    st.header("🎓 Student Upload")
    # choose teacher -> lab shown through passcode mapping
    teacher_list = list(st.session_state.teachers.keys())
    if not teacher_list:
        st.info("No teachers registered yet. Ask your instructor.")
    else:
        teacher_choice = st.selectbox("Select Teacher", ["-- select --"] + teacher_list)
        passcode = st.text_input("Enter Exam Passcode (from teacher)", value="", help="Enter code given by your teacher for this exam")
        student_id = st.text_input("Enter Your Student ID (use unique ID)")
        uploaded = st.file_uploader("Choose PDF/DOCX file", type=["pdf", "docx"])
        server_ip = get_server_ip()

        if st.button("Submit Paper"):
            if not (teacher_choice and teacher_choice != "-- select --"):
                st.warning("Select your teacher.")
            elif not passcode or passcode not in st.session_state.active_passcodes:
                st.error("Invalid or expired passcode.")
            else:
                pass_info = st.session_state.active_passcodes.get(passcode)
                # verify assigned teacher and lab and deadline
                if pass_info["teacher"] != teacher_choice:
                    st.error("Passcode does not belong to selected teacher.")
                else:
                    # time check
                    now = datetime.now()
                    end = datetime.fromisoformat(pass_info["end"])
                    if now > end:
                        st.error("Submission time expired for this passcode.")
                    else:
                        # file checks
                        if not student_id or not uploaded:
                            st.warning("Enter student ID and upload file.")
                        else:
                            lab = pass_info["lab"]
                            lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
                            ensure_dir(lab_folder)
                            student_folder = os.path.join(lab_folder, student_id)
                            ensure_dir(student_folder)

                            # Duplicate check: same ID OR same IP should be blocked
                            duplicate = False
                            for rec in st.session_state.submissions_index.values():
                                if rec["id"] == student_id or rec["ip"] == server_ip:
                                    duplicate = True
                                    break
                            if duplicate:
                                st.error("Submission blocked: same Student ID or same IP already submitted.")
                            else:
                                # compute serial: count total files in lab
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

                                # record
                                st.session_state.submissions_index[safe_name] = {"id": student_id, "ip": server_ip, "time": datetime.now().isoformat(), "lab": lab, "teacher": teacher_choice}
                                record_log(f"UPLOAD: {safe_name} by {student_id} ip={server_ip} lab={lab} teacher={teacher_choice}")
                                st.success(f"Submitted ✅ as {safe_name}")

# ---------------- TEACHER SIGNUP ----------------
elif mode == "Teacher Signup":
    st.header("👩‍🏫 Teacher Signup")
    name = st.text_input("Full name")
    username = st.text_input("Username")
    phone = st.text_input("Phone (for OTP SMS; optional)")
    password = st.text_input("Password", type="password")
    lab_for = st.text_input("Assigned Lab name (e.g., Lab1)")

    if st.button("Register"):
        if not username or not password or not lab_for:
            st.warning("Fill username, password and lab.")
        elif username in st.session_state.teachers:
            st.warning("Username exists.")
        else:
            st.session_state.teachers[username] = {"name": name or username, "password": password, "phone": phone, "lab": lab_for, "uploads_allowed": True}
            save_teachers(st.session_state.teachers)
            record_log(f"TEACHER_REGISTER: {username} lab={lab_for}")
            st.success("Registered. Please login using Teacher Login.")

# ---------------- FORGOT PASSWORD ----------------
elif mode == "Forgot Password":
    st.header("🔑 Forgot Password (OTP)")
    uname = st.text_input("Enter your username")
    if st.button("Send OTP"):
        teachers = st.session_state.teachers
        if uname not in teachers:
            st.error("Username not found.")
        else:
            otp = gen_otp()
            teachers[uname]["otp"] = otp
            save_teachers(teachers)
            # ---- PRODUCTION: integrate Twilio here to send SMS to teachers[uname]['phone'] ----
            st.info(f"OTP simulated (for real SMS integrate Twilio): {otp}")
            record_log(f"OTP_SENT simulated for {uname}")

    code = st.text_input("Enter OTP")
    new_pw = st.text_input("New password", type="password")
    if st.button("Reset Password"):
        teachers = st.session_state.teachers
        if uname in teachers and teachers[uname].get("otp") == code:
            teachers[uname]["password"] = new_pw
            teachers[uname].pop("otp", None)
            save_teachers(teachers)
            st.success("Password reset. Login now.")
            record_log(f"PW_RESET for {uname}")
        else:
            st.error("Invalid OTP or user.")

# ---------------- TEACHER LOGIN & DASHBOARD ----------------
elif mode == "Teacher Login":
    if st.session_state.logged_in:
        # direct dashboard (no extra welcome)
        teacher = st.session_state.user
        st.header(f"🔒 {teacher} — Dashboard")
        teachers = st.session_state.teachers
        info = teachers[teacher]
        lab = info.get("lab")
        st.subheader(f"Lab: {lab}")

        # controls row
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Generate Passcode"):
                code = gen_passcode(6)
                # set active passcode valid for configured minutes (default 60)
                duration = st.number_input("Passcode duration (minutes)", min_value=5, max_value=720, value=60, key="pc_duration")
                start = datetime.now()
                end = start + timedelta(minutes=duration)
                st.session_state.active_passcodes[code] = {"teacher": teacher, "lab": lab, "start": start.isoformat(), "end": end.isoformat()}
                st.success(f"Passcode: {code} (valid till {end.strftime('%Y-%m-%d %H:%M:%S')})")
                record_log(f"PASSGEN by {teacher} lab={lab} code={code} dur={duration}")

        with c2:
            if st.button("Start Exam (enable uploads)"):
                teachers[teacher]["uploads_allowed"] = True
                save_teachers(teachers)
                st.success("Uploads enabled.")
        with c3:
            if st.button("Disable Uploads"):
                teachers[teacher]["uploads_allowed"] = False
                save_teachers(teachers)
                st.warning("Uploads disabled.")

        st.markdown("---")
        st.subheader("Submissions (select & manage)")

        lab_folder = os.path.join(SUBMISSIONS_ROOT, lab)
        ensure_dir(lab_folder)
        files = walk_lab_files(lab_folder)  # list of dicts

        if not files:
            st.info("No submissions yet.")
        else:
            # select all toggle
            sel_all = st.checkbox("Select All")
            display_list = [f["display"] for f in files]
            if sel_all:
                selected = st.multiselect("Selected files", display_list, default=display_list)
            else:
                selected = st.multiselect("Selected files", display_list)

            # map selected to paths
            selected_paths = [f["path"] for f in files if f["display"] in selected]

            # direct download listing + individual downloads
            st.markdown("**Files:**")
            for f in files:
                name = f["filename"]
                st.write(f"{f['display']}")
                with open(f["path"], "rb") as fh:
                    st.download_button(label="Download", data=fh, file_name=name, key=f"dl_{f['serial']}")

            # copy to folder (works if running locally on teacher machine)
            st.markdown("---")
            st.subheader("Copy selected → local folder (runs on server, for local use put server on teacher machine)")

            dest = st.text_input("Destination folder path (absolute) on this machine", value="")
            if st.button("Copy Selected"):
                if not selected_paths:
                    st.warning("Select files first")
                elif not dest:
                    st.warning("Enter destination path")
                else:
                    try:
                        ensure_dir(dest)
                        count = 0
                        for p in selected_paths:
                            shutil.copy(p, dest)
                            count += 1
                        st.success(f"Copied {count} files to {dest}")
                        record_log(f"COPY_SELECTED by {teacher} -> {dest} count={count}")
                    except Exception as e:
                        st.error(f"Copy failed: {e}")

            if st.button("Copy All to Destination"):
                if not dest:
                    st.warning("Enter destination path")
                else:
                    try:
                        ensure_dir(dest)
                        cnt = 0
                        for f in files:
                            shutil.copy(f["path"], dest)
                            cnt += 1
                        st.success(f"Copied all {cnt} files to {dest}")
                        record_log(f"COPY_ALL by {teacher} -> {dest} count={cnt}")
                    except Exception as e:
                        st.error(f"Copy all failed: {e}")

            # download selected as ZIP
            if st.button("Download Selected as ZIP"):
                if not selected_paths:
                    st.warning("Select files first")
                else:
                    # create temp zip
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                    with zipfile.ZipFile(tmp.name, "w") as zf:
                        for p in selected_paths:
                            zf.write(p, arcname=os.path.basename(p))
                    with open(tmp.name, "rb") as zf:
                        st.download_button("Download ZIP", zf.read(), file_name=f"submissions_{lab}.zip")
                    os.unlink(tmp.name)

        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.experimental_rerun()

    else:
        # login form (direct login -> redirect)
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
                st.error("Invalid credentials")

# ---------------- ADMIN (simple) ----------------
elif mode == "Admin":
    st.header("🔧 Admin (local)")
    st.write("Server IP:", get_server_ip())
    st.write("Teachers registered:", list(st.session_state.teachers.keys()))
    if st.button("Save teachers to disk"):
        save_teachers(st.session_state.teachers)
        st.success("Saved")
    if st.button("Reload teachers from disk"):
        st.session_state.teachers = load_teachers()
        st.success("Reloaded")

# ---------- persist teachers on action exit ----------
save_teachers(st.session_state.teachers)
