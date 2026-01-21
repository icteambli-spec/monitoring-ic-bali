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

# --- 2. KONFIGURASI CLOUDINARY & PATH ---
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
        div[data-baseweb="input"] input { color: #000 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI SISTEM ---
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

@st.cache_data(ttl=300)
def list_files_monitoring():
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/", max_results=500)
        return res.get('resources', [])
    except: return []

# --- 5. FUNGSI EXCEL ---
def tampilkan_excel(url):
    try:
        resp = requests.get(url)
        xl = pd.ExcelFile(io.BytesIO(resp.content))
        sh = st.selectbox("Pilih Sheet:", xl.sheet_names)
        hd = st.number_input("Header Baris ke-:", value=1)
        df = pd.read_excel(io.BytesIO(resp.content), sheet_name=sh, header=hd-1).fillna("")
        
        cari = st.text_input("Cari Data:")
        if cari:
            mask = df.astype(str).apply(lambda x: x.str.contains(cari, case=False)).any(axis=1)
            df = df[mask]
        
        st.dataframe(df, use_container_width=True, height=500)
        st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "data.csv", "text/csv")
    except Exception as e:
        st.error(f"Gagal membaca file: {e}")

# --- 6. MAIN APP ---
def main():
    init_cloudinary()
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin' not in st.session_state: st.session_state['admin'] = False

    st.title("📊 Monitoring IC Bali")
    menu = st.sidebar.radio("Navigasi", ["Halaman Utama", "🔐 Admin Panel"])

    # --- HALAMAN USER ---
    if menu == "Halaman Utama":
        if not st.session_state['auth']:
            tab1, tab2 = st.tabs(["Login", "Daftar Akun"])
            with tab1:
                with st.form("login_form"):
                    u = st.text_input("Username")
                    p = st.text_input("Password", type="password")
                    if st.form_submit_button("Masuk"):
                        db = get_json_cloud(USER_DB_PATH)
                        if u in db and db[u] == hash_password(p):
                            st.session_state['auth'] = True
                            st.session_state['user'] = u
                            catat_log(u)
                            st.rerun()
                        else: st.error("Username/Password salah")
            with tab2:
                with st.form("reg_form"):
                    nu = st.text_input("Username Baru")
                    np = st.text_input("Password Baru", type="password")
                    if st.form_submit_button("Daftar"):
                        db = get_json_cloud(USER_DB_PATH)
                        if nu in db: st.error("Username sudah ada")
                        else:
                            db[nu] = hash_password(np)
                            save_json_cloud(db, USER_DB_PATH)
                            st.success("Berhasil daftar! Silakan Login.")
        else:
            c1, c2 = st.columns([5,1])
            c1.write(f"👋 Halo, **{st.session_state['user']}**")
            if c2.button("Logout"):
                st.session_state['auth'] = False
                st.rerun()
            
            st.divider()
            files = list_files_monitoring()
            if files:
                f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                pilih_f = st.selectbox("Pilih File Monitoring:", list(f_dict.keys()))
                tampilkan_excel(f_dict[pilih_f])
            else:
                st.info("Belum ada file monitoring yang diupload admin.")

    # --- HALAMAN ADMIN ---
    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            pw_admin = st.text_input("Masukkan Password Admin:", type="password")
            if st.button("Masuk Admin"):
                if pw_admin == "ic034":
                    st.session_state['admin'] = True
                    st.rerun()
                else: st.error("Password Salah!")
        else:
            if st.button("Keluar Panel Admin"):
                st.session_state['admin'] = False
                st.rerun()
            
            tab_f, tab_u, tab_l = st.tabs(["📂 Kelola File", "👥 Kelola User", "📈 Log Aktivitas"])
            
            with tab_f:
                st.subheader("Upload File Monitoring (Excel)")
                up = st.file_uploader("Pilih file .xlsx", type=['xlsx'])
                if up and st.button("Upload Sekarang"):
                    with st.spinner("Mengunggah..."):
                        cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                        st.success(f"Berhasil upload: {up.name}")
                        time.sleep(1)
                        st.rerun()
                
                st.divider()
                st.subheader("Hapus File")
                files = list_files_monitoring()
                if files:
                    for f in files:
                        fname = f['public_id'].split('/')[-1]
                        c1, c2 = st.columns([3,1])
                        c1.write(fname)
                        if c2.button("Hapus", key=f['public_id']):
                            cloudinary.api.delete_resources([f['public_id']], resource_type="raw")
                            st.success("Terhapus")
                            st.rerun()

            with tab_u:
                st.subheader("Daftar User & Management")
                db_u = get_json_cloud(USER_DB_PATH)
                if db_u:
                    for user_name in list(db_u.keys()):
                        with st.expander(f"User: {user_name}"):
                            new_p = st.text_input(f"Password Baru untuk {user_name}", type="password", key=f"p_{user_name}")
                            c1, c2 = st.columns(2)
                            if c1.button(f"Update Password {user_name}"):
                                if new_p:
                                    db_u[user_name] = hash_password(new_p)
                                    save_json_cloud(db_u, USER_DB_PATH)
                                    st.success("Password diupdate")
                            if c2.button(f"Hapus Akun {user_name}", type="primary"):
                                del db_u[user_name]
                                save_json_cloud(db_u, USER_DB_PATH)
                                st.rerun()
                else: st.info("Tidak ada user terdaftar.")

            with tab_l:
                st.subheader("Log Aktivitas User")
                logs = get_json_cloud(LOG_DB_PATH)
                if logs:
                    rekap = []
                    for tgl, u_data in logs.items():
                        for usr, jml in u_data.items():
                            rekap.append({"Tanggal": tgl, "Username": usr, "Akses": jml})
                    df_log = pd.DataFrame(rekap).sort_values(by="Tanggal", ascending=False)
                    st.dataframe(df_log, use_container_width=True)
                    st.download_button("📥 Download Log CSV", df_log.to_csv(index=False).encode('utf-8'), "log_aktivitas.csv", "text/csv")
                else: st.info("Belum ada log aktivitas.")

if __name__ == "__main__":
    main()
