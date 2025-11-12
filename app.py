import streamlit as st
import os
import datetime
import random
import string
import socket
import uuid

# ----------------- Data Storage -----------------
if "teachers" not in st.session_state:
    st.session_state.teachers = {}
if "logged_in_teacher" not in st.session_state:
    st.session_state.logged_in_teacher = None
if "passcode" not in st.session_state:
    st.session_state.passcode = None
if "exam_folder" not in st.session_state:
    st.session_state.exam_folder = "Lab_Exams"
if "exam_durations" not in st.session_state:
    st.session_state.exam_durations = {}
if "submitted_data" not in st.session_state:
    st.session_state.submitted_data = {}  # store ip and id

# ----------------- Helper Functions -----------------
def generate_passcode(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown_IP"

def generate_serial(files):
    return len(files) + 1

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# ----------------- Signup & Login -----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("Username already exists.")
        elif not username or not password or not phone:
            st.warning("All fields are required.")
        else:
            st.session_state.teachers[username] = {"password": password, "name": name, "phone": phone}
            st.success("✅ Registered successfully! Please log in.")

def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
            st.success(f"Welcome {st.session_state.teachers[username]['name']}!")
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")

def forgot_password():
    st.title("🔑 Forgot Password (OTP Recovery)")
    username = st.text_input("Enter your registered username")

    if st.button("Send OTP"):
        if username in st.session_state.teachers:
            otp = generate_otp()
            st.session_state.teachers[username]["otp"] = otp
            st.info(f"📱 OTP sent to registered phone number ({st.session_state.teachers[username]['phone']})")
            st.session_state.current_reset_user = username
        else:
            st.error("Username not found!")

    if "current_reset_user" in st.session_state:
        otp_input = st.text_input("Enter received OTP")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            if otp_input == st.session_state.teachers[st.session_state.current_reset_user].get("otp"):
                st.session_state.teachers[st.session_state.current_reset_user]["password"] = new_pass
                del st.session_state.teachers[st.session_state.current_reset_user]["otp"]
                del st.session_state.current_reset_user
                st.success("✅ Password reset successful! Please log in.")
            else:
                st.error("Incorrect OTP.")

# ----------------- Teacher Dashboard -----------------
def teacher_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state.teachers[st.session_state.logged_in_teacher]['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_teacher = None
        st.experimental_rerun()

    st.header("📚 Teacher Dashboard")

    lab_name = st.text_input("Enter Lab Name (e.g., Lab1)")
    folder_path = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher, lab_name)
    ensure_folder(folder_path)

    # Generate Passcode
    if st.button("Generate Passcode for Students"):
        st.session_state.passcode = generate_passcode()
        st.success(f"🎟️ Passcode for students: {st.session_state.passcode}")

    # Set & Extend Duration
    st.subheader("⏱ Exam Time Settings")
    duration = st.number_input("Set Exam Duration (minutes)", min_value=5, max_value=300, value=60)
    if st.button("Start Exam"):
        st.session_state.exam_durations[lab_name] = duration
        st.success(f"Exam started for {duration} minutes!")

    extra_time = st.number_input("Extend by (minutes)", min_value=1, max_value=60, value=10)
    if st.button("Extend Time"):
        st.session_state.exam_durations[lab_name] = st.session_state.exam_durations.get(lab_name, duration) + extra_time
        st.info(f"Extended! New Duration: {st.session_state.exam_durations[lab_name]} minutes")

    # Show Uploaded Papers
    st.subheader("📄 Submitted Papers")
    files = os.listdir(folder_path)
    if files:
        for i, f in enumerate(sorted(files), 1):
            file_path = os.path.join(folder_path, f)
            st.write(f"{i}. {f}")
            with open(file_path, "rb") as fp:
                st.download_button(label="⬇ Download", data=fp, file_name=f)
    else:
        st.info("No papers submitted yet.")

# ----------------- Student Portal -----------------
def student_portal():
    st.title("🎓 Student Portal")
    passcode = st.text_input("Enter Passcode Provided by Teacher")

    if passcode == st.session_state.passcode and st.session_state.logged_in_teacher:
        lab_name = st.text_input("Enter Lab Name (provided by teacher)")
        student_id = st.text_input("Enter Student ID")
        student_ip = get_ip()
        teacher_folder = os.path.join(st.session_state.exam_folder, st.session_state.logged_in_teacher)
        upload_folder = os.path.join(teacher_folder, lab_name)
        ensure_folder(upload_folder)

        uploaded_file = st.file_uploader("Upload your file (PDF/Word)", type=["pdf", "docx", "doc"])
        if uploaded_file:
            existing_submissions = [
                val for val in st.session_state.submitted_data.values()
                if val["id"] == student_id or val["ip"] == student_ip
            ]
            if existing_submissions:
                st.error("❌ Submission blocked! Same ID or IP already submitted.")
            else:
                files = os.listdir(upload_folder)
                serial = generate_serial(files)
                filename = f"{serial}_{student_id}_{student_ip}_{uploaded_file.name}"
                save_path = os.path.join(upload_folder, filename)

                with open(save_path, "wb") as f:
                    f.write(uploaded_file.read())

                st.session_state.submitted_data[filename] = {"id": student_id, "ip": student_ip}
                st.success("✅ File submitted successfully!")
    else:
        st.warning("Enter a valid passcode to continue.")

# ----------------- Navigation -----------------
st.sidebar.title("🔹 Navigation")
menu = st.sidebar.radio("Go to", ["Teacher Login", "Teacher Signup", "Forgot Password", "Student Portal"])

if menu == "Teacher Signup":
    signup_teacher()
elif menu == "Teacher Login":
    if st.session_state.logged_in_teacher:
        teacher_dashboard()
    else:
        login_teacher()
elif menu == "Forgot Password":
    forgot_password()
elif menu == "Student Portal":
    student_portal()
