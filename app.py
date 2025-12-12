import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup database (SQLite)
engine = create_engine("sqlite:///exam_system.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Define database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    exams = relationship("Exam", back_populates="owner")
    attempts = relationship("ExamAttempt", back_populates="user")

class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="exam")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
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
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Integer)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User", back_populates="attempts")

# Create tables
Base.metadata.create_all(bind=engine)

# Helper functions for password hashing
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

# Streamlit app UI and logic
def main():
    st.title("Offline LAN Exam System")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None

    session = SessionLocal()

    if not st.session_state.logged_in:
        auth_mode = st.sidebar.selectbox("Login / Sign Up", ["Login", "Sign Up"])
        if auth_mode == "Login":
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
        else:
            new_username = st.text_input("Choose Username", key="signup_username")
            new_password = st.text_input("Choose Password", type="password", key="signup_password")
            if st.button("Sign Up"):
                if get_user(session, new_username):
                    st.error("Username already exists.")
                elif len(new_password) < 4:
                    st.error("Password should be at least 4 characters.")
                else:
                    new_user = User(username=new_username, hashed_password=get_password_hash(new_password))
                    session.add(new_user)
                    session.commit()
                    st.success("User created successfully. Please login.")
    else:
        st.sidebar.write(f"Logged in as: {st.session_state.user.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.experimental_rerun()

        menu = st.sidebar.selectbox("Menu", ["Create Exam", "Add Questions", "Take Exam", "View Exams"])

        if menu == "Create Exam":
            st.subheader("Create New Exam")
            title = st.text_input("Exam Title")
            description = st.text_area("Exam Description")
            if st.button("Create Exam"):
                if not title.strip():
                    st.error("Exam title is required.")
                else:
                    exam = Exam(title=title.strip(), description=description.strip(), owner_id=st.session_state.user.id)
                    session.add(exam)
                    session.commit()
                    st.success(f"Exam '{title}' created.")
                    st.session_state.new_exam_id = exam.id

        elif menu == "Add Questions":
            if "new_exam_id" not in st.session_state:
                st.info("Please create an exam first.")
            else:
                exam_id = st.session_state.new_exam_id
                exam = session.query(Exam).filter(Exam.id == exam_id).first()
                if exam:
                    st.subheader(f"Add Questions to '{exam.title}'")
                    question_text = st.text_area("Question Text")
                    option1 = st.text_input("Option 1")
                    option2 = st.text_input("Option 2")
                    option3 = st.text_input("Option 3")
                    option4 = st.text_input("Option 4")
                    correct_option = st.selectbox("Correct Option", [1, 2, 3, 4])
                    if st.button("Add Question"):
                        if not all([question_text.strip(), option1.strip(), option2.strip(), option3.strip(), option4.strip()]):
                            st.error("All fields are required.")
                        else:
                            question = Question(
                                exam_id=exam_id,
                                question_text=question_text.strip(),
                                option1=option1.strip(),
                                option2=option2.strip(),
                                option3=option3.strip(),
                                option4=option4.strip(),
                                correct_option=correct_option
                            )
                            session.add(question)
                            session.commit()
                            st.success("Question added.")
                else:
                    st.error("Exam not found.")

        elif menu == "Take Exam":
            exams = session.query(Exam).all()
            if not exams:
                st.info("No exams available.")
            else:
                exam_titles = {exam.title: exam.id for exam in exams}
                selected_title = st.selectbox("Select Exam", list(exam_titles.keys()))
                if st.button("Start Exam"):
                    st.session_state.current_exam_id = exam_titles[selected_title]

            if "current_exam_id" in st.session_state:
                exam = session.query(Exam).filter(Exam.id == st.session_state.current_exam_id).first()
                if exam:
                    st.subheader(f"Exam: {exam.title}")
                    questions = exam.questions
                    answers = {}
                    for q in questions:
                        ans = st.radio(q.question_text, options=[q.option1, q.option2, q.option3, q.option4], key=f"q_{q.id}")
                        answers[q.id] = ans

                    if st.button("Submit Exam"):
                        score = 0
                        for q in questions:
                            correct_answer = getattr(q, f"option{q.correct_option}")
                            if answers[q.id] == correct_answer:
                                score += 1
                        st.success(f"Your Score: {score} / {len(questions)}")
                        attempt = ExamAttempt(exam_id=exam.id, user_id=st.session_state.user.id, score=score)
                        session.add(attempt)
                        session.commit()
                        del st.session_state.current_exam_id

        elif menu == "View Exams":
            st.subheader("All Exams")
            exams = session.query(Exam).all()
            for exam in exams:
                st.markdown(f"### {exam.title}")
                st.write(f"Description: {exam.description}")
                st.write(f"Created by User ID: {exam.owner_id}")

if __name__ == "__main__":
    main()
