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
        /* Styling Kotak Saldo */
        [data-testid="stMetricValue"] { font-size: 28px !important; color: #007bff !important; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #007bff; }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI PEMBANTU (FORMATTING & AUTH) ---
def format_angka_indo(nilai):
    """Mengubah angka 1000000 menjadi string '1.000.000'"""
    try:
        # Gunakan format ribuan standar (1,000,000) lalu ganti koma menjadi titik
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

# --- 5. LOGIKA MONITORING DENGAN PEMISAH RIBUAN ---
def proses_dan_tampilkan_data(url, current_user, is_admin=False):
    try:
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
        df.columns = df.columns.str.strip()

        if 'User' not in df.columns:
            st.error("❌ Kolom 'User' tidak ditemukan!")
            return

        if is_admin:
            st.info("💡 Mode Admin: Menampilkan Seluruh Data")
            df_admin_display = df.copy()
            for col in df_admin_display.select_dtypes(include=['number']).columns:
                df_admin_display[col] = df_admin_display[col].apply(format_angka_indo)
            # Menghilangkan index untuk tampilan Admin
            st.dataframe(df_admin_display, use_container_width=True, hide_index=True)
        else:
            user_df = df[df['User'].astype(str).str.lower() == current_user.lower()].copy()

            if not user_df.empty:
                st.subheader(f"👋 Ringkasan Saldo: {current_user}")
                
                for col in user_df.columns:
                    if col != 'User':
                        user_df[col] = pd.to_numeric(user_df[col], errors='ignore')

                numeric_cols = user_df.select_dtypes(include=['number']).columns
                
                if not numeric_cols.empty:
                    cols_ui = st.columns(len(numeric_cols))
                    for i, col_name in enumerate(numeric_cols):
                        total_sum = user_df[col_name].sum()
                        with cols_ui[i]:
                            st.metric(label=f"Total {col_name}", value=format_angka_indo(total_sum))
                
                st.divider()
                
                # MEMPERCANTIK TABEL RINCIAN
                df_display = user_df.copy()
                for col in numeric_cols:
                    df_display[col] = df_display[col].apply(format_angka_indo)
                
                st.write("**Rincian Data:**")
                
                # GUNAKAN st.dataframe DENGAN hide_index=True
                st.dataframe(df_display, use_container_width=True, hide_index=True)
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
            tab_in, tab_reg = st.tabs(["Login", "Daftar"])
            with tab_in:
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
                        st.error("Gagal Login")
            with tab_reg:
                with st.form("r"):
                    nu, np = st.text_input("Username"), st.text_input("Password", type="password")
                    if st.form_submit_button("Daftar"):
                        db = get_json_cloud(USER_DB_PATH)
                        db[nu] = hash_password(np)
                        save_json_cloud(db, USER_DB_PATH)
                        st.success("Berhasil!")
        else:
            c1, c2 = st.columns([5,1])
            c2.button("Keluar", on_click=lambda: st.session_state.update({"auth": False}))
            
            try:
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"{MONITORING_FOLDER}/")
                files = res.get('resources', [])
                if files:
                    f_dict = {f['public_id'].split('/')[-1]: f['secure_url'] for f in files}
                    pilih = st.selectbox("Pilih Periode:", list(f_dict.keys()))
                    proses_dan_tampilkan_data(f_dict[pilih], st.session_state['user'])
                else: st.info("Tidak ada data.")
            except: st.info("Gagal memuat file.")

    elif menu == "🔐 Admin Panel":
        if not st.session_state['admin']:
            ad_p = st.text_input("Pass:", type="password")
            if st.button("Masuk"):
                if ad_p == "ic034": st.session_state['admin'] = True; st.rerun()
        else:
            st.button("Tutup", on_click=lambda: st.session_state.update({"admin": False}))
            up = st.file_uploader("Upload Excel", type=['xlsx'])
            if up and st.button("Simpan"):
                cloudinary.uploader.upload(up, resource_type="raw", public_id=f"{MONITORING_FOLDER}/{up.name}", overwrite=True)
                st.success("Terupload"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
