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
# Pastikan Anda sudah mengisi Secrets di Streamlit Cloud
USER_DB_PATH = "Config/users_area.json"       
LOG_DB_PATH = "Config/activity_log_area.json"
MONITORING_FOLDER = "Monitoring"

def init_cloudinary():
    if "cloudinary" not in st.secrets:
        st.error("⚠️ Kunci Cloudinary belum dipasang di Secrets!")
        st.stop()
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True
    )

# --- 3. CSS CUSTOM (TAMPILAN) ---
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden; display: none;}
        footer {visibility: hidden; display: none;}
        .main .block-container {padding-top: 2rem;}
        /* Styling Input agar kontras */
        div[data-baseweb="input"] input { color: #000 !important; background-color: #fff !important; }
        /* Styling Kotak Saldo (Metric) */
        [data-testid="stMetricValue"] { font-size: 26px !important; color: #007bff !important; }
        .stMetric { 
            background-color: #ffffff; 
            padding: 20px; 
            border-radius: 12px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); 
            border-left: 5px solid #007bff; 
        }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI PEMBANTU (FORMATTING & DATABASE) ---
def format_angka_indo(nilai):
    """Format angka 1000000 menjadi 1.000.000"""
    try:
        if pd.isna(nilai) or nilai == "": return "0"
        return "{:,.0f}".format(float(nilai)).replace(",", ".")
    except:
        return nilai

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

# --- 5. LOGIKA UTAMA: PROSES EXCEL (FILTER, SUM, FORMAT) ---
def proses_dan_tampilkan_data(url, current_user, is_admin=False):
    try:
        resp = requests.get(url)
        # Membaca excel
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
        df.columns = df.columns.astype(str).str.strip() # Bersihkan nama kolom

        if 'User' not in df.columns:
            st.error("❌ File Excel tidak memiliki kolom 'User'. Harap lapor Admin.")
            return

        if is_admin:
            st.info("💡 Mode Admin: Menampilkan Seluruh Data Tanpa Filter.")
            df_admin = df.copy()
            # Format ribuan untuk kolom angka di tampilan admin
            for col in df_admin.select_dtypes(include=['number']).columns:
                df_admin[col] = df_admin[col].apply(format_angka_indo)
            
            auto_cfg = {c: st.column_config.Column(width="auto") for c in df_admin.columns}
            st.dataframe(df_admin, use_container_width=True, hide_index=True, column_config=auto_cfg)
        else:
            # FILTER DATA BERDASARKAN USER
            user_df = df[df['User'].astype(str).str.lower() == current_user.lower()].copy()

            if not user_df.empty:
                st.subheader(f"👋 Ringkasan Saldo: {current_user}")
                
                # Identifikasi kolom angka untuk di-SUM otomatis
                for col in user_df.columns:
                    if col != 'User':
                        user_df[col] = pd.to_numeric(user_df[col], errors='ignore')

                numeric_cols = user_df.select_dtypes(include=['number']).columns
                
                # A. TAMPILKAN KOTAK SALDO (SUM)
                if not numeric_cols.empty:
                    cols_ui = st.columns(len(numeric_cols))
                    for i, col_name in enumerate(numeric_cols):
                        total_sum = user_df[col_name].sum()
                        with cols_ui[i]:
                            st.metric(label=f"Total {col_name}", value=format_angka_indo(total_sum))
                
                st.divider()
                
                # B. TAMPILKAN TABEL RINCIAN (FORMAT TITIK & LEBAR OTOMATIS)
                df_display = user_df.copy()
                for col in numeric_cols:
                    df_display[col] = df_display[col].apply(format_angka_indo)
                
                st.write("**Rincian Transaksi:**")
                
                # Pengaturan lebar kolom otomatis (Auto-Width)
                auto_config = {c: st.column_config.Column(width="auto") for c in df_display.columns}
                
                st.dataframe(
                    df_display, 
                    use_container_width=True, 
                    hide_index=True, # MENGHILANGKAN CELL KOSONG DI KIRI
                    column_config=auto_config
                )
            else:
                st.warning(f"Data untuk user '{current_user}' tidak ditemukan di periode ini.")

    except Exception as e:
        st.error(f"Gagal memproses data: {e}")

# --- 6. NAVIGASI & MENU ---
def main():
    init_cloudinary()
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin' not in st.session_state: st.session_state['admin'] = False

    st.sidebar.title("IC BALI SYSTEM")
    menu = st.sidebar.radio("Navigasi", ["Monitoring User", "🔐 Admin Panel"])

    # --- HALAMAN USER ---
    if menu == "Monitoring User":
        if not st.session_state['auth']:
            st.title("📊 Portal Monitoring")
            t1, t2 = st.tabs(["Login", "Daftar Akun"])
            with t1:
                with st.form("login_form"):
                    u = st.text_input("Username").strip()
                    p = st.text_input("Password", type="password")
                    if st.form_submit_button("Masuk"):
                        db = get_json_cloud(USER_DB_PATH)
                        if u.lower() in [k.lower() for k in db.keys()]:
                            orig_u = [k for k in db.keys() if k.lower() == u.lower()][0]
                            if db[orig_u] == hash_password(p):
                                st.session_state['auth'] = True
                                st.session_state['user'] = orig_u
                                catat_log(orig_u)
                                st.rerun()
                        st.error("Username atau Password Salah!")
            with t2:
                with st.form("reg_form"):
                    nu = st.text_input("Username Baru").strip()
                    np = st.text_input("Password Baru", type="password")
                    if st.form_submit_button("Daftar"):
                        if nu and np:
                            db = get_json_cloud(USER_DB_PATH)
                            db[nu] = hash_password(np)
                            save_json_cloud(db, USER_DB_PATH)
                            st.success("Pendaftaran Berhasil! Silakan Login.")
        else:
            c1, c2 = st.columns([5,1])
            c1.info(f"Login sebagai: **{st.session_state['user']}**")
            if c2.button("Log Out"):
                st.session_state['auth'] = False
                st.rerun()
            
            st.divider()
            # List file dari folder Monitoring
            try:
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                files = res.get('resources', [])
                if files:
                    f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                    pilih_f = st.selectbox("Pilih Periode Laporan:", list(f_dict.keys()))
                    proses_dan_tampilkan_data(f_dict[pilih_f], st.session_state['user'])
                else:
                    st.info("Admin belum mengunggah laporan Excel.")
            except:
                st.error("Gagal mengambil data dari server.")

    # --- HALAMAN ADMIN ---
    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            st.subheader("Akses Terbatas")
            pw_admin = st.text_input("Password Admin:", type="password")
            if st.button("Masuk Panel"):
                if pw_admin == "ic034":
                    st.session_state['admin'] = True
                    st.rerun()
                else: st.error("Akses Ditolak!")
        else:
            st.success("✅ Terautentikasi sebagai Admin")
            if st.button("Keluar Panel Admin"):
                st.session_state['admin'] = False
                st.rerun()
            
            tab_up, tab_user, tab_log = st.tabs(["📤 Upload Excel", "👥 Kelola User", "📈 Log Akses"])
            
            with tab_up:
                st.write("### Unggah Data Excel (.xlsx)")
                up = st.file_uploader("Pilih file", type=['xlsx'])
                if up and st.button("Simpan ke Cloud"):
                    with st.spinner("Mengunggah..."):
                        cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                        st.success(f"Berhasil: {up.name}")
                        time.sleep(1)
                        st.rerun()
                
                st.divider()
                st.write("### Daftar File Terupload")
                try:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                    for f in res.get('resources', []):
                        fn = f['public_id'].split('/')[-1]
                        c1, c2 = st.columns([4,1])
                        c1.write(f"📄 {fn}")
                        if c2.button("Hapus", key=f['public_id']):
                            cloudinary.api.delete_resources([f['public_id']], resource_type="raw")
                            st.rerun()
                except: pass

            with tab_user:
                db_u = get_json_cloud(USER_DB_PATH)
                st.write(f"Total User Terdaftar: {len(db_u)}")
                for username in list(db_u.keys()):
                    with st.expander(f"User: {username}"):
                        if st.button(f"Hapus Akun {username}", type="primary"):
                            del db_u[username]
                            save_json_cloud(db_u, USER_DB_PATH)
                            st.rerun()

            with tab_log:
                logs = get_json_cloud(LOG_DB_PATH)
                if logs:
                    rekap = []
                    for tgl, u_data in logs.items():
                        for usr, hits in u_data.items():
                            rekap.append({"Tanggal": tgl, "User": usr, "Jumlah Akses": hits})
                    st.table(pd.DataFrame(rekap).sort_values(by="Tanggal", ascending=False))

if __name__ == "__main__":
    main()
