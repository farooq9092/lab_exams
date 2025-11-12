import streamlit as st
import os
import datetime
import random
import string
import socket
import shutil

# ----------------- Data Storage -----------------
if "teachers" not in st.session_state:
    st.session_state.teachers = {}
if "logged_in_teacher" not in st.session_state:
    st.session_state.logged_in_teacher = None
if "passcode" not in st.session_state:
    st.session_state.passcode = None
if "exam_folder" not in st.session_state:
    st.session_state.exam_folder = "Lab_Exams"
if "exam_durations" not in st.session_state:
    st.session_state.exam_durations = {}
if "submitted_data" not in st.session_state:
    st.session_state.submitted_data = {}  # filename -> {id, ip}

# ----------------- Helpers -----------------
def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def get_ip():
    try:
        # best-effort IP detection on server
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown_IP"

def generate_serial(files_list):
    return len(files_list) + 1

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def collect_lab_files(lab_folder):
    """
    Walk lab_folder and return list of tuples:
    (relative_display_name, absolute_path, student_id, filename, serial)
    """
    items = []
    serial = 1
    if not os.path.exists(lab_folder):
        return items
    for student in sorted(os.listdir(lab_folder)):
        student_folder = os.path.join(lab_folder, student)
        if not os.path.isdir(student_folder):
            continue
        for fname in sorted(os.listdir(student_folder)):
            fpath = os.path.join(student_folder, fname)
            if os.path.isfile(fpath):
                # fname format may include serial_studentid_ip_originalname
                display = f"{student} / {fname}"
                items.append((f"{serial}. {display}", fpath, student, fname, serial))
                serial += 1
    return items

# ----------------- Signup/Login/OTP -----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number (for OTP simulation)")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if not username or not password or not phone:
            st.warning("All fields are required.")
            return
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
            return
        st.session_state.teachers[username] = {"password": password, "name": name, "phone": phone,
                                               "lab": None, "uploads_allowed": True, "passcode": None,
                                               "exam_deadline": None}
        st.success("Registered successfully. Please Login.")

def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
            # go directly to dashboard
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")

def forgot_password():
    st.title("🔑 Forgot Password (OTP)")
    username = st.text_input("Registered username")
    if st.button("Send OTP"):
        if username in st.session_state.teachers:
            otp = generate_otp()
            st.session_state.teachers[username]["otp"] = otp
            # In production: send sms via Twilio. Here we simulate:
            st.info(f"OTP sent to {st.session_state.teachers[username]['phone']} (Simulated).")
            st.caption(f"Simulation only — OTP: {otp}")
            st.session_state._pwd_reset_user = username
        else:
            st.error("Username not found.")
    if "_pwd_reset_user" in st.session_state:
        otp_input = st.text_input("Enter OTP")
        new_pass = st.text_input("New password", type="password")
        if st.button("Reset Password"):
            user = st.session_state._pwd_reset_user
            if st.session_state.teachers[user].get("otp") == otp_input:
                st.session_state.teachers[user]["password"] = new_pass
                del st.session_state.teachers[user]["otp"]
                del st.session_state._pwd_reset_user
                st.success("Password reset. Please login.")
            else:
                st.error("Invalid OTP.")

