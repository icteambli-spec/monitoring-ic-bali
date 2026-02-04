import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import json
import time
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

# Custom CSS untuk tampilan Background & Tabel
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label, .stTabs [data-baseweb="tab"] { 
        color: white !important; 
        text-shadow: 1px 1px 2px black; 
    }
    div[data-testid="stDataEditor"] { 
        background-color: rgba(255,255,255,0.05); 
        border-radius: 10px; padding: 10px; 
    }
    .stTabs [data-baseweb="tab-list"] {
        background-color: rgba(255,255,255,0.1);
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"

# =================================================================
# 2. FUNGSI CORE
# =================================================================
def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    s = str(val).replace(',', '').replace(' ', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try:
        return float(s)
    except: return 0.0

@st.cache_data(ttl=30)
def get_master_data():
    try:
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", cache_control="no-cache")
        v = str(res.get('version', '1'))
        resp = requests.get(res['secure_url'])
        df = pd.read_excel(io.BytesIO(resp.content))
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            if col in ['QTY', 'RUPIAH']:
                df[col] = df[col].apply(clean_numeric)
            else:
                df[col] = df[col].fillna("")
        return df, v
    except: return None, "0"

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(new_db).encode()),
            resource_type="raw",
            public_id=USER_DB,
            overwrite=True,
            invalidate=True
        )
        return True
    except: return False

