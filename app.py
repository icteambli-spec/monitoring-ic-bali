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

# =================================================================
# 2. CSS CUSTOM UNTUK BACKGROUND IMAGE & DARK MODE TWEAKS
# =================================================================
def add_custom_css():
    st.markdown(
        f"""
        <style>
        /* Mengatur Background Utama */
        .stApp {{
            background: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), 
                        url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* Membuat Form & Input lebih kontras (Glassmorphism) */
        .stTextInput input, .stSelectbox div, .stTextArea textarea {{
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }}
        
        /* Mengatur warna teks agar tetap terbaca */
        h1, h2, h3, p, span, label {{
            color: white !important;
            text-shadow: 1px 1px 2px black;
        }}

        /* Tabel data editor agar tetap jelas */
        div[data-testid="stDataEditor"] {{
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 10px;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

add_custom_css()

# Database Path
USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
LOG_DB = "pareto_nkl/config/access_pareto_nkllogs.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"

# =================================================================
# 3. FUNGSI CORE (DATABASE & DATA)
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
        
        # Tambahkan baris ini untuk membersihkan nama kolom dari spasi liar
        df.columns = [str(c).strip() for c in df.columns] 
        return df
    except: return None

# =================================================================
# 4. ROUTING & STATE
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "LOGIN"
if 'user_nik' not in st.session_state: st.session_state.user_nik = ""

# --- HALAMAN LOGIN ---
if st.session_state.page == "LOGIN":
    st.title("📊 Pareto NKL System")
    st.subheader("Monitoring & Input Penjelasan Pareto")
    
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Masuk", type="primary", use_container_width=True):
            db = load_json_db(USER_DB)
            if l_nik in db and db[l_nik] == l_pw:
                st.session_state.user_nik = l_nik
                record_log(l_nik)
                st.session_state.page = "USER_INPUT"
                st.rerun()
            else:
                st.error("NIK atau Password Salah!")
    
    with col2:
        with st.popover("📝 Daftar Akun Baru", use_container_width=True):
            st.subheader("Form Pendaftaran")
            new_nik = st.text_input("Masukkan NIK Baru:", max_chars=10)
            new_pw = st.text_input("Buat Password:", type="password")
            confirm_pw = st.text_input("Konfirmasi Password:", type="password")
            
            if st.button("Kirim Pendaftaran"):
                if not new_nik or not new_pw:
                    st.warning("NIK dan Password tidak boleh kosong!")
                elif new_pw != confirm_pw:
                    st.error("Konfirmasi password tidak cocok!")
                else:
                    db = load_json_db(USER_DB)
                    if new_nik in db:
                        st.error("NIK sudah terdaftar!")
                    else:
                        db[new_nik] = new_pw
                        save_json_db(USER_DB, db)
                        st.success(f"✅ Akun NIK {new_nik} berhasil dibuat! Silakan Login.")

    st.write("---")
    if st.button("🛡️ Admin Panel", use_container_width=True):
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
        f_master = st.file_uploader("Upload Excel", type=["xlsx"])
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
        list_toko = sorted(df_m['TOKO'].unique())
        selected_toko = st.selectbox("PILIH TOKO:", list_toko)
        data_toko = df_m[df_m['TOKO'] == selected_toko].copy()
        
        st.info(f"Menampilkan {len(data_toko)} item Pareto untuk toko {selected_toko}")
        
        # Cari nama kolom asli yang mengandung kata kunci tertentu
    c_rp = next((c for c in data_toko.columns if 'rp' in c.lower()), 'RP JUAL')
    c_desc = next((c for c in data_toko.columns if 'desc' in c.lower()), 'DESC')

    edited_df = st.data_editor(   
        data_toko,
        column_config={
        "PENJELASAN": st.column_config.TextColumn("PENJELASAN"),
        c_rp: st.column_config.NumberColumn("RP JUAL", format="Rp %d", disabled=True),
        c_desc: st.column_config.TextColumn("DESC", disabled=True),
        # Pastikan kolom lain yang tidak ingin ditampilkan atau diatur tetap aman
        },
        hide_index=True, 
        use_container_width=True
        )
          
        if st.button("🚀 Simpan Penjelasan", type="primary", use_container_width=True):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as w: edited_df.to_excel(w, index=False)
            p_id = f"pareto_nkl/hasil/Hasil_{selected_toko}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True)
            st.success("✅ Data berhasil disimpan ke cloud!")
    else:
        st.warning("⚠️ File Master belum diupload oleh Admin.")

    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()
