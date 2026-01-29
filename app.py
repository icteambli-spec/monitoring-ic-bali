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

# Database Path
USER_DB = "pareto_nkl/config/users.json"
LOG_DB = "pareto_nkl/config/access_logs.json"
MASTER_PATH = "pareto_nkl/master_pareto.xlsx"

# =================================================================
# 2. FUNGSI CORE (DATABASE & DATA)
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

def record_log(nik):
    db_logs = load_json_db(LOG_DB)
    now = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    if nik not in db_logs: db_logs[nik] = []
    db_logs[nik].append(now)
    save_json_db(LOG_DB, db_logs)

@st.cache_data(ttl=60)
def get_master_data():
    try:
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw")
        url = res['secure_url']
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content))
        return df
    except: return None

# =================================================================
# 3. ROUTING & STATE
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "LOGIN"
if 'user_nik' not in st.session_state: st.session_state.user_nik = ""

# --- HALAMAN LOGIN ---
if st.session_state.page == "LOGIN":
    st.header("🔑 Login Sistem Pareto")
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    
    col1, col2 = st.columns(2)
    if col1.button("Masuk", type="primary", use_container_width=True):
        db = load_json_db(USER_DB)
        if l_nik in db and db[l_nik] == l_pw:
            st.session_state.user_nik = l_nik
            record_log(l_nik)
            st.session_state.page = "USER_INPUT"
            st.rerun()
        else: st.error("NIK atau Password Salah!")
    
    if col2.button("🛡️ Admin Panel", use_container_width=True):
        st.session_state.page = "ADMIN_AUTH"
        st.rerun()

# --- HALAMAN ADMIN AUTH ---
elif st.session_state.page == "ADMIN_AUTH":
    st.header("🛡️ Admin Authorization")
    adm_pw = st.text_input("Admin Password:", type="password")
    if st.button("Login Admin"):
        if adm_pw == "icnkl034":
            st.session_state.page = "ADMIN_PANEL"
            st.rerun()
        else: st.error("Akses Ditolak!")
    if st.button("⬅️ Kembali"): st.session_state.page = "LOGIN"; st.rerun()

# --- HALAMAN ADMIN PANEL ---
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Dashboard Admin")
    t1, t2, t3 = st.tabs(["📤 Upload Master", "📊 Log Akses", "🔐 Reset Password"])

    with t1:
        st.subheader("Update Master Pareto")
        f_master = st.file_uploader("Upload Excel (Format: TOKO, AM, PRDCD, DESC, QTY, RP JUAL, PENJELASAN)", type=["xlsx"])
        if f_master and st.button("Publish Master Baru"):
            cloudinary.uploader.upload(f_master, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("✅ Master Berhasil Diperbarui!"); st.cache_data.clear()

    with t2:
        st.subheader("Log Aktivitas User")
        logs = load_json_db(LOG_DB)
        if logs:
            flat_logs = [{"NIK": k, "Waktu Akses": t} for k, v in logs.items() for t in v]
            st.dataframe(pd.DataFrame(flat_logs).sort_values("Waktu Akses", ascending=False), use_container_width=True)

    with t3:
        st.subheader("Reset Password User")
        r_nik = st.text_input("Masukkan NIK:")
        r_pw = st.text_input("Password Baru:", type="password")
        if st.button("Simpan Password"):
            db = load_json_db(USER_DB)
            db[r_nik] = r_pw
            save_json_db(USER_DB, db)
            st.success(f"✅ Password NIK {r_nik} berhasil direset.")
            
    if st.button("🚪 Keluar Admin"): st.session_state.page = "LOGIN"; st.rerun()

# --- HALAMAN USER INPUT ---
elif st.session_state.page == "USER_INPUT":
    st.title(f"📋 Input Penjelasan Pareto ({st.session_state.user_nik})")
    df_m = get_master_data()
    
    if df_m is not None:
        # Filter Toko dari Master
        list_toko = sorted(df_m['TOKO'].unique())
        selected_toko = st.selectbox("PILIH TOKO:", list_toko)
        
        # Filter data berdasarkan toko
        data_toko = df_m[df_m['TOKO'] == selected_toko].copy()
        
        st.info(f"Menampilkan {len(data_toko)} item Pareto untuk toko {selected_toko}")
        
        edited_df = st.data_editor(
            data_toko,
            column_config={
                "PENJELASAN": st.column_config.TextColumn("PENJELASAN (Alfanumerik)", help="Wajib diisi"),
                "TOKO": None, # Sembunyikan karena sudah difilter
                "AM": st.column_config.TextColumn("AM", disabled=True),
                "PRDCD": st.column_config.TextColumn("PRDCD", disabled=True),
                "DESC": st.column_config.TextColumn("DESC", disabled=True),
                "QTY": st.column_config.NumberColumn("QTY", disabled=True),
                "RP JUAL": st.column_config.NumberColumn("RP JUAL", format="Rp %d", disabled=True),
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("🚀 Simpan Penjelasan", type="primary", use_container_width=True):
            # Logika simpan hasil per toko
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as w: edited_df.to_excel(w, index=False)
            p_id = f"pareto_nkl/hasil/Hasil_{selected_toko}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True)
            st.success("✅ Data berhasil disimpan ke cloud!")
    else:
        st.warning("⚠️ File Master belum diupload oleh Admin.")

    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()
