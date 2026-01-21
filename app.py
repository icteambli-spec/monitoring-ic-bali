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
        st.error("⚠️ Secrets 'cloudinary' belum dipasang!")
        st.stop()
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True
    )

# --- 3. CSS CUSTOM (UI/UX) ---
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden; display: none;}
        footer {visibility: hidden; display: none;}
        .main .block-container {padding-top: 2rem;}
        /* Input text agar hitam kontras */
        div[data-baseweb="input"] input { color: #000 !important; background-color: #fff !important; }
        /* Styling Kotak Saldo (Metric) */
        [data-testid="stMetricValue"] { font-size: 26px !important; color: #007bff !important; font-weight: bold; }
        .stMetric { 
            background-color: #ffffff; 
            padding: 20px; 
            border-radius: 12px; 
            box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
            border-left: 6px solid #007bff; 
        }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI FORMATTING & DATABASE ---
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

# --- 5. LOGIKA UTAMA (FILTER, SUM, AUTO-WIDTH) ---
def proses_dan_tampilkan_data(url, current_user, is_admin=False):
    try:
        resp = requests.get(url)
        # Load Excel
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
        df.columns = df.columns.astype(str).str.strip()

        if 'User' not in df.columns:
            st.error("❌ Kolom 'User' tidak ditemukan di Excel!")
            return

        if is_admin:
            st.info("💡 Mode Admin: Menampilkan Seluruh Data")
            df_admin = df.copy()
            for col in df_admin.select_dtypes(include=['number']).columns:
                df_admin[col] = df_admin[col].apply(format_angka_indo)
            
            # Konfigurasi lebar otomatis untuk admin
            auto_cfg_admin = {c: st.column_config.Column(width="auto") for c in df_admin.columns}
            st.dataframe(df_admin, use_container_width=True, hide_index=True, column_config=auto_cfg_admin)
        else:
            # FILTER DATA BERDASARKAN USER LOGIN
            user_df = df[df['User'].astype(str).str.lower() == current_user.lower()].copy()

            if not user_df.empty:
                st.subheader(f"👋 Ringkasan Saldo Area AM/AS: {current_user}")
                
                # Identifikasi & Konversi Kolom Angka
                for col in user_df.columns:
                    if col != 'User':
                        user_df[col] = pd.to_numeric(user_df[col], errors='ignore')

                numeric_cols = user_df.select_dtypes(include=['number']).columns
                
                # A. KOTAK SALDO (SUM)
                if not numeric_cols.empty:
                    cols_ui = st.columns(len(numeric_cols))
                    for i, col_name in enumerate(numeric_cols):
                        total_sum = user_df[col_name].sum()
                        with cols_ui[i]:
                            st.metric(label=f"Total {col_name}", value=format_angka_indo(total_sum))
                
                st.divider()
                st.write("**Rincian Transaksi:**")
                
                # B. TABEL DETAIL (FORMAT TITIK & AUTO-WIDTH)
                df_display = user_df.copy()
                for col in numeric_cols:
                    df_display[col] = df_display[col].apply(format_angka_indo)
                
                # Pengaturan lebar kolom menyesuaikan karakter terpanjang
                auto_config = {c: st.column_config.Column(width="auto") for c in df_display.columns}
                
                st.dataframe(
                    df_display, 
                    use_container_width=True, 
                    hide_index=True, # Cell kosong di kiri dihilangkan
                    column_config=auto_config
                )
            else:
                st.warning(f"Data untuk '{current_user}' belum tersedia.")

    except Exception as e:
        st.error(f"Gagal memproses file: {e}")

# --- 6. NAVIGASI APP ---
def main():
    init_cloudinary()
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin' not in st.session_state: st.session_state['admin'] = False

    st.sidebar.title("IC BALI SYSTEM")
    menu = st.sidebar.radio("Menu Utama", ["📊 Monitoring User", "🔐 Admin Panel"])

    if menu == "📊 Monitoring User":
        if not st.session_state['auth']:
            st.title("Portal Monitoring")
            t1, t2 = st.tabs(["Login", "Daftar Akun"])
            with t1:
                with st.form("l"):
                    u = st.text_input("Username").strip()
                    p = st.text_input("Password", type="password")
                    if st.form_submit_button("Masuk"):
                        db = get_json_cloud(USER_DB_PATH)
                        if u.lower() in [k.lower() for k in db.keys()]:
                            orig = [k for k in db.keys() if k.lower() == u.lower()][0]
                            if db[orig] == hash_password(p):
                                st.session_state['auth'], st.session_state['user'] = True, orig
                                st.rerun()
                        st.error("Login Gagal")
            with t2:
                with st.form("r"):
                    nu, np = st.text_input("Username Baru"), st.text_input("Password Baru", type="password")
                    if st.form_submit_button("Daftar"):
                        db = get_json_cloud(USER_DB_PATH)
                        db[nu] = hash_password(np)
                        save_json_cloud(db, USER_DB_PATH)
                        st.success("Berhasil Daftar!")
        else:
            c1, c2 = st.columns([5,1])
            c1.info(f"User: **{st.session_state['user']}**")
            if c2.button("Log Out"): st.session_state['auth'] = False; st.rerun()
            
            st.divider()
            try:
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                files = res.get('resources', [])
                if files:
                    f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                    pilih = st.selectbox("Pilih Periode Laporan:", list(f_dict.keys()))
                    proses_dan_tampilkan_data(f_dict[pilih], st.session_state['user'])
                else: st.info("Admin belum mengunggah file.")
            except: st.error("Koneksi Server Gagal.")

    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            ad_p = st.text_input("Password Admin:", type="password")
            if st.button("Buka Panel"):
                if ad_p == "ic034": st.session_state['admin'] = True; st.rerun()
                else: st.error("Akses Ditolak")
        else:
            st.button("Keluar Admin", on_click=lambda: st.session_state.update({"admin": False}))
            t_up, t_us = st.tabs(["📤 Upload File", "👥 User Akun"])
            with t_up:
                up = st.file_uploader("Upload Excel", type=['xlsx'])
                if up and st.button("Simpan Laporan"):
                    cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                    st.success("File Terupload!"); time.sleep(1); st.rerun()
                st.divider()
                try:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                    for f in res.get('resources', []):
                        fn = f['public_id'].split('/')[-1]
                        c1, c2 = st.columns([4,1])
                        c1.write(f"📄 {fn}")
                        if c2.button("Hapus", key=f['public_id']):
                            cloudinary.api.delete_resources([f['public_id']], resource_type="raw"); st.rerun()
                except: pass
            with t_us:
                db_u = get_json_cloud(USER_DB_PATH)
                for un in list(db_u.keys()):
                    with st.expander(f"User: {un}"):
                        if st.button(f"Hapus {un}", key="h_"+un):
                            del db_u[un]; save_json_cloud(db_u, USER_DB_PATH); st.rerun()

if __name__ == "__main__":
    main()
