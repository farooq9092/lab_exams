import streamlit as st
import os
import shutil
from datetime import datetime

# ------------------- CONFIG -------------------
UPLOAD_FOLDER = "submissions"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load teacher credentials from Streamlit Secrets
TEACHER_USERNAME = st.secrets.get("TEACHER_USERNAME", "admin")
TEACHER_PASSWORD = st.secrets.get("TEACHER_PASSWORD", "admin")

# ------------------- APP START -------------------
st.set_page_config(page_title="SZABIST Exam Portal", page_icon="🎓", layout="centered")

st.title("🎓 SZABIST Exam Submission Portal")

menu = st.sidebar.radio("Select User Type", ["Student", "Teacher"])

# ------------------- STUDENT SECTION -------------------
if menu == "Student":
    st.header("🧑‍🎓 Student Upload Section")

    student_id = st.text_input("Enter your Student ID or Exam Passcode:")
    uploaded_file = st.file_uploader(
        "Upload your Exam File (PDF, DOCX, or ZIP):",
        type=["pdf", "docx", "zip"]
    )

    if st.button("📤 Submit Paper"):
        if student_id and uploaded_file:
            student_folder = os.path.join(UPLOAD_FOLDER, student_id)
            os.makedirs(student_folder, exist_ok=True)

            file_path = os.path.join(student_folder, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.success(f"✅ Paper uploaded successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.warning("⚠️ Please enter your ID and select a file before submitting.")

# ------------------- TEACHER SECTION -------------------
elif menu == "Teacher":
    st.header("👩‍🏫 Teacher Control Panel")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("🔓 Login"):
        if username == TEACHER_USERNAME and password == TEACHER_PASSWORD:
            st.success("✅ Login successful.")
            st.subheader("📂 Student Submissions")

            if not os.listdir(UPLOAD_FOLDER):
                st.info("No submissions yet.")
            else:
                for student in os.listdir(UPLOAD_FOLDER):
                    student_folder = os.path.join(UPLOAD_FOLDER, student)
                    files = os.listdir(student_folder)
                    if files:
                        st.write(f"**{student}** → {', '.join(files)}")
                    else:
                        st.write(f"**{student}** → (Empty folder)")

            # Copy all submissions to a backup folder
            if st.button("📁 Copy All Files to Backup Folder"):
                backup_folder = "backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copytree(UPLOAD_FOLDER, backup_folder)
                st.success(f"✅ All files copied to: `{backup_folder}`")

        else:
            st.error("❌ Invalid username or password.")
