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
st.set_page_config(page_title="IC Bali Monitoring", layout="wide", page_icon="🏢")

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

# --- 3. CSS CUSTOM ---
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden; display: none !important;}
        footer {visibility: hidden; display: none;}
        .main .block-container {padding-top: 1rem; padding-bottom: 1rem;}
        div[data-baseweb="input"] input { color: #000 !important; background-color: #fff !important; }
        [data-testid="stMetricValue"] { font-size: 26px !important; color: #007bff !important; font-weight: bold; }
        .stMetric { 
            background-color: #ffffff; padding: 15px; border-radius: 10px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-left: 5px solid #007bff; 
        }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI PEMBANTU ---
def format_angka_indo(nilai):
    try:
        if pd.isna(nilai) or nilai == "": return "0"
        return "{:,.0f}".format(float(nilai)).replace(",", ".")
    except: return str(nilai)

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

# --- 5. LOGIKA DATA (FILTER AM/AS & KODE TOKO) ---
def proses_tabel_user(url, current_user):
    try:
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
        df.columns = df.columns.astype(str).str.strip()

        # Validasi Kolom
        req_cols = ['AM', 'AS', 'Sisa Saldo ITB', 'Kode Toko']
        missing = [c for c in req_cols if c not in df.columns]
        if missing:
            st.error(f"Kolom berikut tidak ditemukan di Excel: {', '.join(missing)}")
            return

        # 1. FILTER BERDASARKAN AM ATAU AS (Case Insensitive)
        user_lower = current_user.lower()
        mask = (df['AM'].astype(str).str.lower() == user_lower) | \
               (df['AS'].astype(str).str.lower() == user_lower)
        
        user_df = df[mask].copy()

        if not user_df.empty:
            # 2. RESUME / METRIC (SUM)
            user_df['Sisa Saldo ITB'] = pd.to_numeric(user_df['Sisa Saldo ITB'], errors='coerce').fillna(0)
            total_saldo = user_df['Sisa Saldo ITB'].sum()
            
            st.subheader(f"👋 Ringkasan Data: {current_user}")
            c_met, c_fil = st.columns([1, 2])
            with c_met:
                st.metric(label="Total Sisa Saldo ITB", value=format_angka_indo(total_saldo))
            
            # 3. FILTER TAMBAHAN: KODE TOKO
            with c_fil:
                list_toko = sorted(user_df['Kode Toko'].unique().tolist())
                pilih_toko = st.multiselect("🔍 Filter Kode Toko:", options=list_toko, placeholder="Pilih satu atau lebih toko...")

            # Apply Filter Toko jika ada yang dipilih
            if pilih_toko:
                display_df = user_df[user_df['Kode Toko'].isin(pilih_toko)].copy()
            else:
                display_df = user_df.copy()

            st.write("---")
            # 4. TAMPILKAN TABEL RINCIAN
            # Format ribuan untuk kolom saldo di tabel
            display_df_formatted = display_df.copy()
            display_df_formatted['Sisa Saldo ITB'] = display_df_formatted['Sisa Saldo ITB'].apply(format_angka_indo)
            
            auto_cfg = {c: st.column_config.Column(width="auto") for c in display_df_formatted.columns}
            st.dataframe(display_df_formatted, use_container_width=True, hide_index=True, column_config=auto_cfg)
        else:
            st.warning(f"Data untuk user '{current_user}' tidak ditemukan pada kolom AM atau AS.")
    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengolah data: {e}")

# --- 6. MAIN APP ---
def main():
    init_cloudinary()
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if 'admin_auth' not in st.session_state: st.session_state['admin_auth'] = False

    st.title("📊 Monitoring IC Bali")
    nav = st.radio("Menu:", ["Monitoring User", "🔐 Admin Panel"], horizontal=True, label_visibility="collapsed")
    st.write("---")

    if nav == "Monitoring User":
        if not st.session_state['auth']:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                t1, t2 = st.tabs(["Login", "Daftar Akun"])
                with t1:
                    with st.form("l"):
                        u = st.text_input("Username").strip()
                        p = st.text_input("Password", type="password")
                        if st.form_submit_button("Masuk", use_container_width=True):
                            db = get_json_cloud(USER_DB_PATH)
                            if u.lower() in [k.lower() for k in db.keys()]:
                                orig = [k for k in db.keys() if k.lower() == u.lower()][0]
                                if db[orig] == hash_password(p):
                                    st.session_state['auth'], st.session_state['user'] = True, orig
                                    st.rerun()
                            st.error("Username/Password Salah")
                with t2:
                    with st.form("r"):
                        nu, np = st.text_input("Username Baru"), st.text_input("Password Baru", type="password")
                        if st.form_submit_button("Daftar Akun", use_container_width=True):
                            db = get_json_cloud(USER_DB_PATH)
                            db[nu] = hash_password(np)
                            save_json_cloud(db, USER_DB_PATH)
                            st.success("Berhasil! Silakan Login.")
        else:
            h1, h2 = st.columns([5, 1])
            h1.subheader(f"User: {st.session_state['user']}")
            if h2.button("Log Out", type="primary"): 
                st.session_state['auth'] = False; st.rerun()
            
            try:
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                files = res.get('resources', [])
                if files:
                    f_map = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                    pilih = st.selectbox("Pilih Periode Laporan:", list(f_map.keys()))
                    proses_tabel_user(f_map[pilih], st.session_state['user'])
                else: st.info("Laporan belum tersedia.")
            except: st.error("Gagal terhubung ke Cloudinary.")

    elif nav == "🔐 Admin Panel":
        if not st.session_state['admin_auth']:
            c1, c2, c3 = st.columns([1, 1, 1])
            with c2:
                ap = st.text_input("Password Admin:", type="password")
                if st.button("Buka Panel", use_container_width=True):
                    if ap == "ic034": st.session_state['admin_auth'] = True; st.rerun()
                    else: st.error("Akses Ditolak")
        else:
            if st.button("Tutup Admin"): st.session_state['admin_auth'] = False; st.rerun()
            t_f, t_u = st.tabs(["📂 File Manager", "👥 User Manager"])
            with t_f:
                up = st.file_uploader("Upload Excel", type=['xlsx'])
                if up and st.button("Upload"):
                    cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                    st.success("Tersimpan!"); time.sleep(1); st.rerun()
                st.divider()
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                for f in res.get('resources', []):
                    fn = f['public_id'].split('/')[-1]
                    ca, cb = st.columns([4, 1])
                    ca.write(fn)
                    if cb.button("Hapus", key=f['public_id']):
                        cloudinary.api.delete_resources([f['public_id']], resource_type="raw"); st.rerun()
            with t_u:
                db_u = get_json_cloud(USER_DB_PATH)
                st.write(f"Total User: {len(db_u)}")
                for u in list(db_u.keys()):
                    if st.button(f"Hapus User: {u}"):
                        del db_u[u]; save_json_cloud(db_u, USER_DB_PATH); st.rerun()

if __name__ == "__main__":
    main()
