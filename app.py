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

# Custom CSS untuk Glassmorphism & Teks Putih
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
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"

# =================================================================
# 2. FUNGSI CORE & PEMBERSIHAN DATA
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

def clean_numeric(val):
    """Mengonversi format akuntansi (262,200) menjadi float standar"""
    if pd.isna(val) or val == "": return 0.0
    s = str(val).replace(',', '').replace(' ', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try:
        return float(s)
    except:
        return 0.0

@st.cache_data(ttl=30)
def get_master_data():
    try:
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", cache_control="no-cache")
        version = str(res.get('version', '1'))
        resp = requests.get(res['secure_url'])
        df = pd.read_excel(io.BytesIO(resp.content))
        df.columns = [str(c).strip() for c in df.columns]
        
        # Pembersihan data untuk mencegah APIException
        for col in df.columns:
            if col in ['QTY', 'RP JUAL']:
                df[col] = df[col].apply(clean_numeric)
            else:
                df[col] = df[col].fillna("")
                
        if 'PRDCD' in df.columns:
            df['PRDCD'] = df['PRDCD'].astype(str)
            
        return df, version
    except: return None, "0"

# =================================================================
# 3. ROUTING & LOGIN
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "LOGIN"

if st.session_state.page == "LOGIN":
    st.title("📊 Pareto NKL System")
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Masuk", type="primary", use_container_width=True):
            db = load_json_db(USER_DB)
            if l_nik in db and db[l_nik] == l_pw:
                st.session_state.user_nik = l_nik
                st.session_state.page = "USER_INPUT"; st.rerun()
            else: st.error("NIK atau Password Salah!")
    with col2:
        if st.button("🛡️ Admin Panel", use_container_width=True):
            st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw = st.text_input("Admin Password:", type="password")
    if st.button("Buka Panel Admin"):
        if pw == "icnkl034": st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "LOGIN"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (DENGAN MONITORING & GABUNG VERSI)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Dashboard Admin")
    df_master_check, v_aktif = get_master_data()
    
    tab1, tab2 = st.tabs(["📊 Monitoring & Gabung Data", "📤 Upload & User"])
    
    with tab1:
        st.subheader(f"Status Input Versi Aktif: {v_aktif}")
        target_v = st.text_input("Masukkan Versi yang ingin ditarik:", value=v_aktif)
        
        if st.button("🔍 Cek Progres & Siapkan Data"):
            with st.spinner("Memindai cloud..."):
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
                all_files = res.get('resources', [])
                filtered = [f for f in all_files if f"v{target_v}" in f['public_id']]
                
                if not filtered:
                    st.warning(f"Belum ada data untuk versi {target_v}")
                else:
                    monitor_data = []
                    combined_list = []
                    for f in filtered:
                        parts = f['public_id'].split('_')
                        toko_id = parts[1] if len(parts) > 1 else "Unknown"
                        
                        resp = requests.get(f['secure_url'])
                        temp_df = pd.read_excel(io.BytesIO(resp.content))
                        combined_list.append(temp_df)
                        monitor_data.append({"Kode Toko": toko_id, "File": f['public_id']})
                    
                    st.success(f"Ditemukan {len(monitor_data)} toko.")
                    st.dataframe(pd.DataFrame(monitor_data), use_container_width=True, hide_index=True)
                    
                    final_df = pd.concat(combined_list, ignore_index=True)
                    final_df = final_df.drop_duplicates(subset=['TOKO', 'PRDCD'], keep='last')
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Download Rekap Gabungan (.xlsx)",
                        data=output.getvalue(),
                        file_name=f"Rekap_Pareto_V{target_v}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

    with tab2:
        f_up = st.file_uploader("Pilih Excel Master", type=["xlsx"])
        if f_up and st.button("🚀 Publish Master Baru"):
            cloudinary.uploader.upload(f_up, resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.success("Master Berhasil Diperbarui!"); st.cache_data.clear()
            
    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()

# =================================================================
# 5. USER INPUT
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m, v_master = get_master_data()
    
    if df_m is not None:
        list_toko = sorted(df_m['TOKO'].unique())
        selected_toko = st.selectbox("PILIH TOKO:", list_toko)
        data_toko = df_m[df_m['TOKO'] == selected_toko].copy().reset_index(drop=True)
        
        if not data_toko.empty:
            st.info(f"Toko: {selected_toko} | Versi Master: {v_master}")
            
            # Konfigurasi desimal agar stabil di data_editor
            config = {
                "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
                "RP JUAL": st.column_config.NumberColumn("RP JUAL", format="%.0f", disabled=True),
                "PENJELASAN": st.column_config.TextColumn("PENJELASAN", required=True),
                "PRDCD": st.column_config.TextColumn("PRDCD", disabled=True),
                "DESC": st.column_config.TextColumn("DESC", disabled=True)
            }

            edited_df = st.data_editor(
                data_toko,
                column_config=config,
                hide_index=True,
                use_container_width=True,
                key=f"ed_{selected_toko}_{v_master}_{len(data_toko)}" 
            )
            
            if st.button("🚀 Simpan Penjelasan", type="primary", use_container_width=True):
                buf = io.BytesIO()
                with pd.ExcelWriter(buf) as w:
                    edited_df.to_excel(w, index=False)
                
                tgl_save = datetime.now().strftime('%Y%m%d')
                p_id = f"pareto_nkl/hasil/Hasil_{selected_toko}_{tgl_save}_v{v_master}.xlsx"
                
                with st.spinner("Menyimpan..."):
                    cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success(f"✅ Tersimpan!")
        else: st.warning("Data tidak tersedia.")
    else: st.error("Gagal memuat Master.")

    if st.button("🚪 Logout"): st.session_state.page = "LOGIN"; st.rerun()
