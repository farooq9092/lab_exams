"""
Single-file Streamlit app for Offline LAN Exam System
Features:
- Teacher register / login (bcrypt hashed passwords)
- Create / list / delete exams
- Student submission with one-submission-per-IP restriction
- File storage under ./submissions/<exam_code>/
- Download submissions as ZIP by teacher
- Run on LAN: streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=8501

Notes:
- Streamlit cannot reliably detect client IP from server side; students should enter their device IP in the form (auto-detect attempt included).
- Configure sensible defaults in constants below.
"""

import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import os
import zipfile
import socket

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from passlib.context import CryptContext

# ----------------------
# Configuration
# ----------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "exam_app_streamlit.db"
SUBMISSION_DIR = BASE_DIR / "submissions"
SUBMISSION_DIR.mkdir(exist_ok=True)

# Streamlit server host/port instructions shown to user later

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ----------------------
# Database (SQLAlchemy)
# ----------------------
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    exams = relationship('Exam', back_populates='teacher')

class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    exam_name = Column(String)
    exam_code = Column(String, unique=True, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    teacher = relationship('Teacher', back_populates='exams')
    submissions = relationship('Submission', back_populates='exam')

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey('exams.id'))
    student_ip = Column(String)
    student_name = Column(String)
    roll_number = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String)
    resubmission_used = Column(Boolean, default=False)
    exam = relationship('Exam', back_populates='submissions')

Base.metadata.create_all(bind=engine)

# ----------------------
# Helpers
# ----------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def try_detect_ip():
    # Attempt to detect local IP address used on LAN
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # doesn't need to be reachable
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def save_uploaded_file(uploaded_file, dest_path: str):
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# ----------------------
# Streamlit UI
# ----------------------

st.set_page_config(page_title="Offline Exam - Streamlit", layout="wide")
st.title("Offline Exam System — Streamlit (LAN)")

menu = st.sidebar.selectbox("I am a", ["Teacher", "Student", "Admin / Info"])

