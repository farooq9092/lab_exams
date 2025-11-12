import streamlit as st
import os
import datetime
import random
import string
import socket

# ---------------- CONFIGURATION ----------------
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
    st.session_state.submitted_data = {}
if "page" not in st.session_state:
    st.session_state.page = "home"

# ---------------- HELPERS ----------------
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

# ---------------- TEACHER SIGNUP ----------------
def signup_teacher():
    st.title("👩‍🏫 Teacher Signup")
    name = st.text_input("Full Name")
    username = st.text_input("Username")
    phone = st.text_input("Phone Number")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if username in st.session_state.teachers:
            st.warning("⚠️ Username already exists.")
        elif not username or not password or not phone:
            st.warning("⚠️ All fields are required.")
        else:
            st.session_state.teachers[username] = {"password": password, "name": name, "phone": phone}
            st.success("✅ Registration successful! Please log in.")
            st.session_state.page = "login"

# ---------------- TEACHER LOGIN ----------------
def login_teacher():
    st.title("👨‍🏫 Teacher Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.teachers and st.session_state.teachers[username]["password"] == password:
            st.session_state.logged_in_teacher = username
            st.session_state.page = "dashboard"
        else:
            st.error("❌ Invalid username or password")

# ---------------- FORGOT PASSWORD ----------------
def forgot_password():
    st.title("🔑 Forgot Password (OTP Recovery)")
    username = st.text_input("Enter your registered username")

    if st.button("Send OTP"):
        if username in st.session_state.teachers:
            otp = generate_otp()
            st.session_state.teachers[username]["otp"] = otp
            st.info(f"📱 OTP sent to registered phone ({st.session_state.teachers[username]['phone']}) — [Simulation: {otp}]")
            st.session_state.current_reset_user = username
        else:
            st.error("❌ Username not found!")

    if "current_reset_user" in st.session_state:
        otp_input = st.text_input("Enter received OTP")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            user = st.session_state.current_reset_user
            if otp_input == st.session_state.teachers[user].get("otp"):
                st.session_state.teachers[user]["password"] = new_pass
                del st.session_state.teachers[user]["otp"]
                del st.session_state.current_reset_user
                st.success("✅ Password reset successful! Please log in.")
                st.session_state.page = "login"
            else:
                st.error("❌ Incorrect OTP.")

# ---------------- TEACHER DASHBOARD ----------------
def teacher_dashboard():
    teacher = st.session_state.logged_in_teacher
    st.sidebar.title(f"Welcome, {st.session_state.teachers[teacher]['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_teacher = None
        st.session_state.page = "login"

    st.header("📚 Teacher Dashboard")

    lab_name = st.text_input("Enter Lab Name (e.g., Lab1, Lab2)")
    folder_path = os.path.join(st.session_state.exam_folder, teacher, lab_name)
    ensure_folder(folder_path)

    # Passcode Generation
    if st.button("🎟️ Generate Passcode"):
        st.session_state.passcode = generate_passcode()
        st.success(f"Passcode for Students: {st.session_state.passcode}")

    # Time Settings
    st.subheader("⏱ Exam Timing")
    duration = st.number_input("Set Exam Duration (minutes)", min_value=5, max_value=300, value=60)
    if st.button("Start Exam"):
        st.session_state.exam_durations[lab_name] = duration
        st.success(f"Exam started for {duration} minutes.")

    extra_time = st.number_input("Extend Time (minutes)", min_value=1, max_value=60, value=10)
    if st.button("Extend Time"):
        st.session_state.exam_durations[lab_name] = st.session_state.exam_durations.get(lab_name, duration) + extra_time
        st.info(f"New Duration: {st.session_state.exam_durations[lab_name]} minutes")

    # Submitted Files
    st.subheader("📄 Submitted Papers")
    if os.path.exists(folder_path):
        files = sorted([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))])
        if files:
            for i, f in enumerate(files, 1):
                file_path = os.path.join(folder_path, f)
                st.write(f"{i}. {f}")
                with open(file_path, "rb") as fp:
                    st.download_button(f"⬇ Download {f}", data=fp, file_name=f)
            if st.button("📦 Download All (Zip)"):
                import shutil
                zip_name = f"{lab_name}_submissions.zip"
                shutil.make_archive(lab_name, 'zip', folder_path)
                with open(f"{zip_name}", "rb") as zp:
                    st.download_button("⬇ Download All Files (ZIP)", data=zp, file_name=zip_name)
        else:
            st.info("No submissions yet.")
    else:
        st.warning("No lab folder found.")

# ---------------- STUDENT PORTAL ----------------
def student_portal():
    st.title("🎓 Student Submission Portal")
    passcode = st.text_input("Enter Passcode Provided by Teacher")

    if passcode == st.session_state.passcode and st.session_state.logged_in_teacher:
        teacher = st.session_state.logged_in_teacher
        lab_name = st.text_input("Enter Lab Name (given by Teacher)")
        student_id = st.text_input("Enter Student ID")
        student_ip = get_ip()

        upload_folder = os.path.join(st.session_state.exam_folder, teacher, lab_name)
        ensure_folder(upload_folder)

        uploaded_file = st.file_uploader("Upload your Exam File (PDF or Word)", type=["pdf", "docx", "doc"])

        if uploaded_file:
            existing = [
                val for val in st.session_state.submitted_data.values()
                if val["id"] == student_id or val["ip"] == student_ip
            ]
            if existing:
                st.error("❌ Submission blocked! Same Student ID or IP already submitted.")
            else:
                files = [f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))]
                serial = generate_serial(files)
                filename = f"{serial}_{student_id}_{student_ip}_{uploaded_file.name}"
                save_path = os.path.join(upload_folder, filename)

                with open(save_path, "wb") as f:
                    f.write(uploaded_file.read())

                st.session_state.submitted_data[filename] = {"id": student_id, "ip": student_ip}
                st.success("✅ File submitted successfully!")
    else:
        st.warning("Enter a valid passcode to continue.")

# ---------------- NAVIGATION ----------------
st.sidebar.title("🔹 Navigation")
if st.session_state.page == "home":
    menu = st.sidebar.radio("Go to", ["Teacher Login", "Teacher Signup", "Forgot Password", "Student Portal"])
else:
    menu = st.session_state.page

if menu == "Teacher Signup":
    signup_teacher()
elif menu == "Teacher Login" or st.session_state.page == "login":
    if st.session_state.logged_in_teacher:
        teacher_dashboard()
    else:
        login_teacher()
elif menu == "Forgot Password":
    forgot_password()
elif menu == "dashboard":
    teacher_dashboard()
elif menu == "Student Portal":
    student_portal()
