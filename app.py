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
        /* Styling untuk teks input agar kontras */
        div[data-baseweb="input"] input { color: #000 !important; background-color: #fff !important; }
        .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
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

@st.cache_data(ttl=60)
def list_files_monitoring():
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/", max_results=500)
        return res.get('resources', [])
    except: return []

# --- 5. FUNGSI LOGIKA MONITORING (FILTER USER) ---
def proses_dan_tampilkan_data(url, current_user, is_admin=False):
    try:
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content), header=0).fillna(0)
        
        # Bersihkan nama kolom (hapus spasi di depan/belakang)
        df.columns = df.columns.str.strip()

        if 'User' in df.columns:
            if is_admin:
                st.info("💡 Mode Admin: Menampilkan Seluruh Data")
                st.dataframe(df, use_container_width=True)
            else:
                # Filter data berdasarkan User yang sedang login (case-insensitive)
                user_data = df[df['User'].astype(str).str.lower() == current_user.lower()]
                
                if not user_data.empty:
                    st.subheader(f"👋 Selamat Datang, {current_user}")
                    
                    # Tampilkan dalam bentuk Metric/Label yang rapi
                    cols = st.columns(len(user_data.columns) - 1)
                    idx_col = 0
                    for col_name in user_data.columns:
                        if col_name != 'User':
                            nilai = user_data.iloc[0][col_name]
                            # Format ribuan jika angka
                            if isinstance(nilai, (int, float)):
                                val_display = "{:,.0f}".format(nilai).replace(",", ".")
                            else:
                                val_display = nilai
                            
                            with cols[idx_col % len(cols)]:
                                st.metric(label=col_name, value=val_display)
                            idx_col += 1
                    
                    st.divider()
                    st.caption("Detail Tabel Anda:")
                    st.table(user_data)
                else:
                    st.warning(f"⚠️ Data untuk user '{current_user}' belum tersedia di file ini.")
        else:
            st.error("❌ Error: Kolom 'User' tidak ditemukan di file Excel.")
            if is_admin: st.dataframe(df)

    except Exception as e:
        st.error(f"Gagal memproses file: {e}")

# --- 6. MAIN APP ---
def main():
    init_cloudinary()
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin' not in st.session_state: st.session_state['admin'] = False

    st.sidebar.title("IC BALI")
    menu = st.sidebar.radio("Navigasi", ["Halaman Utama", "🔐 Admin Panel"])

    if menu == "Halaman Utama":
        if not st.session_state['auth']:
            st.title("📊 Monitoring Login")
            tab1, tab2 = st.tabs(["Masuk", "Daftar Akun"])
            with tab1:
                with st.form("login"):
                    u = st.text_input("Username").strip()
                    p = st.text_input("Password", type="password")
                    if st.form_submit_button("Login"):
                        db = get_json_cloud(USER_DB_PATH)
                        if u.lower() in [k.lower() for k in db.keys()]:
                            # Cari key asli untuk password
                            orig_u = [k for k in db.keys() if k.lower() == u.lower()][0]
                            if db[orig_u] == hash_password(p):
                                st.session_state['auth'] = True
                                st.session_state['user'] = orig_u
                                catat_log(orig_u)
                                st.rerun()
                        st.error("Username/Password salah")
            with tab2:
                with st.form("daftar"):
                    nu = st.text_input("Username Baru").strip()
                    np = st.text_input("Password Baru", type="password")
                    if st.form_submit_button("Buat Akun"):
                        if nu:
                            db = get_json_cloud(USER_DB_PATH)
                            db[nu] = hash_password(np)
                            save_json_cloud(db, USER_DB_PATH)
                            st.success("Berhasil! Silakan masuk di tab Login.")
        else:
            # TAMPILAN SETELAH LOGIN
            c1, c2 = st.columns([5,1])
            c2.button("Log Out", on_click=lambda: st.session_state.update({"auth": False}))
            
            files = list_files_monitoring()
            if files:
                f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                # Jika file hanya ada satu, langsung tampilkan tanpa selectbox (opsional)
                pilih_f = st.selectbox("Pilih Periode Data:", list(f_dict.keys()))
                proses_dan_tampilkan_data(f_dict[pilih_f], st.session_state['user'])
            else:
                st.info("Menunggu Admin mengunggah data...")

    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            pw_admin = st.text_input("Password Admin:", type="password")
            if st.button("Masuk"):
                if pw_admin == "ic034":
                    st.session_state['admin'] = True
                    st.rerun()
                else: st.error("Akses Ditolak")
        else:
            st.button("Keluar Admin", on_click=lambda: st.session_state.update({"admin": False}))
            t1, t2, t3 = st.tabs(["📤 Upload Data", "👥 User Akun", "📊 Log"])
            
            with t1:
                up = st.file_uploader("Upload Excel Monitoring", type=['xlsx'])
                if up and st.button("Simpan ke Web"):
                    cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                    st.success("File Berhasil Diupload!")
                    time.sleep(1)
                    st.rerun()
                
                st.divider()
                st.subheader("Lihat/Hapus File")
                files = list_files_monitoring()
                for f in files:
                    fn = f['public_id'].split('/')[-1]
                    c1, c2, c3 = st.columns([3,1,1])
                    c1.write(fn)
                    if c2.button("Lihat", key="v_"+fn):
                        proses_dan_tampilkan_data(f['secure_url'], "", is_admin=True)
                    if c3.button("Hapus", key="d_"+fn):
                        cloudinary.api.delete_resources([f['public_id']], resource_type="raw")
                        st.rerun()

            with t2:
                db_u = get_json_cloud(USER_DB_PATH)
                for u_name in list(db_u.keys()):
                    with st.expander(f"Kelola {u_name}"):
                        new_p = st.text_input(f"Reset Pass {u_name}", type="password", key="np_"+u_name)
                        if st.button(f"Update {u_name}"):
                            db_u[u_name] = hash_password(new_p)
                            save_json_cloud(db_u, USER_DB_PATH)
                            st.success("Updated")
                        if st.button(f"Hapus {u_name}", type="primary"):
                            del db_u[u_name]
                            save_json_cloud(db_u, USER_DB_PATH)
                            st.rerun()

            with t3:
                logs = get_json_cloud(LOG_DB_PATH)
                if logs:
                    df_l = pd.DataFrame([{"Tanggal": t, "User": u, "Hits": j} for t, d in logs.items() for u, j in d.items()])
                    st.dataframe(df_l, use_container_width=True)

if __name__ == "__main__":
    main()
