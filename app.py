import streamlit as st
import os
import shutil
from datetime import datetime, timedelta
import random
import string

# --- Configuration ---
UPLOAD_FOLDER = "submissions"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Initialize Session State ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "teacher" not in st.session_state:
    st.session_state.teacher = None
if "passcode" not in st.session_state:
    st.session_state.passcode = None
if "upload_allowed" not in st.session_state:
    st.session_state.upload_allowed = True
if "exam_deadline" not in st.session_state:
    st.session_state.exam_deadline = None

# --- Registered Teachers ---
teachers = {
    "ali": "1234",
    "ahmad": "abcd"
}

# --- Helper Functions ---
def generate_passcode():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def remaining_time():
    if st.session_state.exam_deadline:
        remaining = st.session_state.exam_deadline - datetime.now()
        if remaining.total_seconds() > 0:
            return str(remaining).split(".")[0]
        else:
            return "⏰ Time Over"
    return "Not set"

# --- Main Title ---
st.title("📘 SZABIST Exam Portal")

menu = st.sidebar.radio("Select User Type", ["Student", "Teacher"])

# ---------------- STUDENT SECTION ----------------
if menu == "Student":
    st.header("🧑‍🎓 Student Upload Portal")
    student_id = st.text_input("Enter your Student ID:")
    entered_passcode = st.text_input("Enter Passcode (provided by teacher):")
    uploaded_file = st.file_uploader("Upload your exam file:", type=["pdf", "docx"])

    if st.session_state.exam_deadline:
        st.info(f"⏳ Remaining Time: {remaining_time()}")

    if st.button("Submit Paper"):
        if not st.session_state.upload_allowed:
            st.warning("🚫 Uploads are currently disabled by the teacher.")
        elif st.session_state.exam_deadline and datetime.now() > st.session_state.exam_deadline:
            st.error("⏰ Exam time is over. Submission closed.")
        elif entered_passcode != st.session_state.passcode:
            st.error("❌ Invalid passcode.")
        elif student_id and uploaded_file:
            student_folder = os.path.join(UPLOAD_FOLDER, student_id)
            os.makedirs(student_folder, exist_ok=True)
            file_path = os.path.join(student_folder, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ Paper uploaded successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.warning("⚠️ Please enter your ID and upload your file.")

# ---------------- TEACHER SECTION ----------------
elif menu == "Teacher":
    if not st.session_state.logged_in:
        st.header("👩‍🏫 Teacher Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username in teachers and teachers[username] == password:
                st.session_state.logged_in = True
                st.session_state.teacher = username
                st.success(f"✅ Welcome, {username.capitalize()}!")
            else:
                st.error("❌ Invalid username or password")

        st.caption("Forgot password? Contact admin for reset.")
        st.caption("New teacher? Contact admin to register your account.")

    else:
        st.header(f"👋 Welcome, {st.session_state.teacher.capitalize()}")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.teacher = None
            st.session_state.passcode = None
            st.session_state.exam_deadline = None
            st.experimental_rerun()

        st.subheader("📂 Exam Controls")

        lab_name = st.text_input("Enter Lab Name (e.g. Lab1, Lab2):")

        if st.button("Generate Passcode"):
            st.session_state.passcode = generate_passcode()
            st.success(f"🧾 Passcode for students: **{st.session_state.passcode}**")

        st.subheader("⏰ Exam Timing Control")
        duration = st.number_input("Set Exam Duration (in minutes):", min_value=5, max_value=180, step=5)
        if st.button("Start Exam Timer"):
            st.session_state.exam_deadline = datetime.now() + timedelta(minutes=duration)
            st.success(f"⏱️ Exam time started for {duration} minutes!")

        if st.button("Extend Time by 10 Minutes"):
            if st.session_state.exam_deadline:
                st.session_state.exam_deadline += timedelta(minutes=10)
                st.info("⏳ Time extended by 10 minutes.")
            else:
                st.warning("⚠️ Exam not started yet.")

        st.subheader("📤 Upload Permissions")
        if st.button("Allow Uploads"):
            st.session_state.upload_allowed = True
            st.success("✅ Uploads enabled for all students.")
        if st.button("Disable Uploads"):
            st.session_state.upload_allowed = False
            st.warning("🚫 Uploads disabled.")

        st.subheader("📁 View Student Submissions")
        if lab_name:
            if os.path.exists(UPLOAD_FOLDER):
                all_students = os.listdir(UPLOAD_FOLDER)
                st.write(f"**Total Files Submitted:** {len(all_students)}")
                for i, student in enumerate(all_students, start=1):
                    files = os.listdir(os.path.join(UPLOAD_FOLDER, student))
                    st.write(f"{i}. **{student}** → {', '.join(files)}")
            else:
                st.info("No submissions yet.")

        st.subheader("📦 Backup")
        if st.button("Copy All Files to Backup Folder"):
            backup_folder = "backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copytree(UPLOAD_FOLDER, backup_folder)
            st.success(f"✅ All files copied to '{backup_folder}'")
