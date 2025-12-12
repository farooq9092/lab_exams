import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# DB setup
engine = create_engine("sqlite:///exam_system.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Database Models

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    exams = relationship("Exam", back_populates="owner")
    attempts = relationship("ExamAttempt", back_populates="user")

class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete")
    attempts = relationship("ExamAttempt", back_populates="exam")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    question_text = Column(Text)
    option1 = Column(String)
    option2 = Column(String)
    option3 = Column(String)
    option4 = Column(String)
    correct_option = Column(Integer)  # 1 to 4

    exam = relationship("Exam", back_populates="questions")

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Integer)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User", back_populates="attempts")

Base.metadata.create_all(bind=engine)

# Helper Functions

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(session, username):
    return session.query(User).filter(User.username == username).first()

def authenticate_user(session, username, password):
    user = get_user(session, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Streamlit App

st.title("Offline LAN Exam System")

# Initialize session state variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

session = SessionLocal()

def login():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = authenticate_user(session, username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid username or password")

def signup():
    st.subheader("Sign Up")
    new_username = st.text_input("Choose a username", key="signup_username")
    new_password = st.text_input("Choose a password", type="password", key="signup_password")
    if st.button("Register"):
        existing_user = get_user(session, new_username)
        if existing_user:
            st.error("Username already exists. Please choose another.")
        elif len(new_password) < 4:
            st.error("Password too short. Minimum 4 characters.")
        else:
            user = User(username=new_username, hashed_password=get_password_hash(new_password))
            session.add(user)
            session.commit()
            st.success("User created successfully. Please login.")

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.success("Logged out successfully.")

def create_exam():
    st.subheader("Create a New Exam")
    title = st.text_input("Exam Title")
    description = st.text_area("Exam Description")
    if st.button("Create Exam"):
        if title.strip() == "":
            st.error("Exam title is required.")
            return
        exam = Exam(title=title, description=description, owner_id=st.session_state.user.id)
        session.add(exam)
        session.commit()
        st.success(f"Exam '{title}' created. You can now add questions.")
        st.session_state.new_exam_id = exam.id

def add_questions(exam_id):
    st.subheader("Add Questions to Exam")
    exam = session.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        st.error("Exam not found.")
        return

    question_text = st.text_area("Question Text")
    option1 = st.text_input("Option 1")
    option2 = st.text_input("Option 2")
    option3 = st.text_input("Option 3")
    option4 = st.text_input("Option 4")
    correct_option = st.selectbox("Correct Option", options=[1, 2, 3, 4])

    if st.button("Add Question"):
        if not question_text or not option1 or not option2 or not option3 or not option4:
            st.error("All question fields are required.")
            return
        question = Question(
            exam_id=exam_id,
            question_text=question_text,
            option1=option1,
            option2=option2,
            option3=option3,
            option4=option4,
            correct_option=correct_option,
        )
        session.add(question)
        session.commit()
        st.success("Question added successfully.")

def list_exams():
    st.subheader("Available Exams")
    exams = session.query(Exam).all()
    for exam in exams:
        st.markdown(f"### {exam.title}")
        st.write(exam.description)
        if st.button(f"Attempt Exam: {exam.title}", key=f"attempt_{exam.id}"):
            st.session_state.attempt_exam_id = exam.id

def attempt_exam(exam_id):
    exam = session.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        st.error("Exam not found.")
        return

    st.subheader(f"Attempting Exam: {exam.title}")
    questions = exam.questions

    answers = []
    for q in questions:
        answer = st.radio(q.question_text, options=[q.option1, q.option2, q.option3, q.option4], key=f"q_{q.id}")
        answers.append((q, answer))

    if st.button("Submit Exam"):
        score = 0
        for q, ans in answers:
            correct_answer = getattr(q, f"option{q.correct_option}")
            if ans == correct_answer:
                score += 1
        st.success(f"Your Score: {score} / {len(questions)}")

        # Save attempt
        attempt = ExamAttempt(exam_id=exam.id, user_id=st.session_state.user.id, score=score)
        session.add(attempt)
        session.commit()

        # Reset attempt exam session state
        del st.session_state.attempt_exam_id

def main():
    if not st.session_state.logged_in:
        choice = st.sidebar.selectbox("Login or Sign Up", ["Login", "Sign Up"])
        if choice == "Login":
            login()
        else:
            signup()
    else:
        st.sidebar.write(f"Logged in as: {st.session_state.user.username}")
        if st.sidebar.button("Logout"):
            logout()

        menu = st.sidebar.selectbox("Menu", ["Create Exam", "Add Questions", "Attempt Exam", "View Exams"])

        if menu == "Create Exam":
            create_exam()

        elif menu == "Add Questions":
            if "new_exam_id" in st.session_state:
                add_questions(st.session_state.new_exam_id)
            else:
                st.info("Please create an exam first.")

        elif menu == "Attempt Exam":
            if "attempt_exam_id" in st.session_state:
                attempt_exam(st.session_state.attempt_exam_id)
            else:
                list_exams()

        elif menu == "View Exams":
            st.subheader("All Exams")
            exams = session.query(Exam).all()
            for exam in exams:
                st.write(f"**{exam.title}** - Created by User ID: {exam.owner_id}")

if __name__ == "__main__":
    main()
