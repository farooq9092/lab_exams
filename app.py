import streamlit as st
import os
import random
import string
import hashlib
import socket
import zipfile
import io
import datetime

# ----------------- Initialization -----------------
if "teachers" not in st.session_state:
    st.session_state.teachers = {}  # username → {password, name, phone, passcode, exams}
if "logged_in_teacher" not in st.session_state:
    st.session_state.logged_in_teacher = None
if "exam_folder" not in st.session_state:
    st.session_state.exam_folder = "Lab_Exams"
if "submissions" not in st.session_state:
    st.session_state.submissions = {}  # teacher → {lab_name → [submissions]}
if "exam_timers" not in st.session_state:
    st.session_state.exam_timers = {}  # teacher → {lab_name → {"start": t1, "end": t2}}

os.makedirs(st.session_state.exam_folder, exist_ok=True)

# ----------------- Utility Functions -----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown_IP"

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

# ----------------- Teacher Registration & Login -----------------
def teacher_signup():
    st.title("👩‍🏫 Teacher Registration")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
        elif not username or not password or not name:
            st.warning("All fields are required.")
        else:
            st.session_state.teachers[username] = {
                "name": name,
                "phone": phone,
                "password": hash_password(password),
                "passcode": None,
                "exams": {}
            }
            st.success("✅ Teacher registered successfully! Please log in.")

def teacher_login():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        teacher = st.session_state.teachers.get(username)
        if teacher and verify_password(password, teacher["password"]):
            st.session_state.logged_in_teacher = username
            st.success(f"Welcome, {teacher['name']}!")
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        else:
            st.error("Invalid username or password.")

# ----------------- Teacher Dashboard -----------------
def teacher_dashboard():
    teacher = st.session_state.teachers[st.session_state.logged_in_teacher]
    st.sidebar.title(f"Welcome, {teacher['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_teacher = None
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()

    st.header("📚 Teacher Dashboard")

    lab_name = st.text_input("Enter Lab Name (e.g., Lab1)")
    folder_path = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher, lab_name)
    ensure_folder(folder_path)

    if st.button("Generate Passcode for Students"):
        passcode = generate_passcode()
        teacher["passcode"] = passcode
        st.success(f"🎟️ Passcode for students: {passcode}")

    # Exam timing controls
    st.subheader("🕒 Exam Duration Control")
    start_time = st.time_input("Start Time")
    end_time = st.time_input("End Time")
    if st.button("Set Exam Duration"):
        st.session_state.exam_timers.setdefault(st.session_state.logged_in_teacher, {})[lab_name] = {
            "start": start_time,
            "end": end_time
        }
        st.success(f"Exam scheduled from {start_time} to {end_time}")

    # File viewing and downloads
    st.subheader("📁 Submitted Papers")
    files = os.listdir(folder_path)
    if files:
        selected_files = st.multiselect("Select files to download or copy", files)
        for f in files:
            with open(os.path.join(folder_path, f), "rb") as fp:
                st.download_button("⬇ Download " + f, data=fp, file_name=f)
        if st.button("Download Selected as ZIP") and selected_files:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for f in selected_files:
                    zipf.write(os.path.join(folder_path, f), arcname=f)
            st.download_button(
                label="⬇ Download ZIP",
                data=zip_buffer.getvalue(),
                file_name=f"{lab_name}_submissions.zip"
            )
    else:
        st.info("No papers submitted yet.")

# ----------------- Student Portal -----------------
def student_portal():
    st.title("🎓 Student Exam Portal")

    teacher_names = list(st.session_state.teachers.keys())
    if not teacher_names:
        st.warning("No teachers available yet. Please wait.")
        return

    selected_teacher = st.selectbox("Select Your Teacher", teacher_names)
    passcode = st.text_input("Enter Passcode Provided by Teacher")

    teacher = st.session_state.teachers[selected_teacher]
    if passcode and passcode == teacher.get("passcode"):
        st.success("✅ Passcode verified! You can now submit your exam.")
        student_id = st.text_input("Enter Student ID")
        uploaded_file = st.file_uploader("Upload your answer file", type=["pdf", "docx", "zip"])
        student_ip = get_ip()
        lab_name = st.text_input("Enter Lab Name")

        upload_folder = os.path.join(st.session_state.exam_folder, selected_teacher, lab_name)
        ensure_folder(upload_folder)

        existing = [
            s for s in st.session_state.submissions.get(selected_teacher, {}).get(lab_name, [])
            if s["id"] == student_id or s["ip"] == student_ip
        ]
        if existing:
            st.error("❌ Submission blocked! Same ID or IP has already submitted.")
            return

        if uploaded_file and st.button("Submit Paper"):
            filename = f"{student_id}_{student_ip}_{uploaded_file.name}"
            save_path = os.path.join(upload_folder, filename)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.read())

            st.session_state.submissions.setdefault(selected_teacher, {}).setdefault(lab_name, []).append({
                "id": student_id, "ip": student_ip, "file": filename,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            st.success("✅ Submission successful!")
    else:
        if passcode:
            st.error("Invalid passcode.")

# ----------------- Main App -----------------
def main():
    st.sidebar.title("🔹 Navigation")
    menu = st.sidebar.radio("Go to", ["Teacher Login", "Teacher Signup", "Student Portal"])

    if st.session_state.logged_in_teacher:
        teacher_dashboard()
    else:
        if menu == "Teacher Login":
            teacher_login()
        elif menu == "Teacher Signup":
            teacher_signup()
        elif menu == "Student Portal":
            student_portal()

if __name__ == "__main__":
    main()
