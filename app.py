import streamlit as st
import os
import random
import string
import socket

# ----------------- Session Data -----------------
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
    st.session_state.submitted_data = {}

# ----------------- Helper Functions -----------------
def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown_IP"

# ----------------- Signup -----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
        elif not username or not password or not phone:
            st.warning("All fields are required.")
        else:
            st.session_state.teachers[username] = {"password": password, "name": name, "phone": phone}
            st.success("✅ Registered successfully! Please log in.")

# ----------------- Login -----------------
def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
        else:
            st.error("Invalid username or password")

# ----------------- Forgot Password -----------------
def forgot_password():
    st.title("🔑 Forgot Password")
    username = st.text_input("Enter your registered username")
    if st.button("Recover"):
        if username in st.session_state.teachers:
            st.info("📱 OTP sent to your registered number (simulation)")
        else:
            st.error("Username not found!")

# ----------------- Teacher Dashboard -----------------
def teacher_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state.teachers[st.session_state.logged_in_teacher]['name']}")
    if st.sidebar.button("🏠 Home"):
        st.session_state.logged_in_teacher = None
        st.session_state.page = "Home"
        return
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in_teacher = None
        return

    st.header("📚 Teacher Dashboard")

    lab_name = st.text_input("Enter Lab Name (e.g., Lab1)")
    folder_path = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher, lab_name)
    ensure_folder(folder_path)

    if st.button("Generate Passcode for Students"):
        st.session_state.passcode = generate_passcode()
        st.success(f"🎟️ Student Passcode: {st.session_state.passcode}")

    st.subheader("⏱ Exam Time Settings")
    duration = st.number_input("Exam Duration (minutes)", min_value=5, max_value=300, value=60)
    if st.button("Start Exam"):
        st.session_state.exam_durations[lab_name] = duration
        st.success(f"Exam started for {duration} minutes.")

    extra = st.number_input("Extend Time (minutes)", min_value=1, max_value=60, value=10)
    if st.button("Extend Time"):
        st.session_state.exam_durations[lab_name] = st.session_state.exam_durations.get(lab_name, duration) + extra
        st.info(f"Extended! New Duration: {st.session_state.exam_durations[lab_name]} minutes.")

    st.subheader("📄 Submitted Papers")
    try:
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        if files:
            for f in sorted(files):
                file_path = os.path.join(folder_path, f)
                st.write(f)
                with open(file_path, "rb") as fp:
                    st.download_button("⬇ Download", data=fp, file_name=f)
        else:
            st.info("No papers submitted yet.")
    except FileNotFoundError:
        st.info("No lab folder found.")

# ----------------- Student Portal -----------------
def student_portal():
    st.title("🎓 Student Portal")
    passcode = st.text_input("Enter Passcode")

    if passcode == st.session_state.passcode and st.session_state.logged_in_teacher:
        lab_name = st.text_input("Lab Name")
        student_id = st.text_input("Student ID")
        student_ip = get_ip()
        folder_path = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher, lab_name)
        ensure_folder(folder_path)

        uploaded_file = st.file_uploader("Upload File (PDF/Word)", type=["pdf", "docx", "doc"])
        if uploaded_file:
            file_path = os.path.join(folder_path, f"{student_id}_{student_ip}_{uploaded_file.name}")
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success("✅ File submitted successfully!")
    else:
        st.warning("Enter valid passcode.")

# ----------------- Navigation -----------------
if "page" not in st.session_state:
    st.session_state.page = "Home"

st.sidebar.title("🔹 Navigation")
menu = st.sidebar.radio("Go to", ["Home", "Teacher Login", "Teacher Signup", "Forgot Password", "Student Portal"])

if menu == "Home":
    st.session_state.page = "Home"
elif menu == "Teacher Login":
    st.session_state.page = "Teacher Login"
elif menu == "Teacher Signup":
    st.session_state.page = "Teacher Signup"
elif menu == "Forgot Password":
    st.session_state.page = "Forgot Password"
elif menu == "Student Portal":
    st.session_state.page = "Student Portal"

# ----------------- Page Display -----------------
if st.session_state.logged_in_teacher:
    teacher_dashboard()
else:
    if st.session_state.page == "Home":
        st.title("🏫 Lab Exam Management App")
        st.write("Use sidebar to navigate between pages.")
    elif st.session_state.page == "Teacher Login":
        login_teacher()
    elif st.session_state.page == "Teacher Signup":
        signup_teacher()
    elif st.session_state.page == "Forgot Password":
        forgot_password()
    elif st.session_state.page == "Student Portal":
        student_portal()
