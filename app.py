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

# Custom CSS
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

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(io.BytesIO(json.dumps(new_db).encode()), resource_type="raw", public_id=USER_DB, overwrite=True, invalidate=True)
        return True
    except: return False

# =================================================================
# 3. ROUTING & HOME
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

if st.session_state.page == "HOME":
    st.title("📊 Pareto NKL System")
    tab_login, tab_daftar = st.tabs(["🔐 Masuk", "📝 Daftar Akun"])
    with tab_login:
        l_nik = st.text_input("NIK:", max_chars=10, key="l_nik")
        l_pw = st.text_input("Password:", type="password", key="l_pw")
        if st.button("LOG IN", type="primary", use_container_width=True):
            try:
                url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                db = requests.get(url_user).json()
                if l_nik in db and db[l_nik] == l_pw:
                    st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"
                    st.rerun()
                else: st.error("NIK/Password salah!")
            except: st.error("Database user error.")
        st.markdown(f'<a href="https://wa.me/6287725860048" target="_blank" style="text-decoration:none;"><button style="width:100%; background:transparent; color:white; border:1px solid white; border-radius:5px; cursor:pointer; padding:5px;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)
    with tab_daftar:
        d_nik = st.text_input("NIK Baru:", max_chars=10, key="d_nik")
        d_pw = st.text_input("Password Baru:", type="password", key="d_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="d_cpw")
        if st.button("DAFTAR", use_container_width=True):
            if d_nik and d_pw == d_cpw:
                url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
                db = requests.get(url_user).json()
                if d_nik in db: st.warning("NIK sudah ada.")
                else:
                    db[d_nik] = d_pw
                    if update_user_db(db): st.success("Pendaftaran Berhasil!")
            else: st.error("Data tidak valid.")
    if st.button("🛡️ Admin Login", use_container_width=True): st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw = st.text_input("Password Admin:", type="password")
    if st.button("Masuk Admin"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (DENGAN RESET PASSWORD)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    tab_rek, tab_mas, tab_usr, tab_res = st.tabs(["📊 Rekap", "📤 Master", "👤 Kelola User", "🔥 Reset"])
    
    with tab_rek:
        df_m_check, v_aktif = get_master_data()
        target_v = st.text_input("Versi Rekap:", value=v_aktif)
        if st.button("Gabung Data", use_container_width=True):
            res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
            filtered = [f for f in res.get('resources', []) if f"v{target_v}" in f['public_id']]
            if filtered:
                combined = [pd.read_excel(requests.get(f['secure_url']).url) for f in filtered]
                final_df = pd.concat(combined, ignore_index=True)
                out = io.BytesIO()
                with pd.ExcelWriter(out) as w: final_df.to_excel(w, index=False)
                st.download_button("📥 Download Rekap", out.getvalue(), f"Rekap_V{target_v}.xlsx")

    with tab_mas:
        f_up = st.file_uploader("Upload Data Toko Tambahan", type=["xlsx"])
        if f_up and st.button("🚀 Update Master"):
            old_df, _ = get_master_data()
            new_df = pd.read_excel(f_up)
            new_df.columns = [str(c).strip().upper() for c in new_df.columns]
            final_master = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PLU'], keep='last')
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as w: final_master.to_excel(w, index=False)
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("Master diperbarui!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    with tab_usr:
        st.subheader("Reset Password User")
        try:
            url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
            db_u = requests.get(url_user).json()
            nik_pilihan = st.selectbox("Pilih NIK User:", options=list(db_u.keys()))
            pass_baru = st.text_input("Password Baru:", type="password")
            if st.button("Update Password"):
                if pass_baru:
                    db_u[nik_pilihan] = pass_baru
                    if update_user_db(db_u): st.success(f"Password NIK {nik_pilihan} berhasil diupdate!")
                else: st.warning("Isi password!")
        except: st.error("Gagal muat user.")

    with tab_res:
        konfirmasi = st.text_input("Ketik 'KONFIRMASI' untuk reset:")
        if st.button("🔥 RESET GLOBAL", type="primary"):
            if konfirmasi == "KONFIRMASI":
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                p_ids = [f['public_id'] for f in res.get('resources', [])]
                if p_ids: cloudinary.api.delete_resources(p_ids, resource_type="raw")
                st.success("Dibersihkan!"); time.sleep(1); st.rerun()

    if st.button("Logout Admin"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 5. USER INPUT (SINKRONISASI KOLOM)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Pareto")
    df_m, v_master = get_master_data()
    if df_m is not None:
        list_am = sorted(df_m['AM'].astype(str).str.upper().unique())
        sel_am = st.selectbox("1. PILIH AM:", list_am)
        df_f_am = df_m[df_m['AM'].astype(str).str.upper() == sel_am]
        list_nama_toko = sorted(df_f_am['NAMA TOKO'].astype(str).str.upper().unique())
        sel_nama_toko = st.selectbox("2. PILIH NAMA TOKO:", list_nama_toko)
        df_selected = df_f_am[df_f_am['NAMA TOKO'].astype(str).str.upper() == sel_nama_toko]
        val_kdtoko, val_as = str(df_selected['KDTOKO'].iloc[0]), str(df_selected['AS'].iloc[0])
        
        c1, c2 = st.columns(2)
        c1.metric("KDTOKO:", val_kdtoko); c2.metric("AS:", val_as)

        existing_df = get_existing_result(val_kdtoko, v_master)
        if existing_df is not None:
            data_toko = existing_df.copy()
            st.success("Memuat data tersimpan.")
        else:
            data_toko = df_selected.copy()
            if 'KETERANGAN' not in data_toko.columns: data_toko['KETERANGAN'] = ""

        # SINKRONISASI: Pastikan kolom Master + KETERANGAN ada di urutan yang benar
        original_cols = list(df_m.columns)
        if 'KETERANGAN' not in original_cols: 
            save_cols_order = original_cols + ['KETERANGAN']
        else:
            save_cols_order = original_cols

        disp_cols = ['PLU', 'DESC', 'QTY', 'RUPIAH', 'KETERANGAN']
        config = {
            "PLU": st.column_config.TextColumn("PLU", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
            "RUPIAH": st.column_config.NumberColumn("RUPIAH", format="%.0f", disabled=True),
            "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True),
        }
        
        edited_df = st.data_editor(data_toko[disp_cols], column_config=config, hide_index=True, use_container_width=True, key=f"ed_{val_kdtoko}")
        
        if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
            if edited_df['KETERANGAN'].apply(lambda x: str(x).strip() == "").any():
                st.error("⚠️ Semua kolom KETERANGAN wajib diisi!")
            else:
                # PROSES SINKRONISASI KOLOM:
                # Update kolom KETERANGAN pada data_toko (yang membawa semua kolom master)
                data_toko['KETERANGAN'] = edited_df['KETERANGAN'].values
                
                # Paksa urutan kolom agar sesuai format Master (KETERANGAN di akhir)
                final_save_df = data_toko[save_cols_order]
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf) as w: final_save_df.to_excel(w, index=False)
                p_id = f"pareto_nkl/hasil/Hasil_{val_kdtoko}_v{v_master}.xlsx"
                cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success("✅ Tersimpan!"); time.sleep(3); st.rerun()

    if st.button("Logout"): st.session_state.page = "HOME"; st.rerun()
