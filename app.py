import streamlit as st
import sqlite3
import os
import hashlib
from datetime import datetime, time, timedelta
from io import BytesIO
import zipfile
import socket
import random
import string

# ===========================
# DATABASE INITIALIZATION
# ===========================
DB_PATH = "lab_exam.db"
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT
        )
    """)
    c.execute("""
        CREATE TABLE exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            title TEXT,
            passcode TEXT,
            start_time TEXT,
            end_time TEXT
        )
    """)
    c.execute("""
        CREATE TABLE submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id TEXT,
            ip_address TEXT,
            filename TEXT,
            file_data BLOB,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# ===========================
# UTILITY FUNCTIONS
# ===========================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def generate_passcode():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ===========================
# TEACHER MODULE
# ===========================
def teacher_register():
    st.subheader("🧑‍🏫 Teacher Registration")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if not username or not password:
            st.warning("⚠️ Please fill all fields.")
            return
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO teachers (username, email, password) VALUES (?, ?, ?)",
                      (username, email, hash_password(password)))
            conn.commit()
            st.success("✅ Registration successful! You can now login.")
        except sqlite3.IntegrityError:
            st.error("⚠️ Username already exists.")
        conn.close()

def teacher_login():
    st.subheader("🔐 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, password FROM teachers WHERE username=?", (username,))
        result = c.fetchone()
        conn.close()

        if result and verify_password(password, result[1]):
            st.session_state["teacher_id"] = result[0]
            st.session_state["teacher_username"] = username
            st.session_state["logged_in"] = True
        else:
            st.error("❌ Invalid credentials.")

def teacher_dashboard():
    st.subheader(f"🎓 Welcome, {st.session_state['teacher_username']}")
    teacher_id = st.session_state["teacher_id"]
    conn = get_db_connection()
    c = conn.cursor()

    st.markdown("### 🧾 Create New Exam")
    title = st.text_input("Exam Title")
    start_time = st.time_input("Start Time", time(9, 0))
    end_time = st.time_input("End Time", time(10, 0))

    if st.button("Create Exam"):
        now = datetime.now()
        start = datetime.combine(datetime.today(), start_time)
        end = datetime.combine(datetime.today(), end_time)
        if end <= start:
            end += timedelta(days=1)
        passcode = generate_passcode()

        c.execute("INSERT INTO exams (teacher_id, title, passcode, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                  (teacher_id, title, passcode, str(start), str(end)))
        conn.commit()
        st.success(f"✅ Exam '{title}' created successfully!")
        st.info(f"👉 Copy this Passcode manually and share with students: **{passcode}**")

    st.divider()
    st.markdown("### 📂 Your Exams")
    c.execute("SELECT id, title, passcode, start_time, end_time FROM exams WHERE teacher_id=?", (teacher_id,))
    exams = c.fetchall()

    for ex in exams:
        exam_id, title, passcode, start, end = ex
        st.markdown(f"**{title}**  \n🕒 {start} → {end}")
        if st.button(f"View Submissions ({title})", key=f"view_{exam_id}"):
            show_submissions(exam_id)

    conn.close()

def show_submissions(exam_id):
    st.markdown("### 📁 Student Submissions")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT student_id, filename, timestamp FROM submissions WHERE exam_id=?", (exam_id,))
    data = c.fetchall()

    if not data:
        st.info("No submissions yet.")
        return

    for sid, fname, ts in data:
        st.write(f"📄 {fname} | 🧑 {sid} | ⏰ {ts}")

    if st.button("Download All as ZIP"):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            c.execute("SELECT student_id, filename, file_data FROM submissions WHERE exam_id=?", (exam_id,))
            for sid, fname, fdata in c.fetchall():
                zipf.writestr(f"{sid}_{fname}", fdata)
        zip_buffer.seek(0)
        st.download_button("⬇️ Download ZIP", zip_buffer, file_name="submissions.zip")

    conn.close()

# ===========================
# STUDENT MODULE
# ===========================
def student_portal():
    st.subheader("🎓 Student Exam Portal")
    entered_pass = st.text_input("Enter Exam Passcode to Join")

    if entered_pass:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, start_time, end_time FROM exams WHERE passcode=?", (entered_pass,))
        exam = c.fetchone()

        if not exam:
            st.error("❌ Invalid passcode.")
            return

        exam_id, title, start, end = exam
        now = datetime.now()
        start = datetime.fromisoformat(start)
        end = datetime.fromisoformat(end)

        if not (start <= now <= end):
            st.warning("⏳ Exam is not active right now.")
            return

        st.success(f"✅ Joined Exam: {title}")
        student_id = st.text_input("Enter Your Student ID")
        file = st.file_uploader("Upload Answer File (.pdf or .docx)", type=["pdf", "docx"])

        if st.button("Submit Paper"):
            ip = get_ip()
            c.execute("SELECT * FROM submissions WHERE exam_id=? AND (student_id=? OR ip_address=?)",
                      (exam_id, student_id, ip))
            if c.fetchone():
                st.error("⚠️ You have already submitted.")
            elif file:
                file_data = file.read()
                c.execute("INSERT INTO submissions (exam_id, student_id, ip_address, filename, file_data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                          (exam_id, student_id, ip, file.name, file_data, str(datetime.now())))
                conn.commit()
                st.success("✅ Submission successful!")
            else:
                st.warning("Please upload a file.")
        conn.close()

# ===========================
# MAIN APP
# ===========================
def main():
    st.set_page_config("Lab Exam System", page_icon="🧪", layout="centered")
    st.title("🧪 Lab Exam Management System")

    menu = ["Teacher Login", "Teacher Register", "Student Portal"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Teacher Register":
        teacher_register()
    elif choice == "Teacher Login":
        if "logged_in" in st.session_state and st.session_state["logged_in"]:
            teacher_dashboard()
        else:
            teacher_login()
    elif choice == "Student Portal":
        student_portal()

if __name__ == "__main__":
    main()
