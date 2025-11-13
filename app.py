import streamlit as st
import sqlite3
import hashlib
import datetime
import os
import zipfile
from io import BytesIO

DB_PATH = "exam_app.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher TEXT,
                    lab_name TEXT,
                    passcode TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    active INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher TEXT,
                    lab_name TEXT,
                    student_id TEXT,
                    ip TEXT,
                    filename TEXT,
                    timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ---------------- Helper Functions ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hash_):
    return hash_password(password) == hash_

def get_client_ip():
    return st.session_state.get("client_ip", f"local-{os.urandom(4).hex()}")

def get_active_exam(teacher):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM exams WHERE teacher=? AND active=1", (teacher,))
    exam = c.fetchone()
    conn.close()
    return exam

# ---------------- Teacher Functions ----------------
def teacher_register():
    st.subheader("👩‍🏫 Teacher Registration")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO teachers VALUES (?, ?)", (username, hash_password(password)))
            conn.commit()
            st.success("✅ Registration successful! Please login.")
        except sqlite3.IntegrityError:
            st.error("❌ Username already exists.")
        conn.close()

def teacher_login():
    st.subheader("👩‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT password_hash FROM teachers WHERE username=?", (username,))
        record = c.fetchone()
        conn.close()
        if record and verify_password(password, record[0]):
            st.session_state["teacher"] = username
            st.session_state["page"] = "teacher_dashboard"
        else:
            st.error("❌ Invalid username or password")

def teacher_dashboard():
    st.header(f"Teacher Dashboard - {st.session_state['teacher']}")
    st.subheader("🧪 Create / Manage Exam")

    lab_name = st.text_input("Lab Name")
    passcode = st.text_input("Exam Passcode")
    start_time = st.time_input("Start Time", datetime.time(9, 0))
    end_time = st.time_input("End Time", datetime.time(10, 0))
    
    if st.button("Create Exam"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO exams (teacher, lab_name, passcode, start_time, end_time, active) VALUES (?, ?, ?, ?, ?, 0)",
                  (st.session_state["teacher"], lab_name, passcode, str(start_time), str(end_time)))
        conn.commit()
        conn.close()
        st.success("✅ Exam created successfully! Passcode saved privately.")
    
    st.divider()
    st.subheader("⚙️ Manage Existing Exams")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM exams WHERE teacher=?", (st.session_state["teacher"],))
    exams = c.fetchall()
    conn.close()

    for ex in exams:
        ex_id, teacher, lab_name, passcode, stime, etime, active = ex
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.write(f"📘 {lab_name}")
        with col2:
            st.write(f"🕒 {stime} - {etime}")
        with col3:
            st.write("🟢 Active" if active else "🔴 Inactive")
        with col4:
            if st.button("Toggle Active", key=f"toggle_{ex_id}"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE exams SET active=? WHERE id=?", (0 if active else 1, ex_id))
                conn.commit()
                conn.close()
                st.rerun()

    st.divider()
    st.subheader("📁 View & Download Submissions")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT lab_name FROM submissions WHERE teacher=?", (st.session_state["teacher"],))
    labs = [x[0] for x in c.fetchall()]
    conn.close()

    if labs:
        lab_choice = st.selectbox("Select Lab", labs)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT student_id, filename, timestamp FROM submissions WHERE teacher=? AND lab_name=?",
                  (st.session_state["teacher"], lab_choice))
        records = c.fetchall()
        conn.close()

        for r in records:
            st.write(f"👨‍🎓 {r[0]} — {r[1]} — {r[2]}")
        
        if st.button("Download All as ZIP"):
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for r in records:
                    file_path = os.path.join(UPLOAD_DIR, r[1])
                    if os.path.exists(file_path):
                        zf.write(file_path, arcname=r[1])
            st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name=f"{lab_choice}_submissions.zip")
    else:
        st.info("No submissions yet.")

# ---------------- Student Portal ----------------
def student_portal():
    st.header("🎓 Student Exam Portal")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT teacher FROM exams")
    teachers = [x[0] for x in c.fetchall()]
    conn.close()

    teacher = st.selectbox("Select Teacher", teachers)
    passcode = st.text_input("Enter Exam Passcode")
    student_id = st.text_input("Enter Student ID")
    file = st.file_uploader("Upload your answer file", type=["zip", "pdf", "docx", "txt"])

    if st.button("Submit"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM exams WHERE teacher=? AND passcode=? AND active=1", (teacher, passcode))
        exam = c.fetchone()

        if not exam:
            st.error("❌ Exam not active or invalid passcode.")
        else:
            _, _, lab_name, _, stime, etime, active = exam
            now = datetime.datetime.now().time()
            if not (datetime.time.fromisoformat(stime) <= now <= datetime.time.fromisoformat(etime)):
                st.error("❌ Not within exam time window.")
            else:
                ip = get_client_ip()
                c.execute("SELECT * FROM submissions WHERE teacher=? AND lab_name=? AND (student_id=? OR ip=?)",
                          (teacher, lab_name, student_id, ip))
                if c.fetchone():
                    st.error("❌ Duplicate submission detected!")
                else:
                    filename = f"{teacher}_{lab_name}_{student_id}_{datetime.datetime.now().strftime('%H%M%S')}.dat"
                    filepath = os.path.join(UPLOAD_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(file.read())
                    c.execute("INSERT INTO submissions (teacher, lab_name, student_id, ip, filename, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                              (teacher, lab_name, student_id, ip, filename, str(datetime.datetime.now())))
                    conn.commit()
                    st.success("✅ File submitted successfully!")
        conn.close()

# ---------------- Main ----------------
def main():
    st.title("💻 Secure Lab Exam System")

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    menu = ["Home", "Teacher Login", "Teacher Register", "Student"]
    choice = st.sidebar.radio("Navigation", menu)

    if choice == "Teacher Login":
        teacher_login()
    elif choice == "Teacher Register":
        teacher_register()
    elif choice == "Student":
        student_portal()
    elif choice == "Home":
        st.markdown("### Welcome to the Lab Exam Management System")

    if st.session_state.get("page") == "teacher_dashboard":
        teacher_dashboard()

if __name__ == "__main__":
    main()
