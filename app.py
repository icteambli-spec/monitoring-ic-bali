import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import json
import time
from datetime import datetime

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

# CSS Custom untuk tema gelap & teks putih
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label { color: white !important; text-shadow: 1px 1px 2px black; }
    div[data-testid="stDataEditor"] { background-color: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"

# =================================================================
# 2. FUNGSI CORE & CLEANING
# =================================================================
def clean_numeric(val):
    """Konversi format (262,200) ke float agar tidak error APIException"""
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
        df.columns = [str(c).strip() for c in df.columns]
        for col in ['QTY', 'RP JUAL']:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)
        if 'PRDCD' in df.columns:
            df['PRDCD'] = df['PRDCD'].astype(str)
        return df, v
    except: return None, "0"

def get_existing_result(toko_code, version):
    """Mengambil data yang sudah pernah disimpan agar tidak kosong lagi"""
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return pd.read_excel(io.BytesIO(resp.content))
    except: pass
    return None

# =================================================================
# 3. ROUTING & LOGIN
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "LOGIN"

if st.session_state.page == "LOGIN":
    st.title("📊 Pareto NKL System")
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    if st.button("Masuk", type="primary", use_container_width=True):
        try:
            url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}"
            db = requests.get(url_user).json()
            if l_nik in db and db[l_nik] == l_pw:
                st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"
                st.rerun()
            else: st.error("NIK/Password Salah!")
        except: st.error("Database user tidak dapat diakses.")
    if st.button("🛡️ Admin Panel", use_container_width=True):
        st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw = st.text_input("Admin Password:", type="password")
    if st.button("Masuk Admin"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Password Admin Salah!")
    if st.button("Kembali"): st.session_state.page = "LOGIN"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (MONITORING & REKAP)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Dashboard Admin")
    df_m_check, v_aktif = get_master_data()
    
    tab1, tab2 = st.tabs(["📊 Monitoring Progres", "📤 Upload Master"])
    
    with tab1:
        st.subheader(f"Versi Master Aktif: {v_aktif}")
        target_v = st.text_input("Cek Progres Versi:", value=v_aktif)
        
        if st.button("🔍 Cek & Gabungkan Data"):
            with st.spinner("Memindai file di cloud..."):
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
                all_f = res.get('resources', [])
                filtered = [f for f in all_f if f"v{target_v}" in f['public_id']]
                
                if not filtered:
                    st.warning("Belum ada toko yang mengisi untuk versi ini.")
                else:
                    monitor_list = []
                    combined_dfs = []
                    for f in filtered:
                        toko_id = f['public_id'].split('_')[1]
                        monitor_list.append({"Kode Toko": toko_id, "Waktu Simpan": f['created_at'], "ID File": f['public_id']})
                        combined_dfs.append(pd.read_excel(requests.get(f['secure_url']).url))
                    
                    st.success(f"Ditemukan {len(monitor_list)} toko.")
                    st.dataframe(pd.DataFrame(monitor_list), use_container_width=True)
                    
                    # Gabung Data
                    final_df = pd.concat(combined_dfs, ignore_index=True).drop_duplicates(subset=['TOKO', 'PRDCD'], keep='last')
                    out = io.BytesIO()
                    with pd.ExcelWriter(out) as w: final_df.to_excel(w, index=False)
                    st.download_button("📥 Download Rekap Gabungan", out.getvalue(), f"Rekap_V{target_v}.xlsx", use_container_width=True)

    with tab2:
        f_up = st.file_uploader("Upload Excel Master Baru", type=["xlsx"])
        if f_up and st.button("🚀 Publish & Update Versi"):
            cloudinary.uploader.upload(f_up, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("Master Berhasil Diperbarui!"); st.cache_data.clear(); time.sleep(1); st.rerun()
            
    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()

# =================================================================
# 5. USER INPUT (PERSISTENCE & ANTI-ERROR)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m, v_master = get_master_data()
    
    if df_m is not None:
        list_toko = sorted(df_m['TOKO'].unique())
        selected_toko = st.selectbox("PILIH TOKO:", list_toko)
        
        # LOGIKA PERSISTENCE: Cek apakah sudah ada hasil sebelumnya
        existing_df = get_existing_result(selected_toko, v_master)
        
        if existing_df is not None:
            data_toko = existing_df.copy()
            st.success(f"Memuat data tersimpan (V{v_master}). Anda bisa melanjutkan pengisian.")
        else:
            data_toko = df_m[df_m['TOKO'] == selected_toko].copy().reset_index(drop=True)
            st.info("Menampilkan data baru dari Master.")

        if "PENJELASAN" not in data_toko.columns: data_toko["PENJELASAN"] = ""

        # Konfigurasi Editor (QTY & RP JUAL dipaksa Number agar tidak error)
        config = {
            "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
            "RP JUAL": st.column_config.NumberColumn("RP JUAL", format="%.0f", disabled=True),
            "PENJELASAN": st.column_config.TextColumn("PENJELASAN", required=True),
            "PRDCD": st.column_config.TextColumn("PRDCD", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "TOKO": st.column_config.Column(disabled=True),
            "AM": st.column_config.Column(disabled=True)
        }

        # Key unik: gabungan toko + versi + jumlah baris untuk kestabilan widget
        edited_df = st.data_editor(
            data_toko,
            column_config=config,
            hide_index=True,
            use_container_width=True,
            key=f"ed_{selected_toko}_{v_master}_{len(data_toko)}"
        )
        
        if st.button("🚀 Simpan Penjelasan", type="primary", use_container_width=True):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                edited_df.to_excel(w, index=False)
            
            p_id = f"pareto_nkl/hasil/Hasil_{selected_toko}_v{v_master}.xlsx"
            with st.spinner("Menyimpan..."):
                cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success("✅ Berhasil Disimpan! Data tidak akan hilang saat Anda kembali.")
                time.sleep(1); st.rerun()
    
    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()
