import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import json
from datetime import datetime, timedelta

# =================================================================
# 1. KONFIGURASI & CLOUDINARY
# =================================================================
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Secrets Cloudinary tidak ditemukan!")

st.set_page_config(page_title="Pareto NKL System", layout="wide")

# Tambahkan Background Sesuai Tema
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-position: center; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label { color: white !important; text-shadow: 1px 1px 2px black; }
    div[data-testid="stDataEditor"] { background-color: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Path Database
USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
LOG_DB = "pareto_nkl/config/access_pareto_nkllogs.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"

# =================================================================
# 2. FUNGSI CORE
# =================================================================
def load_json_db(path):
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{path}"
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except: return {}

def save_json_db(path, db_dict):
    json_data = json.dumps(db_dict)
    cloudinary.uploader.upload(io.BytesIO(json_data.encode()), resource_type="raw", public_id=path, overwrite=True, invalidate=True)

@st.cache_data(ttl=30)
def get_master_data():
    try:
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", cache_control="no-cache")
        resp = requests.get(res['secure_url'])
        df = pd.read_excel(io.BytesIO(resp.content))
        # Membersihkan nama kolom dan memastikan data terbaca dengan benar
        df.columns = [str(c).strip() for c in df.columns]
        # Mengubah kolom numerik menjadi string/angka bersih untuk mencegah error tipe data
        df['PRDCD'] = df['PRDCD'].astype(str)
        return df
    except: return None

# =================================================================
# 3. ROUTING
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "LOGIN"

if st.session_state.page == "LOGIN":
    st.title("📊 Pareto NKL System")
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    if st.button("Masuk", type="primary", use_container_width=True):
        db = load_json_db(USER_DB)
        if l_nik in db and db[l_nik] == l_pw:
            st.session_state.user_nik = l_nik
            st.session_state.page = "USER_INPUT"; st.rerun()
        else: st.error("Login Gagal!")
    if st.button("🛡️ Admin Panel", use_container_width=True):
        st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw = st.text_input("Admin Password:", type="password")
    if st.button("Masuk Admin"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "LOGIN"; st.rerun()

elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    f = st.file_uploader("Upload Master Baru", type=["xlsx"])
    if f and st.button("Publish Master"):
        cloudinary.uploader.upload(f, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
        st.success("Berhasil!"); st.cache_data.clear()
    if st.button("Logout"): st.session_state.page = "LOGIN"; st.rerun()

# =================================================================
# 4. USER INPUT (FIXED ERROR)
# =================================================================
@st.cache_data(ttl=30)
def get_master_data():
    try:
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", cache_control="no-cache")
        resp = requests.get(res['secure_url'])
        df = pd.read_excel(io.BytesIO(resp.content))
        
        # 1. Bersihkan nama kolom
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Pembersihan data agar tidak memicu APIException
        for col in df.columns:
            # Pastikan semua data terbaca sebagai string/angka standar, hilangkan NaN
            df[col] = df[col].fillna("")
            
        # Paksa PRDCD tetap string agar tidak berubah jadi format scientific (e.g. 1.00E+07)
        if 'PRDCD' in df.columns:
            df['PRDCD'] = df['PRDCD'].astype(str)
            
        return df
    except: return None

# --- HALAMAN USER INPUT ---
 elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m = get_master_data()
    
    if df_m is not None:
        list_toko = sorted(df_m['TOKO'].unique())
        selected_toko = st.selectbox("PILIH TOKO:", list_toko)
        
        # Filter data dan reset index agar state widget tetap stabil
        data_toko = df_m[df_m['TOKO'] == selected_toko].copy().reset_index(drop=True)
        
        if not data_toko.empty:
            st.info(f"Menampilkan {len(data_toko)} item untuk toko {selected_toko}")
            
            # 3. Konfigurasi Kolom yang 'Safe' (Menggunakan format teks untuk data akuntansi)
            config = {
                "TOKO": st.column_config.Column(disabled=True),
                "AM": st.column_config.Column(disabled=True),
                "PRDCD": st.column_config.TextColumn("PRDCD", disabled=True),
                "DESC": st.column_config.TextColumn("DESC", disabled=True),
                "QTY": st.column_config.TextColumn("QTY", disabled=True), # Gunakan Text agar format (angka) aman
                "RP JUAL": st.column_config.TextColumn("RP JUAL", disabled=True), # Gunakan Text agar format (angka) aman
                "PENJELASAN": st.column_config.TextColumn("PENJELASAN", required=True)
            }

            # 4. Gunakan key unik yang menyertakan jumlah baris agar widget ter-reset sempurna
            edited_df = st.data_editor(
                data_toko,
                column_config=config,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{selected_toko}_{len(data_toko)}" 
            )
            
            if st.button("🚀 Simpan Penjelasan", type="primary", use_container_width=True):
                buf = io.BytesIO()
                with pd.ExcelWriter(buf) as w:
                    edited_df.to_excel(w, index=False)
                
                p_id = f"pareto_nkl/hasil/Hasil_{selected_toko}.xlsx"
                with st.spinner("Menyimpan..."):
                    cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True)
                    st.success(f"✅ Data {selected_toko} Berhasil Disimpan!")
        else:
            st.warning("Data tidak tersedia.")
    else:
        st.error("Gagal memuat Master.")
