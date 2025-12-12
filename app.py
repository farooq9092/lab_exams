import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import os
import socket
import zipfile

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# Password hashing
from passlib.context import CryptContext

# ------------------ Config -------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "exam_app.db"
SUBMISSION_DIR = BASE_DIR / "submissions"
SUBMISSION_DIR.mkdir(exist_ok=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ------------------ Database Setup -------------------
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    exams = relationship("Exam", back_populates="teacher")

class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    exam_name = Column(String, nullable=False)
    exam_code = Column(String, unique=True, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    teacher = relationship("Teacher", back_populates="exams")
    submissions = relationship("Submission", back_populates="exam")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    student_ip = Column(String, nullable=False)
    student_name = Column(String, nullable=False)
    roll_number = Column(String, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String, nullable=False)
    resubmission_used = Column(Boolean, default=False)
    exam = relationship("Exam", back_populates="submissions")

Base.metadata.create_all(engine)

# ------------------ Helpers -------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

def try_detect_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def save_uploaded_file(uploaded_file, dest_path: str):
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# ------------------ Streamlit UI -------------------

st.set_page_config(page_title="Offline LAN Exam System", layout="wide")
st.title("Offline LAN Exam System")

menu = st.sidebar.selectbox("I am a", ["Teacher", "Student", "Admin / Info"])

if menu == "Teacher":
    st.header("Teacher Portal")
    tab = st.sidebar.radio("Action", ["Register", "Login"])

    if tab == "Register":
        st.subheader("Register as Teacher")
        name = st.text_input("Full name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            if not (name and email and password):
                st.error("Please fill all fields")
            else:
                db = SessionLocal()
                exists = db.query(Teacher).filter(Teacher.email == email).first()
                if exists:
                    st.error("Email already registered")
                else:
                    t = Teacher(name=name, email=email, password_hash=hash_password(password))
                    db.add(t)
                    db.commit()
                    st.success("Registration successful! Please login.")
                db.close()

    elif tab == "Login":
        st.subheader("Teacher Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if not (email and password):
                st.error("Please enter email and password")
            else:
                db = SessionLocal()
                t = db.query(Teacher).filter(Teacher.email == email).first()
                if not t or not verify_password(password, t.password_hash):
                    st.error("Invalid credentials")
                else:
                    st.success(f"Welcome {t.name}")
                    st.session_state["teacher_id"] = t.id
                    st.session_state["teacher_name"] = t.name
                db.close()

        # Logged in dashboard
        if st.session_state.get("teacher_id"):
            teacher_id = st.session_state["teacher_id"]
            st.markdown("---")
            st.subheader("Create Exam")
            exam_name = st.text_input("Exam Name", key="exam_name")
            exam_code = st.text_input("Exam Code (unique)", key="exam_code")
            start_time = st.datetime_input("Start Time (UTC)", value=datetime.utcnow())
            end_time = st.datetime_input("End Time (UTC)", value=datetime.utcnow() + timedelta(hours=1))
            if st.button("Create Exam"):
                if not (exam_name and exam_code):
                    st.error("Please provide exam name and code")
                else:
                    db = SessionLocal()
                    exists = db.query(Exam).filter(Exam.exam_code == exam_code).first()
                    if exists:
                        st.error("Exam code already exists")
                    else:
                        ex = Exam(
                            teacher_id=teacher_id,
                            exam_name=exam_name,
                            exam_code=exam_code,
                            start_time=start_time,
                            end_time=end_time,
                        )
                        db.add(ex)
                        db.commit()
                        st.success(f"Exam '{exam_name}' created!")
                    db.close()

            st.markdown("---")
            st.subheader("Your Exams")
            db = SessionLocal()
            exams = db.query(Exam).filter(Exam.teacher_id == teacher_id).all()
            for e in exams:
                with st.expander(f"{e.exam_name} — {e.exam_code} (ID: {e.id})"):
                    st.write(f"Start: {e.start_time}")
                    st.write(f"End: {e.end_time}")
                    cols = st.columns(3)
                    if cols[0].button("Delete Exam", key=f"del_{e.id}"):
                        try:
                            folder = SUBMISSION_DIR / e.exam_code
                            if folder.exists():
                                for f in folder.iterdir():
                                    f.unlink()
                                folder.rmdir()
                            db.query(Submission).filter(Submission.exam_id == e.id).delete()
                            db.delete(e)
                            db.commit()
                            st.success("Exam deleted")
                            st.experimental_rerun()
                        except Exception as ex_del:
                            st.error(f"Failed to delete exam: {ex_del}")

                    if cols[1].button("View Submissions", key=f"view_{e.id}"):
                        subs = db.query(Submission).filter(Submission.exam_id == e.id).all()
                        if not subs:
                            st.info("No submissions yet.")
                        else:
                            for s in subs:
                                st.write(f"{s.student_name} ({s.roll_number}) - {s.student_ip} at {s.submitted_at}")
                                if s.file_path and os.path.exists(s.file_path):
                                    with open(s.file_path, "rb") as fh:
                                        st.download_button(f"Download {os.path.basename(s.file_path)}", data=fh, file_name=os.path.basename(s.file_path))

                    if cols[2].button("Download All ZIP", key=f"zip_{e.id}"):
                        subs = db.query(Submission).filter(Submission.exam_id == e.id).all()
                        if not subs:
                            st.info("No submissions to zip")
                        else:
                            zip_path = SUBMISSION_DIR / f"exam_{e.id}_all.zip"
                            with zipfile.ZipFile(zip_path, "w") as zipf:
                                for s in subs:
                                    if s.file_path and os.path.exists(s.file_path):
                                        zipf.write(s.file_path, os.path.basename(s.file_path))
                            with open(zip_path, "rb") as fh:
                                st.download_button("Download ZIP", fh, file_name=zip_path.name)
            db.close()

elif menu == "Student":
    st.header("Student Submission Portal")
    st.info("Enter exam code, your name, roll number, and upload your answer file.\nIf you know your device IP, enter it to enforce one submission per device.")

    with st.form("submit_form"):
        exam_code = st.text_input("Exam Code")
        student_name = st.text_input("Your Name")
        roll_number = st.text_input("Roll Number")
        detected_ip = try_detect_ip()
        st.write(f"Detected device IP: {detected_ip}")
        student_ip = st.text_input("Your Device IP (leave blank to use detected)", value="")
        uploaded_file = st.file_uploader("Upload Answer File (PDF/DOCX/Images etc.)")
        submitted = st.form_submit_button("Submit")

    if submitted:
        if not (exam_code and student_name and roll_number and uploaded_file):
            st.error("All fields and file upload are required!")
        else:
            client_ip = student_ip.strip() if student_ip.strip() else detected_ip
            db = SessionLocal()
            exam = db.query(Exam).filter(Exam.exam_code == exam_code).first()
            if not exam:
                st.error("Invalid exam code")
            else:
                now = datetime.utcnow()
                if now > exam.end_time:
                    st.error("Exam time has ended, submission rejected.")
                else:
                    existing = db.query(Submission).filter(Submission.exam_id == exam.id, Submission.student_ip == client_ip).first()
                    if existing:
                        st.error("You have already submitted from this device/IP. Contact teacher if resubmission is needed.")
                    else:
                        safe_name = f"{roll_number}_{student_name}_{os.path.basename(uploaded_file.name)}".replace(" ", "_")
                        folder = SUBMISSION_DIR / exam.exam_code
                        folder.mkdir(parents=True, exist_ok=True)
                        file_path = folder / safe_name
                        try:
                            save_uploaded_file(uploaded_file, str(file_path))
                            sub = Submission(
                                exam_id=exam.id,
                                student_ip=client_ip,
                                student_name=student_name,
                                roll_number=roll_number,
                                file_path=str(file_path),
                                submitted_at=datetime.utcnow()
                            )
                            db.add(sub)
                            db.commit()
                            st.success("Submission successful!")
                        except Exception as e:
                            st.error(f"Failed to save submission: {e}")
            db.close()

else:
    st.header("Admin / Info")
    st.write("How to run on LAN:")
    st.code("streamlit run app.py --server.address=0.0.0.0 --server.port=8501")
    st.write("Then other devices on same LAN can access at: http://<server-ip>:8501")
    st.markdown("---")
    st.write("Notes:")
    st.write("- Data stored locally in SQLite DB and ./submissions folder. Backup regularly!")
    st.write("- Teacher passwords are securely hashed with bcrypt.")
    st.write("- Student IP detection is best-effort; asking students to enter device IP helps enforce one submission per device.")
    st.write("- For secure LAN communication consider using reverse proxy with TLS.")

st.markdown("---")
st.caption("Offline LAN Exam System - Streamlit (single file)")
