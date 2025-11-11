import streamlit as st
import os
import json
import random
import string
import shutil
from datetime import datetime, timedelta

# ---------------- CONFIG -----------------
UPLOAD_DIR = "submissions"
TEACHER_FILE = "teachers.json"
PASSCODE_FILE = "passcodes.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------- UTILITIES -----------------
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ---------------- TEACHER SIGNUP / LOGIN -----------------
teachers = load_json(TEACHER_FILE)
passcodes = load_json(PASSCODE_FILE)

st.set_page_config(page_title="SZABIST Exam Portal", page_icon="🎓", layout="centered")

st.title("🎓 SZABIST Exam Submission Portal")

menu = st.sidebar.radio("Select User Type", ["Student", "Teacher"])

# ---------------- STUDENT SECTION -----------------
if menu == "Student":
    st.header("🧑‍🎓 Student Upload Section")
    student_id = st.text_input("Enter your Student ID:")
    passcode = st.text_input("Enter Exam Passcode:")

    uploaded_file = st.file_uploader("Upload Exam File (PDF or DOCX):", type=["pdf", "docx"])

    if st.button("📤 Submit Paper"):
        if not (student_id and passcode and uploaded_file):
            st.warning("⚠️ Please fill all fields and select a file.")
        else:
            # Validate passcode
            passcodes = load_json(PASSCODE_FILE)
            if passcode not in passcodes:
                st.error("❌ Invalid or expired passcode.")
            else:
                info = passcodes[passcode]
                end_time = datetime.strptime(info["end_time"], "%Y-%m-%d %H:%M:%S")
                if datetime.now() > end_time:
                    st.error("⏰ Submission time is over!")
                else:
                    lab_name = info["lab"]
                    teacher = info["teacher"]

                    folder_path = os.path.join(UPLOAD_DIR, teacher, lab_name)
                    os.makedirs(folder_path, exist_ok=True)

                    filename = f"{student_id}_{uploaded_file.name}"
                    with open(os.path.join(folder_path, filename), "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    st.success(f"✅ File uploaded successfully at {datetime.now().strftime('%H:%M:%S')}")

# ---------------- TEACHER SECTION -----------------
elif menu == "Teacher":
    st.header("👩‍🏫 Teacher Panel")

    sub_menu = st.radio("Select Action", ["Login", "Sign Up", "Forgot Password"])

    if sub_menu == "Sign Up":
        new_user = st.text_input("Enter Username:")
        new_pass = st.text_input("Enter Password:", type="password")

        if st.button("Register"):
            teachers = load_json(TEACHER_FILE)
            if new_user in teachers:
                st.warning("⚠️ Username already exists.")
            else:
                teachers[new_user] = {"password": new_pass}
                save_json(TEACHER_FILE, teachers)
                st.success("✅ Account created successfully. You can now log in.")

    elif sub_menu == "Forgot Password":
        user = st.text_input("Enter your Username:")
        new_pass = st.text_input("Enter New Password:", type="password")

        if st.button("Reset Password"):
            teachers = load_json(TEACHER_FILE)
            if user in teachers:
                teachers[user]["password"] = new_pass
                save_json(TEACHER_FILE, teachers)
                st.success("✅ Password reset successfully.")
            else:
                st.error("❌ Username not found.")

    elif sub_menu == "Login":
        username = st.text_input("Username:")
        password = st.text_input("Password:", type="password")

        if st.button("🔓 Login"):
            teachers = load_json(TEACHER_FILE)
            if username in teachers and teachers[username]["password"] == password:
                st.success(f"Welcome, {username}!")
                st.subheader("📘 Exam Management")

                lab = st.selectbox("Select Lab:", ["Lab 1", "Lab 2", "Lab 3", "Lab 4", "Lab 5", "Lab 6"])

                duration = st.number_input("Set Exam Duration (minutes):", min_value=10, max_value=300, step=5)
                if st.button("Generate Passcode"):
                    code = generate_passcode()
                    start_time = datetime.now()
                    end_time = start_time + timedelta(minutes=duration)

                    passcodes = load_json(PASSCODE_FILE)
                    passcodes[code] = {
                        "teacher": username,
                        "lab": lab,
                        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_json(PASSCODE_FILE, passcodes)
                    st.info(f"✅ Generated Passcode for {lab}: `{code}` (Valid till {end_time.strftime('%H:%M:%S')})")

                st.divider()
                st.subheader(f"📂 Submissions for {lab}")

                lab_folder = os.path.join(UPLOAD_DIR, username, lab)
                if os.path.exists(lab_folder):
                    files = os.listdir(lab_folder)
                    if files:
                        for i, f in enumerate(files, 1):
                            st.write(f"{i}. {f}")
                    else:
                        st.info("No submissions yet.")
                else:
                    st.info("No submissions yet.")

                st.divider()

                # Time extension
                extend_passcode = st.text_input("Enter Passcode to Extend Time:")
                extra_minutes = st.number_input("Extra Minutes:", min_value=5, max_value=120, step=5)

                if st.button("Extend Time"):
                    passcodes = load_json(PASSCODE_FILE)
                    if extend_passcode in passcodes:
                        old_end = datetime.strptime(passcodes[extend_passcode]["end_time"], "%Y-%m-%d %H:%M:%S")
                        new_end = old_end + timedelta(minutes=extra_minutes)
                        passcodes[extend_passcode]["end_time"] = new_end.strftime("%Y-%m-%d %H:%M:%S")
                        save_json(PASSCODE_FILE, passcodes)
                        st.success(f"✅ Extended time till {new_end.strftime('%H:%M:%S')}")
                    else:
                        st.error("❌ Invalid passcode.")

                # Copy all files
                if st.button("📁 Copy All Files to Backup Folder"):
                    backup_folder = f"backup_{username}_{lab}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copytree(lab_folder, backup_folder)
                    st.success(f"✅ All files copied to: `{backup_folder}`")
            else:
                st.error("❌ Invalid username or password.")
