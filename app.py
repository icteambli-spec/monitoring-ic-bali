import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import hashlib
import requests
import io
import json
import time
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="IC Bali Monitoring", layout="wide", page_icon="📊")

# --- 2. KONFIGURASI CLOUDINARY ---
USER_DB_PATH = "Config/users_area.json"       
LOG_DB_PATH = "Config/activity_log_area.json"
MONITORING_FOLDER = "Monitoring"

def init_cloudinary():
    if "cloudinary" not in st.secrets:
        st.error("⚠️ Secrets 'cloudinary' tidak ditemukan!")
        st.stop()
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True
    )

# --- 3. CSS CUSTOM ---
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden; display: none;}
        footer {visibility: hidden; display: none;}
        .main .block-container {padding-top: 2rem;}
        div[data-baseweb="input"] input { color: #000 !important; background-color: #fff !important; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #007bff; }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI DATABASE & AUTH ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_json_cloud(public_id):
    try:
        resource = cloudinary.api.resource(public_id, resource_type="raw")
        url = f"{resource.get('secure_url')}?t={int(time.time())}"
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else {}
    except: return {}

def save_json_cloud(data_dict, public_id):
    json_data = json.dumps(data_dict)
    cloudinary.uploader.upload(io.BytesIO(json_data.encode('utf-8')), resource_type="raw", public_id=public_id, overwrite=True)

def catat_log(username):
    try:
        logs = get_json_cloud(LOG_DB_PATH)
        tgl = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")
        if tgl not in logs: logs[tgl] = {}
        logs[tgl][username] = logs[tgl].get(username, 0) + 1
        save_json_cloud(logs, LOG_DB_PATH)
    except: pass

@st.cache_data(ttl=60)
def list_files_monitoring():
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/", max_results=500)
        return res.get('resources', [])
    except: return []

# --- 5. LOGIKA PENJUMLAHAN OTOMATIS (SUM LOGIC) ---
def proses_dan_tampilkan_data(url, current_user, is_admin=False):
    try:
        resp = requests.get(url)
        # Load Excel
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
        df.columns = df.columns.str.strip() # Bersihkan spasi di nama kolom

        if 'User' not in df.columns:
            st.error("❌ Kolom 'User' tidak ditemukan!")
            return

        if is_admin:
            st.info("💡 Mode Admin: Menampilkan Seluruh Data")
            st.dataframe(df, use_container_width=True)
        else:
            # 1. Filter baris milik User (Case Insensitive)
            user_df = df[df['User'].astype(str).str.lower() == current_user.lower()].copy()

            if not user_df.empty:
                st.subheader(f"👋 Ringkasan Saldo: {current_user}")
                
                # 2. Identifikasi kolom angka untuk di-SUM
                # Kita coba konversi semua kolom (selain User) ke numeric jika memungkinkan
                for col in user_df.columns:
                    if col != 'User':
                        user_df[col] = pd.to_numeric(user_df[col], errors='ignore')

                # 3. Hitung Total Sum untuk kolom numerik
                numeric_cols = user_df.select_dtypes(include=['number']).columns
                
                if not numeric_cols.empty:
                    # Tampilan Metric (Kotak Saldo)
                    cols_ui = st.columns(len(numeric_cols))
                    for i, col_name in enumerate(numeric_cols):
                        total_nilai = user_df[col_name].sum()
                        val_display = "{:,.0f}".format(total_nilai).replace(",", ".")
                        with cols_ui[i]:
                            st.metric(label=f"Total {col_name}", value=val_display)
                
                st.divider()
                # 4. Tampilkan rincian baris jika ada lebih dari satu
                if len(user_df) > 1:
                    st.caption(f"Ditemukan {len(user_df)} baris data atas nama {current_user}:")
                else:
                    st.caption("Rincian data Anda:")
                
                st.table(user_df)
            else:
                st.warning(f"Data untuk '{current_user}' belum tersedia.")

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")

# --- 6. MAIN APP ---
def main():
    init_cloudinary()
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin' not in st.session_state: st.session_state['admin'] = False

    st.sidebar.title("IC BALI")
    menu = st.sidebar.radio("Navigasi", ["Monitoring", "🔐 Admin Panel"])

    if menu == "Monitoring":
        if not st.session_state['auth']:
            st.title("📊 Portal Monitoring")
            tab1, tab2 = st.tabs(["Login", "Daftar"])
            with tab1:
                with st.form("login"):
                    u = st.text_input("Username").strip()
                    p = st.text_input("Password", type="password")
                    if st.form_submit_button("Masuk"):
                        db = get_json_cloud(USER_DB_PATH)
                        if u.lower() in [k.lower() for k in db.keys()]:
                            orig_u = [k for k in db.keys() if k.lower() == u.lower()][0]
                            if db[orig_u] == hash_password(p):
                                st.session_state['auth'], st.session_state['user'] = True, orig_u
                                catat_log(orig_u)
                                st.rerun()
                        st.error("Username/Password Salah")
            with tab2:
                with st.form("reg"):
                    nu = st.text_input("Buat Username").strip()
                    np = st.text_input("Buat Password", type="password")
                    if st.form_submit_button("Daftar"):
                        if nu and np:
                            db = get_json_cloud(USER_DB_PATH)
                            db[nu] = hash_password(np)
                            save_json_cloud(db, USER_DB_PATH)
                            st.success("Akun terdaftar! Silakan Login.")
        else:
            # Dashboard User
            c1, c2 = st.columns([5,1])
            c2.button("Keluar", on_click=lambda: st.session_state.update({"auth": False}))
            
            files = list_files_monitoring()
            if files:
                f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                pilih_f = st.selectbox("Pilih Periode Monitoring:", list(f_dict.keys()))
                proses_dan_tampilkan_data(f_dict[pilih_f], st.session_state['user'])
            else:
                st.info("Belum ada data dari Admin.")

    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            pw = st.text_input("Admin Password:", type="password")
            if st.button("Masuk Admin"):
                if pw == "ic034":
                    st.session_state['admin'] = True
                    st.rerun()
                else: st.error("Salah!")
        else:
            st.button("Tutup Panel", on_click=lambda: st.session_state.update({"admin": False}))
            t1, t2, t3 = st.tabs(["📤 Upload Excel", "👥 Kelola User", "📈 Log"])
            
            with t1:
                up = st.file_uploader("Pilih File Excel (.xlsx)", type=['xlsx'])
                if up and st.button("Upload File"):
                    cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                    st.success("File Terupload!")
                    time.sleep(1)
                    st.rerun()
                
                st.divider()
                files = list_files_monitoring()
                for f in files:
                    fn = f['public_id'].split('/')[-1]
                    c1, c2 = st.columns([4,1])
                    c1.write(fn)
                    if c2.button("Hapus", key="del_"+fn):
                        cloudinary.api.delete_resources([f['public_id']], resource_type="raw")
                        st.rerun()

            with t2:
                db_u = get_json_cloud(USER_DB_PATH)
                for u_n in list(db_u.keys()):
                    with st.expander(f"User: {u_n}"):
                        if st.button(f"Hapus {u_n}", key="h_"+u_n):
                            del db_u[u_n]
                            save_json_cloud(db_u, USER_DB_PATH)
                            st.rerun()
            with t3:
                l = get_json_cloud(LOG_DB_PATH)
                st.write(l)

if __name__ == "__main__":
    main()
