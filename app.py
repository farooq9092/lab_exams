import streamlit as st
import sqlite3
import os
import hashlib
import time
import zipfile
from datetime import datetime, timedelta

# ============================================================
# Utility functions
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def init_db():
    conn = sqlite3.connect("exam_portal.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT UNIQUE,
                    password TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER,
                    title TEXT,
                    passcode TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    uploads_enabled INTEGER DEFAULT 1
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id INTEGER,
                    student_id TEXT,
                    student_ip TEXT,
                    filename TEXT,
                    submitted_at TEXT
                )""")
    conn.commit()
    conn.close()

# ============================================================
# File and Folder Management
# ============================================================

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_uploaded_file(exam_id, student_id, uploaded_file):
    folder_path = os.path.join(UPLOAD_DIR, str(exam_id))
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{student_id}_{uploaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def zip_selected_files(files, folder_path):
    zip_path = os.path.join(folder_path, "selected_submissions.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files:
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):  # ✅ fix here to skip folders
                zipf.write(file_path, arcname=file)
    return zip_path

# ============================================================
# Authentication
# ============================================================

def teacher_register():
    st.subheader("👩‍🏫 Teacher Registration")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if password != confirm:
            st.error("Passwords do not match.")
            return
        conn = sqlite3.connect("exam_portal.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO teachers (name, email, password) VALUES (?, ?, ?)",
                      (name, email, hash_password(password)))
            conn.commit()
            st.success("Registration successful! You can now log in.")
        except sqlite3.IntegrityError:
            st.error("Email already registered.")
        conn.close()

def teacher_login():
    st.subheader("👨‍🏫 Teacher Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = sqlite3.connect("exam_portal.db")
        c = conn.cursor()
        c.execute("SELECT id, name, password FROM teachers WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        if user and verify_password(password, user[2]):
            st.session_state["teacher_id"] = user[0]
            st.session_state["teacher_name"] = user[1]
            st.success(f"Welcome, {user[1]}!")
            st.rerun()
        else:
            st.error("Invalid email or password.")

# ============================================================
# Teacher Dashboard
# ============================================================

def teacher_dashboard():
    teacher_id = st.session_state["teacher_id"]
    st.title(f"👩‍🏫 Welcome {st.session_state['teacher_name']}")
    st.subheader("Exam Management")

    conn = sqlite3.connect("exam_portal.db")
    c = conn.cursor()

    with st.expander("➕ Create New Exam"):
        title = st.text_input("Exam Title")
        passcode = st.text_input("Exam Passcode")
        start_time = st.time_input("Start Time")
        end_time = st.time_input("End Time")
        if st.button("Create Exam"):
            start = datetime.combine(datetime.today(), start_time)
            end = datetime.combine(datetime.today(), end_time)
            c.execute("INSERT INTO exams (teacher_id, title, passcode, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                      (teacher_id, title, passcode, str(start), str(end)))
            conn.commit()
            st.success("Exam created successfully!")

    c.execute("SELECT * FROM exams WHERE teacher_id=?", (teacher_id,))
    exams = c.fetchall()
    if exams:
        for exam in exams:
            st.divider()
            st.write(f"**Exam:** {exam[2]} | **Passcode:** {exam[3]}")
            st.write(f"🕒 Start: {exam[4]} | End: {exam[5]}")

            exam_id = exam[0]
            uploads_enabled = exam[6]

            toggle = st.checkbox(f"Uploads Enabled for {exam[2]}", value=bool(uploads_enabled), key=f"toggle_{exam_id}")
            c.execute("UPDATE exams SET uploads_enabled=? WHERE id=?", (int(toggle), exam_id))
            conn.commit()

            folder_path = os.path.join(UPLOAD_DIR, str(exam_id))
            if os.path.exists(folder_path):
                files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]  # ✅ fixed
                st.write(f"📂 Total submissions: {len(files)}")

                if files:
                    selected = st.multiselect("Select submissions to ZIP", files, key=f"sel_{exam_id}")
                    if st.button(f"Download ZIP for {exam[2]}", key=f"zip_{exam_id}"):
                        zip_path = zip_selected_files(selected, folder_path)
                        with open(zip_path, "rb") as z:
                            st.download_button("⬇️ Download ZIP", z, file_name="submissions.zip")
            else:
                st.info("No submissions yet.")
    conn.close()

# ============================================================
# Student Portal
# ============================================================

def student_portal():
    st.title("🎓 Student Exam Submission")

    conn = sqlite3.connect("exam_portal.db")
    c = conn.cursor()
    c.execute("SELECT id, title, passcode, start_time, end_time FROM exams")
    exams = c.fetchall()

    if not exams:
        st.warning("No active exams.")
        return

    exam_choice = st.selectbox("Select Exam", [f"{e[1]} (Passcode: {e[2]})" for e in exams])
    exam_index = [f"{e[1]} (Passcode: {e[2]})" for e in exams].index(exam_choice)
    exam = exams[exam_index]

    passcode_input = st.text_input("Enter Exam Passcode")
    student_id = st.text_input("Enter Student ID")
    uploaded_file = st.file_uploader("Upload Answer File", type=["pdf", "zip", "docx", "py", "txt"])

    if st.button("Submit"):
        if passcode_input != exam[2]:
            st.error("Invalid passcode.")
            return

        now = datetime.now()
        start = datetime.fromisoformat(exam[3])
        end = datetime.fromisoformat(exam[4])

        if not (start <= now <= end):
            st.error("Exam is not active.")
            return

        student_ip = st.session_state.get("ip", "unknown")
        c.execute("SELECT * FROM submissions WHERE exam_id=? AND (student_id=? OR student_ip=?)",
                  (exam[0], student_id, student_ip))
        existing = c.fetchone()

        if existing:
            st.error("Submission already exists for this student or device.")
            return

        if uploaded_file:
            file_path = save_uploaded_file(exam[0], student_id, uploaded_file)
            c.execute("INSERT INTO submissions (exam_id, student_id, student_ip, filename, submitted_at) VALUES (?, ?, ?, ?, ?)",
                      (exam[0], student_id, student_ip, file_path, str(now)))
            conn.commit()
            st.success("✅ Submission successful!")
        else:
            st.error("Please upload a file.")
    conn.close()

# ============================================================
# Main App
# ============================================================

def main():
    st.set_page_config(page_title="Exam Portal", layout="wide")
    st.sidebar.title("🔐 Portal Menu")
    init_db()

    if "teacher_id" not in st.session_state:
        choice = st.sidebar.radio("Login Type", ["Teacher Login", "Teacher Register", "Student"])
        if choice == "Teacher Register":
            teacher_register()
        elif choice == "Teacher Login":
            teacher_login()
        else:
            student_portal()
    else:
        if st.sidebar.button("Logout"):
            del st.session_state["teacher_id"]
            del st.session_state["teacher_name"]
            st.rerun()
        teacher_dashboard()

if __name__ == "__main__":
    main()
