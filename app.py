%%writefile app.py
import streamlit as st
import os
from datetime import datetime

# --- Configuration ---
UPLOAD_FOLDER = "submissions"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Default credentials ---
TEACHER_USERNAME = "admin"
TEACHER_PASSWORD = "admin"

# --- App start ---
st.title("📘 SZABIST Exam Portal")

menu = st.sidebar.radio("Select User Type", ["Student", "Teacher"])

# ---------------- STUDENT SECTION ----------------
if menu == "Student":
    st.header("🧑‍🎓 Student Upload Portal")
    student_id = st.text_input("Enter your Student ID or Passcode:")
    uploaded_file = st.file_uploader("Upload your exam file (PDF, DOCX, or ZIP):", type=["pdf", "docx", "zip"])

    if st.button("Submit Paper"):
        if student_id and uploaded_file:
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
    st.header("👩‍🏫 Teacher Control Panel")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == TEACHER_USERNAME and password == TEACHER_PASSWORD:
            st.success("✅ Logged in successfully!")
            st.subheader("📂 Student Submissions")

            for student in os.listdir(UPLOAD_FOLDER):
                student_folder = os.path.join(UPLOAD_FOLDER, student)
                files = os.listdir(student_folder)
                st.write(f"**{student}** → {', '.join(files)}")

            # Allow Uploads / Disable Uploads
            if st.button("Allow Uploads for All"):
                st.info("✅ Uploads Enabled for All Students.")
            if st.button("Disable Uploads"):
                st.warning("🚫 Uploads Disabled.")

            # Copy to all folder
            if st.button("📁 Copy All Files to Backup Folder"):
                import shutil
                backup_folder = "backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copytree(UPLOAD_FOLDER, backup_folder)
                st.success(f"✅ All files copied to '{backup_folder}'")
        else:
            st.error("❌ Invalid username or password")
