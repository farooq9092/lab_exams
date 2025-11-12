import streamlit as st
import os
import datetime
import random
import string

# ----------------- Data Storage -----------------
if "teachers" not in st.session_state:
    st.session_state.teachers = {}
if "logged_in_teacher" not in st.session_state:
    st.session_state.logged_in_teacher = None
if "passcode" not in st.session_state:
    st.session_state.passcode = None
if "exam_folder" not in st.session_state:
    st.session_state.exam_folder = "Lab_Exams"

# ----------------- Helper Functions -----------------
def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

# ----------------- Signup & Login -----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Enter Full Name")
    username = st.text_input("Choose Username")
    password = st.text_input("Choose Password", type="password")
    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
        elif not username or not password:
            st.warning("All fields are required.")
        else:
            st.session_state.teachers[username] = {"password": password, "name": name}
            st.success("Registration successful! Please log in now.")

def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
            st.success(f"Welcome {st.session_state.teachers[username]['name']}!")
        else:
            st.error("Invalid username or password")

def forgot_password():
    st.title("🔑 Reset Password")
    username = st.text_input("Enter your registered username")
    if st.button("Recover"):
        if username in st.session_state.teachers:
            st.info(f"Your password is: {st.session_state.teachers[username]['password']}")
        else:
            st.error("Username not found!")

# ----------------- Teacher Dashboard -----------------
def teacher_dashboard():
    st.sidebar.title(f"Welcome {st.session_state.teachers[st.session_state.logged_in_teacher]['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_teacher = None
        st.experimental_rerun()

    st.header("📚 Teacher Dashboard")

    # Select Lab Folder
    lab_name = st.text_input("Enter Lab Name (e.g., Lab1, Lab2, Lab3)")
    folder_path = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher, lab_name)
    ensure_folder(folder_path)

    # Generate Passcode
    if st.button("Generate Passcode for Students"):
        st.session_state.passcode = generate_passcode()
        st.success(f"Passcode: {st.session_state.passcode}")

    # Set Duration
    duration = st.number_input("Set Exam Duration (minutes)", min_value=10, max_value=180, value=60)

    # Extend time
    if st.button("Extend Time by 10 Minutes"):
        duration += 10
        st.info(f"New Duration: {duration} minutes")

    # View Uploaded Papers
    st.subheader("📄 Submitted Papers")
    files = os.listdir(folder_path)
    if files:
        for i, f in enumerate(files, 1):
            st.write(f"{i}. {f}")
    else:
        st.info("No papers submitted yet.")

# ----------------- Student Portal -----------------
def student_portal():
    st.title("🎓 Student Portal")
    passcode = st.text_input("Enter Passcode Given by Teacher")

    if passcode == st.session_state.passcode and st.session_state.logged_in_teacher:
        teacher_folder = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher)
        lab_name = st.text_input("Enter Lab Name Provided by Teacher")
        upload_folder = os.path.join(teacher_folder, lab_name)
        ensure_folder(upload_folder)

        uploaded_file = st.file_uploader("Upload your paper (PDF or Word)", type=["pdf", "docx", "doc"])
        if uploaded_file is not None:
            save_path = os.path.join(upload_folder, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success("✅ File submitted successfully!")
    else:
        st.warning("Please enter a valid passcode to submit.")

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