# ----------------- Teacher Dashboard -----------------
def teacher_dashboard():
    teacher = st.session_state.logged_in_teacher
    st.sidebar.title(f"Welcome, {st.session_state.teachers[teacher]['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_teacher = None
        st.experimental_rerun()

    st.header("📚 Teacher Dashboard")

    # Lab assignment / set if not set
    current_lab = st.text_input("Your Lab Name (e.g., Lab1)", value=st.session_state.teachers[teacher].get("lab") or "")
    if st.button("Save Lab Name"):
        if current_lab:
            st.session_state.teachers[teacher]["lab"] = current_lab
            st.success(f"Saved lab name: {current_lab}")
    lab = st.session_state.teachers[teacher].get("lab")
    if not lab:
        st.info("Please set your Lab Name to view/manage submissions.")
        return

    lab_folder = os.path.join(st.session_state.exam_folder, lab)
    ensure_folder(lab_folder)

    # Controls
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("🔐 Generate Passcode"):
            code = generate_passcode(6)
            st.session_state.teachers[teacher]["passcode"] = code
            st.success(f"Passcode: {code} (share with students)")
    with col2:
        duration = st.number_input("Exam duration (minutes)", min_value=5, max_value=720, value=60)
        if st.button("⏰ Start Exam"):
            deadline = datetime.datetime.now() + datetime.timedelta(minutes=duration)
            st.session_state.teachers[teacher]["exam_deadline"] = deadline.isoformat()
            st.success(f"Exam started till {deadline.strftime('%Y-%m-%d %H:%M:%S')}")
    with col3:
        if st.button("➕ Extend by 10 min"):
            dl = st.session_state.teachers[teacher].get("exam_deadline")
            if dl:
                new_dl = datetime.datetime.fromisoformat(dl) + datetime.timedelta(minutes=10)
                st.session_state.teachers[teacher]["exam_deadline"] = new_dl.isoformat()
                st.success(f"Extended to {new_dl.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.warning("Start exam first.")

    # Show remaining time
    dl = st.session_state.teachers[teacher].get("exam_deadline")
    if dl:
        remaining = datetime.datetime.fromisoformat(dl) - datetime.datetime.now()
        if remaining.total_seconds() > 0:
            st.info(f"Time remaining: {str(remaining).split('.')[0]}")
        else:
            st.warning("Exam time is over.")

    st.markdown("---")
    st.subheader("🗂 Submissions")

    # Collect files correctly (walk student subfolders)
    lab_files = collect_lab_files(lab_folder)  # list of tuples (display, abs_path, student_id, fname, serial)

    if not lab_files:
        st.info("No submissions yet.")
    else:
        # Provide Select All checkbox
        select_all = st.checkbox("Select All files")
        # Build list for multiselect display
        display_names = [item[0] for item in lab_files]
        if select_all:
            selected = st.multiselect("Selected files", display_names, default=display_names)
        else:
            selected = st.multiselect("Selected files", display_names)

        # Map selected display names back to absolute paths
        selected_paths = []
        for item in lab_files:
            if item[0] in selected:
                selected_paths.append((item[0], item[1]))  # (display, path)

        # Show per-file download buttons and preview
        st.markdown("**Files (direct download):**")
        for disp, path, student_id, fname, serial in lab_files:
            cols = st.columns([6,1])
            cols[0].write(disp)
            with open(path, "rb") as f:
                data = f.read()
            cols[1].download_button(label="⬇", data=data, file_name=fname, mime="application/octet-stream")

        st.markdown("---")
        st.subheader("Copy / Export")

        # Destination path input (server-local path). On Streamlit Cloud this writes to server storage only.
        dest = st.text_input("Destination folder path (where files will be copied on the server):", value="")
        if st.button("📁 Copy Selected Files"):
            if not selected_paths:
                st.warning("Select at least one file.")
            elif not dest:
                st.warning("Enter destination path.")
            else:
                try:
                    ensure_folder(dest)
                    count = 0
                    for disp, p in selected_paths:
                        shutil.copy(p, dest)
                        count += 1
                    st.success(f"Copied {count} file(s) to {dest}")
                except Exception as e:
                    st.error(f"Copy failed: {e}")

        if st.button("📦 Copy All Files to Destination"):
            if not dest:
                st.warning("Enter destination path.")
            else:
                try:
                    ensure_folder(dest)
                    count = 0
                    for disp, p, *_ in lab_files:
                        shutil.copy(p, dest)
                        count += 1
                    st.success(f"Copied {count} file(s) to {dest}")
                except Exception as e:
                    st.error(f"Copy all failed: {e}")

# ----------------- Student Portal -----------------
def student_portal():
    st.title("🎓 Student Portal")
    teacher_list = list(st.session_state.teachers.keys())
    if not teacher_list:
        st.info("No teachers registered yet.")
        return

    teacher_choice = st.selectbox("Select Teacher", teacher_list)
    passcode = st.text_input("Enter Passcode Provided by Teacher")

    # Validate teacher and passcode
    teacher_data = st.session_state.teachers.get(teacher_choice)
    if not teacher_data:
        st.error("Invalid teacher selected.")
        return

    # check uploads allowed and deadline
    allowed = teacher_data.get("uploads_allowed", True)
    dl = teacher_data.get("exam_deadline")
    if dl:
        if datetime.datetime.fromisoformat(dl) < datetime.datetime.now():
            allowed = False

    if not allowed:
        st.warning("Uploads are closed for this teacher/lab.")
        return

    if passcode != teacher_data.get("passcode"):
        st.info("Enter correct passcode to enable upload.")
        # still show nothing else
        return

    lab_name = st.text_input("Enter Lab Name (as given by teacher)")
    student_id = st.text_input("Enter Student ID")
    uploaded_file = st.file_uploader("Upload file (pdf/docx):", type=["pdf", "docx"])

    if st.button("Submit Paper"):
        if not (lab_name and student_id and uploaded_file):
            st.warning("Fill all fields and choose file.")
            return
        # prepare folder
        lab_folder = os.path.join(st.session_state.exam_folder, lab_name)
        ensure_folder(lab_folder)
        # student folder
        student_folder = os.path.join(lab_folder, student_id)
        ensure_folder(student_folder)

        # check duplicates: same id OR same ip
        ip = get_ip()
        duplicate = False
        for record in st.session_state.submitted_data.values():
            if record["id"] == student_id or record["ip"] == ip:
                duplicate = True
                break
        if duplicate:
            st.error("Submission blocked: same ID or same IP already submitted.")
            return

        # collect existing files for serial
        existing = collect_lab_files(lab_folder)
        serial = generate_serial(existing)
        safe_name = f"{serial}_{student_id}_{ip}_{uploaded_file.name}"
        save_path = os.path.join(student_folder, safe_name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # record submission
        st.session_state.submitted_data[safe_name] = {"id": student_id, "ip": ip, "time": datetime.datetime.now().isoformat()}
        st.success(f"Uploaded as: {safe_name}")

# ----------------- App Navigation -----------------
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Go to", ["Teacher Login", "Teacher Signup", "Forgot Password", "Student Portal"])

if menu == "Teacher Signup":
    signup_teacher()
elif menu == "Teacher Login":
    if st.session_state.logged_in_teacher:
        teacher_dashboard()
    else:
        login_teacher()
elif menu == "Forgot Password":
    forgot_password()
elif menu == "Student Portal":
    student_portal()
