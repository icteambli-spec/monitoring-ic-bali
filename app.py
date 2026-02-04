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

# Custom CSS Glassmorphism & Font Styling
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label { color: white !important; text-shadow: 1px 1px 2px black; }
    div[data-testid="stDataEditor"] { background-color: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255,255,255,0.1); border-radius: 10px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: white !important; }
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
# 3. ROUTING & LOGIN / REGISTER (HOME)
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

if st.session_state.page == "HOME":
    st.title("📊 Pareto NKL System")
    
    tab_login, tab_daftar = st.tabs(["🔐 Masuk (Login)", "📝 Daftar Akun Baru"])
    
    with tab_login:
        l_nik = st.text_input("NIK:", max_chars=10, key="login_nik")
        l_pw = st.text_input("Password:", type="password", key="login_pw")
        if st.button("Masuk Sekarang", type="primary", use_container_width=True):
            try:
                url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                db = requests.get(url_user).json()
                if l_nik in db and db[l_nik] == l_pw:
                    st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"
                    st.rerun()
                else: st.error("NIK atau Password Salah!")
            except: st.error("Gagal terhubung ke database user.")
        
        # Link Lupa Password (WhatsApp)
        st.markdown("---")
        wa_link = "https://wa.me/6287725860048?text=Halo%20Admin%2C%20saya%20lupa%20password%20Pareto%20NKL%20dengan%20NIK%3A%20"
        st.markdown(f'<a href="{wa_link}" target="_blank" style="text-decoration: none;"><button style="width: 100%; background-color: transparent; color: white; border: 1px solid white; border-radius: 5px; padding: 5px; cursor: pointer;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)

    with tab_daftar:
        d_nik = st.text_input("NIK Baru (10 Digit):", max_chars=10, key="reg_nik")
        d_pw = st.text_input("Buat Password:", type="password", key="reg_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="reg_cpw")
        
        if st.button("Daftar Akun", type="primary", use_container_width=True):
            if d_nik and d_pw:
                if d_pw == d_cpw:
                    try:
                        url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                        db = requests.get(url_user).json()
                        if d_nik in db:
                            st.warning("NIK ini sudah terdaftar. Silakan login.")
                        else:
                            db[d_nik] = d_pw
                            if update_user_db(db):
                                st.success("✅ Pendaftaran Berhasil! Silakan Masuk di tab sebelah.")
                                time.sleep(1)
                            else: st.error("Gagal menyimpan data ke cloud.")
                    except: st.error("Gagal memproses pendaftaran.")
                else: st.error("Konfirmasi password tidak cocok!")
            else: st.warning("NIK dan Password wajib diisi!")

    st.write("")
    if st.button("🛡️ Admin Panel Login", use_container_width=True):
        st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    st.subheader("🛡️ Verifikasi Administrator")
    pw = st.text_input("Admin Password:", type="password")
    if st.button("Masuk Admin", type="primary"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Password Admin Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (REKAP & MASTER)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Dashboard Admin")
    tab1, tab2 = st.tabs(["📊 Monitoring & Rekap", "📤 Update Master Excel"])
    
    with tab1:
        df_m_check, v_aktif = get_master_data()
        st.subheader(f"Versi Master Saat Ini: {v_aktif}")
        target_v = st.text_input("Pilih Versi Data untuk Rekap:", value=v_aktif)
        
        if st.button("🔍 Tarik Data & Gabungkan", use_container_width=True):
            with st.spinner("Mengunduh data toko..."):
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
                filtered = [f for f in res.get('resources', []) if f"v{target_v}" in f['public_id']]
                if filtered:
                    combined_list = []
                    for f in filtered:
                        resp = requests.get(f['secure_url'])
                        combined_list.append(pd.read_excel(io.BytesIO(resp.content)))
                    
                    final_df = pd.concat(combined_list, ignore_index=True)
                    out = io.BytesIO()
                    with pd.ExcelWriter(out) as w: final_df.to_excel(w, index=False)
                    st.success(f"Ditemukan data dari {len(filtered)} toko.")
                    st.download_button("📥 Download File Rekap", out.getvalue(), f"Rekap_V{target_v}.xlsx", use_container_width=True)
                else: st.warning("Tidak ada data toko yang masuk untuk versi ini.")

    with tab2:
        f_up = st.file_uploader("Upload Excel Master Baru", type=["xlsx"])
        if f_up and st.button("🚀 Publish Master Baru"):
            cloudinary.uploader.upload(f_up, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("Master Terupdate! Cache dibersihkan."); st.cache_data.clear(); time.sleep(1); st.rerun()

    if st.button("🚪 Logout Admin", use_container_width=True): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 5. USER INPUT (TIERED FILTERS & COLUMN LOCK)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Penjelasan Pareto NKL")
    df_m, v_master = get_master_data()
    
    if df_m is not None:
        # Filter Bertingkat
        list_am = sorted(df_m['AM'].unique())
        sel_am = st.selectbox("1. PILIH AM:", list_am)
        
        df_f_am = df_m[df_m['AM'] == sel_am]
        list_toko = sorted(df_f_am['KDTOKO'].unique())
        sel_toko = st.selectbox("2. PILIH KDTOKO:", list_toko)
        
        # Label AS otomatis
        info_as = df_f_am[df_f_am['KDTOKO'] == sel_toko]['AS'].iloc[0]
        st.markdown(f'<div style="background-color:rgba(255,255,255,0.1); padding:10px; border-radius:5px;"><b>3. AS (Area Supervisor):</b> {info_as}</div>', unsafe_allow_html=True)
        st.write("")

        # Cek Data Cloud
        existing_df = get_existing_result(sel_toko, v_master)
        if existing_df is not None:
            data_toko = existing_df.copy()
            st.success("Memuat data tersimpan.")
        else:
            data_toko = df_f_am[df_f_am['KDTOKO'] == sel_toko].copy()
            if 'KETERANGAN' not in data_toko.columns: data_toko['KETERANGAN'] = ""
            st.info("Data baru siap diinput.")

        # Konfigurasi Tampilan Kolom (Sesuai Gambar User)
        display_cols = ['PLU', 'DESC', 'QTY', 'RUPIAH', 'KETERANGAN']
        
        # Lock Kolom Master
        config = {
            "PLU": st.column_config.TextColumn("PLU", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
            "RUPIAH": st.column_config.NumberColumn("RUPIAH", format="%.0f", disabled=True),
            "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Alpha-Numerik)", required=True),
        }

        # Data Editor
        edited_df = st.data_editor(
            data_toko[display_cols],
            column_config=config,
            hide_index=True,
            use_container_width=True,
            key=f"editor_{sel_toko}_{v_master}"
        )
        
        if st.button("🚀 Simpan Data ke Cloud", type="primary", use_container_width=True):
            # Validasi Wajib Isi
            kosong = edited_df['KETERANGAN'].apply(lambda x: str(x).strip() == "").any()
            
            if kosong:
                st.error("⚠️ GAGAL SIMPAN! Semua baris kolom KETERANGAN harus diisi penjelasan.")
            else:
                # Gabung kembali dengan kolom tersembunyi (NO, KDTOKO, AM, AS)
                for col in data_toko.columns:
                    if col not in display_cols:
                        edited_df[col] = data_toko[col].values
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    edited_df.to_excel(w, index=False)
                
                p_id = f"pareto_nkl/hasil/Hasil_{sel_toko}_v{v_master}.xlsx"
                with st.spinner("Mengunggah..."):
                    cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success("✅ Data berhasil disimpan secara permanen!")
                    time.sleep(1); st.rerun()
    
    st.write("---")
    if st.button("🚪 Keluar (Logout)", use_container_width=True): st.session_state.page = "HOME"; st.rerun()
