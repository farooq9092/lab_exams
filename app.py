import streamlit as st
import os, json, socket, shutil, zipfile, tempfile, logging, random, string, hashlib
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
APP_DATA = "app_data"
TEACHERS_FILE = os.path.join(APP_DATA, "teachers.json")
SUBMISSIONS_ROOT = os.path.join(APP_DATA, "submissions")
LOG_FILE = os.path.join(APP_DATA, "activity.log")
ADMIN_FILE = os.path.join(APP_DATA, "admin.json")

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(SUBMISSIONS_ROOT, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------------- UTILS ----------------
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def verify_password(p, h): return hash_password(p) == h
def load_json(fp, d=None): return json.load(open(fp)) if os.path.exists(fp) else (d or {})
def save_json(fp, d): json.dump(d, open(fp, "w"), indent=2)
def ensure_dir(p): os.makedirs(p, exist_ok=True)
def record_log(msg): logging.info(msg)
def gen_passcode(n=6): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))
def gen_otp(n=6): return ''.join(random.choices(string.digits, k=n))
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except: return "127.0.0.1"

def walk_lab_files(folder):
    lst = []; serial = 1
    if not os.path.exists(folder): return []
    for s in sorted(os.listdir(folder)):
        p = os.path.join(folder, s)
        if not os.path.isdir(p): continue
        for f in sorted(os.listdir(p)):
            fp = os.path.join(p, f)
            if os.path.isfile(fp):
                lst.append({"display": f"{serial}. {s} → {f}", "path": fp, "student": s, "filename": f, "serial": serial})
                serial += 1
    return lst

# ---------------- SESSION INIT ----------------
for k, v in {
    "teachers": load_json(TEACHERS_FILE, {}),
    "admin": load_json(ADMIN_FILE, {}),
    "logged_in_user": None,
    "logged_in_role": None,
    "active_passcodes": {},
    "submissions_index": {},
    "otp_store": {}
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ---------------- BASE FUNCS ----------------
def admin_logged(): return st.session_state.logged_in_role == "admin"
def teacher_logged(): return st.session_state.logged_in_role == "teacher"

def logout():
    st.session_state.logged_in_user = None
    st.session_state.logged_in_role_