def get_existing_result(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            df_res = pd.read_excel(io.BytesIO(resp.content))
            df_res.columns = [str(c).strip().upper() for c in df_res.columns]
            return df_res
    except: pass
    return None

# =================================================================
# 3. HALAMAN HOME (LOGIN & DAFTAR)
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

if st.session_state.page == "HOME":
    st.title("📊 Pareto NKL System")
    
    # MENU DAFTAR TERSEDIA DI SINI (TABS)
    tab_login, tab_daftar = st.tabs(["🔐 Masuk (Login)", "📝 Daftar Akun"])
    
    with tab_login:
        l_nik = st.text_input("NIK Anda:", max_chars=10, key="l_nik")
        l_pw = st.text_input("Password:", type="password", key="l_pw")
        if st.button("LOG IN", type="primary", use_container_width=True):
            try:
                url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                db = requests.get(url_user).json()
                if l_nik in db and db[l_nik] == l_pw:
                    st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"
                    st.rerun()
                else: st.error("NIK atau Password salah!")
            except: st.error("Gagal memuat database user.")
        
        # Tombol Lupa Password WhatsApp
        wa_api = "https://wa.me/6287725860048?text=Halo%20Admin%2C%20saya%20lupa%20password%20Pareto%20NKL%20NIK%3A%20"
        st.markdown(f'<a href="{wa_api}" target="_blank" style="text-decoration:none;"><button style="width:100%; padding:8px; border:1px solid white; background:transparent; color:white; border-radius:5px; cursor:pointer;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)

    with tab_daftar:
        st.subheader("Registrasi Mandiri")
        d_nik = st.text_input("Masukkan NIK Baru:", max_chars=10, key="d_nik")
        d_pw = st.text_input("Buat Password:", type="password", key="d_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="d_cpw")
        
        if st.button("DAFTAR SEKARANG", use_container_width=True):
            if d_nik and d_pw:
                if d_pw == d_cpw:
                    try:
                        url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                        db = requests.get(url_user).json()
                        if d_nik in db:
                            st.warning("NIK sudah terdaftar!")
                        else:
                            db[d_nik] = d_pw
                            if update_user_db(db):
                                st.success("✅ Akun berhasil dibuat! Silakan pindah ke Tab Masuk.")
                            else: st.error("Gagal menyimpan ke Cloud.")
                    except: st.error("Error database.")
                else: st.error("Password tidak cocok!")
            else: st.warning("Data harus lengkap!")

    st.write("")
    if st.button("🛡️ Admin Login", use_container_width=True):
        st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    st.subheader("🛡️ Verifikasi Admin")
    pw = st.text_input("Password Admin:", type="password")
    if st.button("Login Admin", type="primary"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Dashboard Admin")
    tab_rek, tab_mas = st.tabs(["📊 Monitoring Rekap", "📤 Master Update"])
    
    with tab_rek:
        df_m_check, v_aktif = get_master_data()
        st.write(f"Versi Aktif: {v_aktif}")
        target_v = st.text_input("Tarik Versi:", value=v_aktif)
        if st.button("Gabungkan Data Toko", use_container_width=True):
            res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
            filtered = [f for f in res.get('resources', []) if f"v{target_v}" in f['public_id']]
            if filtered:
                combined = [pd.read_excel(requests.get(f['secure_url']).url) for f in filtered]
                final_df = pd.concat(combined, ignore_index=True)
                out = io.BytesIO()
                with pd.ExcelWriter(out) as w: final_df.to_excel(w, index=False)
                st.download_button("📥 Download Rekap", out.getvalue(), f"Rekap_V{target_v}.xlsx")
            else: st.warning("Data kosong.")

    with tab_mas:
        f_up = st.file_uploader("Upload Excel Master", type=["xlsx"])
        if f_up and st.button("🚀 Publish Master Baru"):
            cloudinary.uploader.upload(f_up, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("Berhasil!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    if st.button("Logout Admin"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 5. USER INPUT (TIERED FILTER & COLUMN LOCK)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m, v_master = get_master_data()
    
    if df_m is not None:
        # Dropdown AM
        list_am = sorted(df_m['AM'].unique())
        sel_am = st.selectbox("1. PILIH AM:", list_am)
        
        # Dropdown KDTOKO berdasarkan AM
        df_f_am = df_m[df_m['AM'] == sel_am]
        list_toko = sorted(df_f_am['KDTOKO'].unique())
        sel_toko = st.selectbox("2. PILIH KDTOKO:", list_toko)
        
        # Label AS (Read Only)
        info_as = df_f_am[df_f_am['KDTOKO'] == sel_toko]['AS'].iloc[0]
        st.info(f"3. AS (Area Supervisor): {info_as}")

        # Cek Data Existing
        existing_df = get_existing_result(sel_toko, v_master)
        if existing_df is not None:
            data_toko = existing_df.copy()
            st.success("Memuat data tersimpan.")
        else:
            data_toko = df_f_am[df_f_am['KDTOKO'] == sel_toko].copy()
            if 'KETERANGAN' not in data_toko.columns: data_toko['KETERANGAN'] = ""

        # Sembunyikan kolom sistem, tampilkan hanya PLU, DESC, QTY, RUPIAH, KETERANGAN
        disp_cols = ['PLU', 'DESC', 'QTY', 'RUPIAH', 'KETERANGAN']
        
        # Konfigurasi: Semua kolom master di-lock (disabled: True)
        config = {
            "PLU": st.column_config.TextColumn("PLU", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
            "RUPIAH": st.column_config.NumberColumn("RUPIAH", format="%.0f", disabled=True),
            "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True),
        }

        # Editor Tabel
        edited_df = st.data_editor(
            data_toko[disp_cols],
            column_config=config,
            hide_index=True,
            use_container_width=True,
            key=f"ed_{sel_toko}"
        )
        
        if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
            # Cek jika ada baris KETERANGAN yang masih kosong
            is_empty = edited_df['KETERANGAN'].apply(lambda x: str(x).strip() == "").any()
            
            if is_empty:
                st.error("⚠️ GAGAL: Seluruh baris kolom KETERANGAN wajib diisi penjelasan!")
            else:
                # Gabungkan data inputan dengan kolom master yang tadi disembunyikan
                for col in data_toko.columns:
                    if col not in disp_cols:
                        edited_df[col] = data_toko[col].values
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf) as w: edited_df.to_excel(w, index=False)
                
                p_id = f"pareto_nkl/hasil/Hasil_{sel_toko}_v{v_master}.xlsx"
                with st.spinner("Menyimpan..."):
                    cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success("✅ Data berhasil tersimpan di cloud!")
                    time.sleep(1); st.rerun()
    
    if st.button("Logout"): st.session_state.page = "HOME"; st.rerun()