# ----------------------
# Teacher area
# ----------------------
if menu == "Teacher":
    st.header("Teacher Portal")
    tab = st.sidebar.radio("Action", ["Login", "Register"])

    if tab == "Register":
        st.subheader("Register as Teacher")
        name = st.text_input("Full name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            if not (name and email and password):
                st.error("Please provide name, email and password")
            else:
                db = next(get_db())
                exists = db.query(Teacher).filter(Teacher.email == email).first()
                if exists:
                    st.error("Email already registered")
                else:
                    t = Teacher(name=name, email=email, password_hash=hash_password(password))
                    db.add(t)
                    db.commit()
                    db.refresh(t)
                    st.success(f"Registered. Your teacher id: {t.id}")

    elif tab == "Login":
        st.subheader("Teacher Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if not (email and password):
                st.error("Provide email and password")
            else:
                db = next(get_db())
                t = db.query(Teacher).filter(Teacher.email == email).first()
                if not t or not verify_password(password, t.password_hash):
                    st.error("Invalid credentials")
                else:
                    st.success(f"Welcome {t.name}")
                    st.session_state["teacher_id"] = t.id
                    st.session_state["teacher_name"] = t.name

        # If logged in, show teacher dashboard
        if st.session_state.get("teacher_id"):
            teacher_id = st.session_state["teacher_id"]
            st.markdown("---")
            st.subheader("Create Exam")
            exam_name = st.text_input("Exam name", key="exam_name")
            exam_code = st.text_input("Exam code (unique)", key="exam_code")
            start_time = st.datetime_input("Start time (UTC)", value=datetime.utcnow())
            end_time = st.datetime_input("End time (UTC)", value=datetime.utcnow() + timedelta(hours=1))
            if st.button("Create Exam"):
                if not (exam_name and exam_code):
                    st.error("Provide exam name and code")
                else:
                    db = next(get_db())
                    exists = db.query(Exam).filter(Exam.exam_code == exam_code).first()
                    if exists:
                        st.error("Exam code already exists")
                    else:
                        ex = Exam(teacher_id=teacher_id, exam_name=exam_name, exam_code=exam_code,
                                  start_time=start_time, end_time=end_time)
                        db.add(ex)
                        db.commit()
                        db.refresh(ex)
                        st.success(f"Exam created (id={ex.id})")

            st.markdown("---")
            st.subheader("Your Exams")
            db = next(get_db())
            exams = db.query(Exam).filter(Exam.teacher_id == teacher_id).all()
            for e in exams:
                with st.expander(f"{e.exam_name} — {e.exam_code} (id={e.id})"):
                    st.write("Start:", e.start_time.isoformat() if e.start_time else "-")
                    st.write("End:", e.end_time.isoformat() if e.end_time else "-")
                    cols = st.columns(3)
                    if cols[0].button("Delete exam", key=f"del_{e.id}"):
                        # delete submissions records and files
                        db2 = next(get_db())
                        subs = db2.query(Submission).filter(Submission.exam_id == e.id).all()
                        # delete DB rows
                        try:
                            db2.query(Submission).filter(Submission.exam_id == e.id).delete(synchronize_session=False)
                            db2.delete(e)
                            db2.commit()
                        except Exception as ex_del:
                            db2.rollback()
                            st.error(f"Failed to delete exam: {ex_del}")
                        else:
                            # delete files on filesystem
                            exam_folder = SUBMISSION_DIR / e.exam_code
                            if exam_folder.exists():
                                for fpath in exam_folder.glob("*"):
                                    try:
                                        fpath.unlink()
                                    except Exception:
                                        pass
                                try:
                                    exam_folder.rmdir()
                                except Exception:
                                    pass
                            st.success("Exam and submissions deleted")
                            st.experimental_rerun()

                    if cols[1].button("View submissions", key=f"view_{e.id}"):
                        db3 = next(get_db())
                        subs = db3.query(Submission).filter(Submission.exam_id == e.id).all()
                        if not subs:
                            st.info("No submissions yet")
                        else:
                            for s in subs:
                                st.write(f"{s.id} — {s.student_name} — {s.roll_number} — {s.student_ip} — {s.submitted_at}")
                                dlc = st.columns([1,5])[0]
                                if dlc.button("Download", key=f"dl_{s.id}"):
                                    if s.file_path and os.path.exists(s.file_path):
                                        with open(s.file_path, "rb") as fh:
                                            data = fh.read()
                                        st.download_button(label="Download file", data=data, file_name=os.path.basename(s.file_path))
                                    else:
                                        st.error("File missing on server")

                    if cols[2].button("Download all as ZIP", key=f"zip_{e.id}"):
                        db4 = next(get_db())
                        subs = db4.query(Submission).filter(Submission.exam_id == e.id).all()
                        if not subs:
                            st.info("No submissions to zip")
                        else:
                            zip_dir = SUBMISSION_DIR / "zips"
                            zip_dir.mkdir(exist_ok=True)
                            zip_path = zip_dir / f"exam_{e.id}_all.zip"
                            with zipfile.ZipFile(zip_path, "w") as zipf:
                                for s in subs:
                                    if s.file_path and os.path.exists(s.file_path):
                                        zipf.write(s.file_path, os.path.basename(s.file_path))
                            with open(zip_path, "rb") as fh:
                                st.download_button("Download ZIP", fh, file_name=zip_path.name)

# ----------------------
# Student area
# ----------------------
elif menu == "Student":
    st.header("Student Submission Portal")
    st.info("Enter exam code, your name, roll number and upload your answer file.\nIf you know your device IP, enter it to ensure one-submission-per-device enforcement.")

    with st.form("submit_form"):
        exam_code = st.text_input("Exam code")
        student_name = st.text_input("Your name")
        roll_number = st.text_input("Roll number")
        detected_ip = try_detect_ip()
        st.write("Detected (server-sensed) LAN IP:", detected_ip)
        student_ip = st.text_input("Your device IP (leave blank to use detected)", value="")
        uploaded_file = st.file_uploader("Answer file (pdf / docx / images etc.)")
        submitted = st.form_submit_button("Submit")

    if submitted:
        if not (exam_code and student_name and roll_number and uploaded_file):
            st.error("All fields + file are required")
        else:
            client_ip = student_ip.strip() if student_ip.strip() else detected_ip
            db = next(get_db())
            exam = db.query(Exam).filter(Exam.exam_code == exam_code).first()
            if not exam:
                st.error("Invalid exam code")
            else:
                now = datetime.utcnow()
                if now > exam.end_time:
                    st.error("Exam time has ended. Submission refused.")
                else:
                    existing = db.query(Submission).filter(Submission.exam_id == exam.id, Submission.student_ip == client_ip).first()
                    if existing:
                        st.error("This device/IP has already submitted. Ask teacher to allow resubmission if needed.")
                    else:
                        safe_name = f"{roll_number}_{student_name}_{os.path.basename(uploaded_file.name)}".replace(" ", "_")
                        folder = SUBMISSION_DIR / exam.exam_code
                        folder.mkdir(parents=True, exist_ok=True)
                        file_path = folder / safe_name
                        try:
                            save_uploaded_file(uploaded_file, str(file_path))
                        except Exception as e:
                            st.error(f"Failed to save file: {e}")
                        else:
                            sub = Submission(exam_id=exam.id, student_ip=client_ip, student_name=student_name,
                                             roll_number=roll_number, file_path=str(file_path), submitted_at=datetime.utcnow())
                            db.add(sub)
                            db.commit()
                            st.success("File submitted successfully")

# ----------------------
# Admin / Info
# ----------------------
else:
    st.header("Admin / Run Info")
    st.write("How to run on LAN:")
    st.code("streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=8501")
    st.write("Then other devices on the same LAN can open: http://<server-ip>:8501")
    st.markdown("---")
    st.write("Configuration & security notes:")
    st.write("- This app stores data in a local SQLite file and files under ./submissions/. Make backups.")
    st.write("- Streamlit by default runs over plain HTTP. For encrypted LAN traffic consider placing a reverse proxy with TLS on the server machine.")
    st.write("- Teacher passwords are hashed with bcrypt.")
    st.write("- Student IP detection is best-effort. Ask students to enter their device IP for reliable one-submission-per-device enforcement.")

# Footer
st.markdown("---")
st.caption("Offline Exam System — Streamlit single-file prototype. Customize as needed.")
