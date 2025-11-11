import streamlit as st
import os
import json
import time
from datetime import datetime, timedelta
import shutil

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
st.title("📘 SZABIST Exam Portal (Official)")

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
                    st.error("⏰ Exam time is over. You can’t upload now.")
                    allowed = False

            if allowed:
                if passcode == teacher_data.get("passcode"):
                    student_id = st.text_input("Enter your Student ID:")
                    uploaded_file = st.file_uploader("Upload your Exam File (PDF or DOCX):", type=["pdf", "docx"])

                    if st.button("Submit Paper"):
                        if student_id and uploaded_file:
                            lab_folder = os.path.join(UPLOAD_FOLDER, lab)
                            os.makedirs(lab_folder, exist_ok=True)

                            student_folder = os.path.join(lab_folder, student_id)
                            os.makedirs(student_folder, exist_ok=True)

                            # Add serial number
                            all_files = os.listdir(lab_folder)
                            serial = len(all_files) + 1
                            file_path = os.path.join(student_folder, f"{serial}_{uploaded_file.name}")

                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())

                            st.success(f"✅ Paper uploaded successfully (Serial #{serial}) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        else:
                            st.warning("⚠️ Please fill all fields and upload your file.")
                elif passcode:
                    st.error("❌ Invalid passcode. Please check with your teacher.")
            else:
                st.warning("🚫 Uploads are currently disabled by your teacher.")
        else:
            st.warning("No teacher data found. Please check with admin.")
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
                st.success("✅ Registration successful! You can now log in.")
            else:
                st.warning("⚠️ Please fill all fields.")

    # ---------- FORGOT PASSWORD ----------
    elif auth_choice == "Forgot Password":
        username = st.text_input("Enter your registered username:")
        new_pass = st.text_input("Enter new password:", type="password")
        confirm = st.text_input("Confirm new password:", type="password")

        if st.button("Reset Password"):
            if username in teachers:
                if new_pass == confirm and new_pass:
                    teachers[username]["password"] = new_pass
                    with open(TEACHER_FILE, "w") as f:
                        json.dump(teachers, f)
                    st.success("✅ Password reset successful.")
                else:
                    st.error("❌ Passwords do not match.")
            else:
                st.error("❌ Username not found.")

    # ---------- LOGIN ----------
    elif auth_choice == "Login":
        username = st.text_input("Username:")
        password = st.text_input("Password:", type="password")

        if st.button("Login"):
            if username in teachers and teachers[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.teacher = username
                st.success(f"✅ Welcome, {username}!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")

        # After login
        if st.session_state.get("logged_in") and st.session_state.get("teacher") == username:
            teacher_data = teachers[username]
            lab = teacher_data["lab"]

            st.subheader(f"📂 Your Lab: {lab}")
            lab_folder = os.path.join(UPLOAD_FOLDER, lab)
            os.makedirs(lab_folder, exist_ok=True)

            # --- Controls ---
            st.markdown("### ⚙️ Exam Controls")

            # Generate Passcode
            if st.button("🔐 Generate Passcode"):
                passcode = str(int(time.time()))[-4:]
                teachers[username]["passcode"] = passcode
                with open(TEACHER_FILE, "w") as f:
                    json.dump(teachers, f)
                st.success(f"✅ Passcode generated: **{passcode}** (Share with students)")

            # Time Duration
            duration = st.number_input("Set Exam Duration (minutes):", min_value=5, max_value=300, value=60)
            if st.button("⏰ Start Exam Timer"):
                deadline = datetime.now() + timedelta(minutes=duration)
                teachers[username]["exam_deadline"] = deadline.isoformat()
                with open(TEACHER_FILE, "w") as f:
                    json.dump(teachers, f)
                st.success(f"✅ Exam started for {duration} minutes!")

            # Extend Time
            if st.button("➕ Extend Time by 10 minutes"):
                if teacher_data.get("exam_deadline"):
                    deadline = datetime.fromisoformat(teacher_data["exam_deadline"]) + timedelta(minutes=10)
                    teachers[username]["exam_deadline"] = deadline.isoformat()
                    with open(TEACHER_FILE, "w") as f:
                        json.dump(teachers, f)
                    st.success("✅ Time extended successfully!")

            # Allow / Disable Uploads
            if st.button("🚫 Disable Uploads"):
                teachers[username]["uploads_allowed"] = False
                with open(TEACHER_FILE, "w") as f:
                    json.dump(teachers, f)
                st.warning("Uploads disabled.")

            if st.button("✅ Re-Allow Uploads"):
                teachers[username]["uploads_allowed"] = True
                with open(TEACHER_FILE, "w") as f:
                    json.dump(teachers, f)
                st.success("Uploads enabled again.")

            # View Submissions
            st.markdown("### 🗂️ Student Submissions")

            if os.path.exists(lab_folder):
                students = os.listdir(lab_folder)
                if students:
                    for i, student in enumerate(students, start=1):
                        files = os.listdir(os.path.join(lab_folder, student))
                        st.write(f"{i}. **{student}** → {', '.join(files)}")
                else:
                    st.info("No submissions yet.")
            else:
                st.info("No lab submissions found.")

            # Copy All Files
            if st.button("📁 Copy All Files to Backup"):
                backup_folder = f"backup_{lab}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(lab_folder, backup_folder)
                st.success(f"✅ All files copied to '{backup_folder}'")

            # Logout
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.session_state.teacher = None
                st.session_state.passcode = None
                st.session_state.exam_deadline = None
                st.rerun()
