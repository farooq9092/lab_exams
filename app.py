import streamlit as st
import os
import json
import time
import shutil
from datetime import datetime, timedelta
import pyperclip  # <-- for clipboard support

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = "submissions"
TEACHER_FILE = "teachers.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load teacher data
if os.path.exists(TEACHER_FILE):
    with open(TEACHER_FILE, "r") as f:
        teachers = json.load(f)
else:
    teachers = {}
    with open(TEACHER_FILE, "w") as f:
        json.dump(teachers, f)

# ---------------- APP TITLE ----------------
st.title("📘 SZABIST Exam Portal (Enhanced Teacher Control)")

menu = st.sidebar.radio("Select User Type", ["Student", "Teacher"])

# ---------------- STUDENT SECTION ----------------
if menu == "Student":
    st.header("🧑‍🎓 Student Upload Portal")

    teacher_usernames = list(teachers.keys())
    if teacher_usernames:
        selected_teacher = st.selectbox("Select Your Teacher", teacher_usernames)
        passcode = st.text_input("Enter Passcode (Provided by Teacher):")

        if selected_teacher in teachers:
            teacher_data = teachers[selected_teacher]
            allowed = teacher_data.get("uploads_allowed", True)
            deadline = teacher_data.get("exam_deadline")
            lab = teacher_data.get("lab")

            if deadline:
                deadline_time = datetime.fromisoformat(deadline)
                remaining = (deadline_time - datetime.now()).total_seconds()
                if remaining > 0:
                    st.info(f"⏳ Time remaining: {int(remaining // 60)} minutes")
                else:
                    st.error("⏰ Exam time is over.")
                    allowed = False

            if allowed:
                if passcode == teacher_data.get("passcode"):
                    student_id = st.text_input("Enter your Student ID:")
                    uploaded_file = st.file_uploader("Upload Exam File (PDF or DOCX):", type=["pdf", "docx"])

                    if st.button("Submit Paper"):
                        if student_id and uploaded_file:
                            lab_folder = os.path.join(UPLOAD_FOLDER, lab)
                            os.makedirs(lab_folder, exist_ok=True)
                            student_folder = os.path.join(lab_folder, student_id)
                            os.makedirs(student_folder, exist_ok=True)

                            serial = len(os.listdir(lab_folder)) + 1
                            file_path = os.path.join(student_folder, f"{serial}_{uploaded_file.name}")

                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())

                            st.success(f"✅ Paper uploaded (Serial #{serial}) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        else:
                            st.warning("⚠️ Please enter ID and upload file.")
                elif passcode:
                    st.error("❌ Invalid passcode.")
            else:
                st.warning("🚫 Uploads are disabled by your teacher.")
    else:
        st.info("📭 No registered teachers yet.")

# ---------------- TEACHER SECTION ----------------
elif menu == "Teacher":
    st.header("👩‍🏫 Teacher Control Panel")

    auth_choice = st.radio("Select Action", ["Login", "Sign Up", "Forgot Password"])

    # ---------- SIGNUP ----------
    if auth_choice == "Sign Up":
        new_username = st.text_input("Choose Username:")
        new_password = st.text_input("Choose Password:", type="password")
        lab_name = st.text_input("Enter Lab Name (e.g., Lab1):")

        if st.button("Register"):
            if new_username in teachers:
                st.warning("⚠️ Username already exists.")
            elif new_username and new_password and lab_name:
                teachers[new_username] = {
                    "password": new_password,
                    "lab": lab_name,
                    "uploads_allowed": True,
                    "passcode": None,
                    "exam_deadline": None
                }
                with open(TEACHER_FILE, "w") as f:
                    json.dump(teachers, f)
                st.success("✅ Registered successfully.")
            else:
                st.warning("⚠️ Please fill all fields.")

    # ---------- LOGIN ----------
    elif auth_choice == "Login":
        username = st.text_input("Username:")
        password = st.text_input("Password:", type="password")

        if st.button("Login"):
            if username in teachers and teachers[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.teacher = username
                st.success(f"✅ Welcome {username}")
                st.rer
