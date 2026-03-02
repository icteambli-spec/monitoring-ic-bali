import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import json
import time
import hashlib
from datetime import datetime, timedelta

# =================================================================
# 1. KONFIGURASI GLOBAL & CLOUDINARY
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

USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"
MT_CONFIG = "pareto_nkl/config/maintenance_config.json"
# PERMINTAAN 4: Link gambar maintenance (Silakan ganti link ini)
MAINTENANCE_IMAGE = "https://res.cloudinary.com/dydpottpm/image/upload/v1772461285/Bugs_Bunny_In_Prison_GIF_-_Prison_Jail_Bugs_Bunny_Prison_-_Discover_Share_GIFs_pq0pez.gif"

# =================================================================
# 2. FUNGSI CORE, MAINTENANCE & PENGUATAN LOGIN
# =================================================================

def get_maintenance_status():
    """PERMINTAAN 4: Cek status maintenance dari Cloudinary"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{MT_CONFIG}?t={int(time.time())}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("maintenance", False)
    except:
        return False
    return False

def set_maintenance_status(status):
    """PERMINTAAN 4: Set status maintenance oleh Admin"""
    try:
        config = {"maintenance": status, "updated_at": str(datetime.now())}
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(config).encode()), 
            resource_type="raw", public_id=MT_CONFIG, overwrite=True, invalidate=True
        )
        return True
    except:
        return False

def clear_all_caches():
    """Fungsi Skrip Inti: Bersihkan seluruh cache memori"""
    st.cache_data.clear()
    keys_to_delete = [k for k in st.session_state.keys() if any(x in k for x in ['ed_', 'result', 'data_toko', 'hash', 'user_db'])]
    for key in keys_to_delete:
        del st.session_state[key]

def get_user_db_safe():
    """PERMINTAAN 2: Penguatan Login dengan Retry 5x dan Session Cache"""
    if 'persistent_user_db' in st.session_state:
        return st.session_state.persistent_user_db
    
    url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
    for i in range(5):
        try:
            resp = requests.get(url_user, timeout=15)
            if resp.status_code == 200:
                db = resp.json()
                st.session_state.persistent_user_db = db
                return db
        except:
            time.sleep(1)
    return None

def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    s = str(val).replace(',', '').replace(' ', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try:
        return float(s)
    except: return 0.0

@st.cache_data(ttl=2) 
def get_master_data():
    try:
        v = datetime.now().strftime("%m-%Y") 
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", invalidate=True)
        url_master = f"{res['secure_url']}?t={int(time.time())}"
        resp = requests.get(url_master)
        df = pd.read_excel(io.BytesIO(resp.content))
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # PERMINTAAN 1: Pastikan kolom baru terformat numerik
        numeric_target = ['QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']
        for col in df.columns:
            if col in numeric_target:
                df[col] = df[col].apply(clean_numeric)
            else:
                df[col] = df[col].fillna("")
        
        if 'KETERANGAN' in df.columns:
            df['KETERANGAN'] = ""
        return df, v
    except: 
        return pd.DataFrame(), datetime.now().strftime("%m-%Y")

def get_existing_result(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}?t={int(time.time())}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            df_res = pd.read_excel(io.BytesIO(resp.content))
            df_res.columns = [str(c).strip().upper() for c in df_res.columns]
            return df_res
        return None
    except: return None

def validate_file_exists_in_cloudinary(toko_code, version):
    """Fungsi Skrip Inti: Pengecekan fisik file agar tidak ghosting"""
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        cloudinary.api.resource(p_id, resource_type="raw")
        return True
    except: return False

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(new_db).encode()), 
            resource_type="raw", public_id=USER_DB, overwrite=True, invalidate=True
        )
        st.session_state.persistent_user_db = new_db
        return True
    except: return False

def get_progress_data(df_m, version):
    if df_m.empty: return pd.DataFrame(), []
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/", max_results=500)
        files = res.get('resources', [])
        finished_stores = []
        suffix = f"_v{version}.xlsx"
        for f in files:
            p_id = f['public_id'].split('/')[-1]
            if p_id.endswith(suffix):
                finished_stores.append(p_id.replace("Hasil_", "").replace(suffix, ""))
        
        df_unique = df_m.drop_duplicates(subset=['KDTOKO']).copy()
        df_unique['STATUS'] = df_unique['KDTOKO'].apply(lambda x: 1 if x in finished_stores else 0)
        return df_unique, finished_stores
    except: return pd.DataFrame(), []

# Custom CSS Glassmorphism (Skrip Inti)
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label, .stTabs [data-baseweb="tab"] { color: white !important; text-shadow: 1px 1px 2px black; }
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { background-color: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; }
    [data-testid="stMetric"] { background-color: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }
    .nk-label { background-color: rgba(255, 75, 75, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .nl-label { background-color: rgba(46, 204, 113, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #2ecc71; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. ROUTING & MAINTENANCE LOGIC (PERMINTAAN 4)
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

# Check Maintenance Mode secara Real-time
is_mt_active = get_maintenance_status()

if is_mt_active and st.session_state.page not in ["ADMIN_AUTH", "ADMIN_PANEL"]:
    st.image(MAINTENANCE_IMAGE, use_container_width=True)
    st.error("### 🛠️ Mohon Maaf, Web sedang Maintenance")
    st.info("Sistem sedang dalam perbaikan berkala. Harap hubungi Admin atau coba lagi nanti.")
    if st.button("🛡️ Admin Login"): 
        st.session_state.page = "ADMIN_AUTH"
        st.rerun()
    st.stop()

# --- HALAMAN HOME (FUNGSI PENUH SKRIP INTI) ---
if st.session_state.page == "HOME":
    st.title("📑 Sistem Penjelasan Pareto NKL")
    df_m_prog, v_prog = get_master_data()
    if not df_m_prog.empty:
        df_u, finished_list = get_progress_data(df_m_prog, v_prog)
        
        total_t, sudah_t = len(df_u), df_u['STATUS'].sum()
        persen_t = (sudah_t / total_t) if total_t > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Toko", total_t)
        c2.metric("Sudah SO", sudah_t, f"{persen_t:.1%}")
        c3.metric("Belum SO", total_t - sudah_t, delta_color="inverse")
        
        st.write("---")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("### 📊 Progres SO PER AM (Urutan Terendah)")
            am_sum = df_u.groupby('AM').agg(Target=('KDTOKO', 'count'), Selesai=('STATUS', 'sum')).reset_index()
            am_sum['Belum'] = am_sum['Target'] - am_sum['Selesai']
            am_sum['Progres_Val'] = (am_sum['Selesai'] / am_sum['Target']).round(2)
            st.dataframe(am_sum.sort_values('Progres_Val'), column_config={"Progres_Val": st.column_config.ProgressColumn("Progres", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)
        with col_b:
            st.write("### 📊 Progres SO PER AS (Urutan Terendah)")
            as_sum = df_u.groupby('AS').agg(Target=('KDTOKO', 'count'), Selesai=('STATUS', 'sum')).reset_index()
            as_sum['Belum'] = as_sum['Target'] - as_sum['Selesai']
            as_sum['Progres_Val'] = (as_sum['Selesai'] / as_sum['Target']).round(2)
            st.dataframe(as_sum.sort_values('Progres_Val'), column_config={"Progres_Val": st.column_config.ProgressColumn("Progres", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        with st.expander("🔍 Detail Toko Belum SO (AM/AS)"):
            df_belum = df_u[df_u['STATUS'] == 0][['AM', 'AS', 'KDTOKO', 'NAMA TOKO']].sort_values(['AM', 'AS'])
            st.dataframe(df_belum, hide_index=True, use_container_width=True)

    st.write("---")
    tab_login, tab_daftar = st.tabs(["🔐 Masuk", "📝 Daftar Akun"])
    with tab_login:
        l_nik = st.text_input("NIK:", max_chars=10, key="l_nik")
        l_pw = st.text_input("Password:", type="password", key="l_pw")
        if st.button("LOG IN", type="primary", use_container_width=True):
            db = get_user_db_safe()
            if db and l_nik in db and db[l_nik] == l_pw:
                st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"; st.rerun()
            else: st.error("NIK/Password salah atau Koneksi DB terputus.")
        st.markdown(f'<a href="https://wa.me/6287725860048" target="_blank" style="text-decoration:none;"><button style="width:100%; background:transparent; color:white; border:1px solid white; border-radius:5px; cursor:pointer; padding:5px;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)
    
    with tab_daftar:
        d_nik = st.text_input("NIK Baru:", max_chars=10, key="d_nik")
        d_pw = st.text_input("Password Baru:", type="password", key="d_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="d_cpw")
        if st.button("DAFTAR", use_container_width=True):
            if d_nik and d_pw == d_cpw:
                db_reg = get_user_db_safe()
                if db_reg and d_nik in db_reg: st.warning("NIK sudah ada.")
                else:
                    db_reg[d_nik] = d_pw
                    if update_user_db(db_reg): st.success("Akun berhasil dibuat! Silakan Login.")
            else: st.error("Data tidak valid atau password tidak cocok.")
    
    if st.button("🛡️ Admin Login", use_container_width=True): st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw_adm = st.text_input("Password Admin:", type="password")
    if st.button("Masuk Admin"):
        if pw_adm == "icnkl034": st.cache_data.clear(); st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Password Admin Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (FULL LOGIC: PERMINTAAN 3 & 5)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    tab_rek, tab_mas, tab_usr, tab_res = st.tabs(["📊 Rekap", "📤 Master", "👤 Kelola User", "🔥 Reset & MT"])
    
    with tab_rek:
        df_m_rek, v_aktif_rek = get_master_data()
        # PERMINTAAN 3: Input Periode Rekap
        st.info(f"Seri Data Saat Ini: {v_aktif_rek}")
        target_v = st.text_input("Pilih Periode Rekap (MM-YYYY):", value=v_aktif_rek)
        
        if st.button("📥 Download Gabungan Item Minus (Full Toko)", use_container_width=True):
            with st.spinner("Menggabungkan data..."):
                res_cloud = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                filtered_f = [f for f in res_cloud.get('resources', []) if f"v{target_v}" in f['public_id']]
                
                combined_in = pd.DataFrame(columns=['KDTOKO', 'PRDCD', 'KETERANGAN'])
                if filtered_f:
                    inputs_list = []
                    for f in filtered_f:
                        try:
                            df_t = pd.read_excel(f"{f['secure_url']}?t={int(time.time())}")
                            df_t.columns = [str(c).upper().strip() for c in df_t.columns]
                            inputs_list.append(df_t[['KDTOKO', 'PRDCD', 'KETERANGAN']])
                        except: pass
                    if inputs_list: combined_in = pd.concat(inputs_list, ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PRDCD'])
                
                # PERMINTAAN 5: Rekap Full Toko, hanya item Minus (RP SO NOW < 0)
                if not df_m_rek.empty:
                    df_minus_master = df_m_rek[df_m_rek['RP SO NOW'] < 0].copy()
                    m_cols = list(df_minus_master.columns)
                    
                    df_m_mrg = df_minus_master.drop(columns=['KETERANGAN']) if 'KETERANGAN' in df_minus_master.columns else df_minus_master.copy()
                    final_rekap = df_m_mrg.merge(combined_in, on=['KDTOKO', 'PRDCD'], how='left').fillna("")
                    final_rekap = final_rekap[m_cols if 'KETERANGAN' in m_cols else m_cols + ['KETERANGAN']]
                    
                    out_rek = io.BytesIO()
                    with pd.ExcelWriter(out_rek) as w: final_rekap.to_excel(w, index=False)
                    st.success(f"Rekap {target_v} siap diunduh.")
                    st.download_button("📥 Klik Download File Excel", out_rek.getvalue(), f"Full_Rekap_Minus_{target_v}.xlsx")
                else: st.error("Data Master tidak ditemukan.")

    with tab_mas:
        master_status = False
        try:
            cloudinary.api.resource(MASTER_PATH, resource_type="raw")
            master_status = True
        except: pass

        f_up = st.file_uploader("Upload Master Baru (.xlsx)", type=["xlsx"])
        if f_up and st.button("🚀 Update Master"):
            with st.spinner("Sinkronisasi Master..."):
                old_df_m, _ = get_master_data()
                new_df_m = pd.read_excel(f_up)
                new_df_m.columns = [str(c).strip().upper() for c in new_df_m.columns]
                
                # Incremental Update (Sinkronisasi PLU/PRDCD)
                final_m = pd.concat([old_df_m, new_df_m], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PRDCD'], keep='last')
                if 'KETERANGAN' in final_m.columns: final_m['KETERANGAN'] = ""
                
                buf_m = io.BytesIO()
                with pd.ExcelWriter(buf_m) as w: final_m.to_excel(w, index=False)
                cloudinary.uploader.upload(buf_m.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
                
                # Keterangan Sukses Dinamis
                if master_status: st.success("✅ Master sukses diperbarui")
                else: st.success("✅ Master baru berhasil diupload")
                st.cache_data.clear(); time.sleep(1); st.rerun()

    with tab_usr:
        st.subheader("Reset Password User")
        nik_tgt = st.text_input("Ketik NIK User:"); db_adm = get_user_db_safe()
        if nik_tgt and db_adm and nik_tgt in db_adm:
            st.success(f"Akun {nik_tgt} aktif.")
            p_new = st.text_input("Password Baru:", type="password")
            if st.button("Update Password"):
                db_adm[nik_tgt] = p_new
                if update_user_db(db_adm): st.success("Berhasil diubah!"); time.sleep(1); st.rerun()

    with tab_res:
        # PERMINTAAN 4: Toggle Maintenance Mode Terotomasi
        st.subheader("🛠️ Panel Maintenance")
        current_mt = get_maintenance_status()
        if current_mt:
            st.warning("Status: SEDANG MAINTENANCE (Terkunci)")
            if st.button("🔴 MATIKAN MAINTENANCE SEKARANG"):
                if set_maintenance_status(False): st.success("Web Dibuka!"); time.sleep(1); st.rerun()
        else:
            st.success("Status: ONLINE (Terbuka)")
            if st.button("🟢 AKTIFKAN MAINTENANCE SEKARANG"):
                if set_maintenance_status(True): st.success("Web Dikunci!"); time.sleep(1); st.rerun()
        
        st.divider()
        st.subheader("🔥 Pembersihan Total")
        if st.button("HAPUS SELURUH HASIL INPUT USER", type="primary"):
            res_del = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
            pids = [f['public_id'] for f in res_del.get('resources', [])]
            if pids: cloudinary.api.delete_resources(pids, resource_type="raw")
            st.cache_data.clear(); st.success("Hasil input dibersihkan!"); time.sleep(1); st.rerun()

    if st.button("Keluar Admin"): 
        st.cache_data.clear()
        st.session_state.page = "HOME"
        st.rerun()

# =================================================================
# 5. USER INPUT (NK/NL, REFRESH, ANIMASI & KOLOM BARU)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m_in, v_m_in = get_master_data()
    if not df_m_in.empty:
        s_am = st.selectbox("1. PILIH AM:", sorted(df_m_in['AM'].unique()))
        df_am = df_m_in[df_m_in['AM'] == s_am]
        s_toko = st.selectbox("2. PILIH NAMA TOKO:", sorted(df_am['NAMA TOKO'].unique()))
        df_sel = df_am[df_am['NAMA TOKO'] == s_toko]
        
        v_kd, v_as = str(df_sel['KDTOKO'].iloc[0]), str(df_sel['AS'].iloc[0])
        
        # Header dengan Tombol Refresh (Skrip Inti)
        ch1, ch2, ch3 = st.columns([2, 2, 1])
        ch1.metric("KDTOKO:", v_kd)
        ch2.metric("AS:", v_as)
        with ch3:
            if st.button("🔄 Refresh Data"): 
                clear_all_caches(); st.rerun()

        # Sinkronisasi Real-time (Skrip Inti)
        data_final = df_sel.copy()
        data_final['PRDCD'] = data_final['PRDCD'].astype(str).str.strip()
        
        existing_res = get_existing_result(v_kd, v_m_in)
        if existing_res is not None:
            if validate_file_exists_in_cloudinary(v_kd, v_m_in):
                cloud_dat = existing_res[['PRDCD', 'KETERANGAN']].copy()
                cloud_dat['PRDCD'] = cloud_dat['PRDCD'].astype(str).str.strip()
                if 'KETERANGAN' in data_final.columns: data_final = data_final.drop(columns=['KETERANGAN'])
                data_final = data_final.merge(cloud_dat.drop_duplicates(subset=['PRDCD']), on='PRDCD', how='left')
                st.success(f"✅ Sinkronisasi Isian Lama v{v_m_in} Berhasil.")
        else:
            data_final['KETERANGAN'] = ""

        # Formatting Angka Ribuan & Tipe Data (PERMINTAAN 1)
        data_final['KETERANGAN'] = data_final['KETERANGAN'].fillna("").astype(str).replace(['nan','NaN','None'], '')
        so_cols = ['QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']
        for c in so_cols: 
            data_final[c] = pd.to_numeric(data_final[c], errors='coerce').fillna(0)

        # PEMISAHAN NK & NL BERDASARKAN RP SO NOW
        df_nk = data_final[data_final['RP SO NOW'] < 0].copy()
        df_nl = data_final[data_final['RP SO NOW'] >= 0].copy()

        # Config Tampilan (Format Ribuan Indonesia)
        conf_view = {
            "PRDCD": st.column_config.TextColumn("PRDCD"),
            "DESC": st.column_config.TextColumn("DESC"),
            "QTY SO LALU": st.column_config.NumberColumn("QTY LALU", format="%,d"),
            "RP SO LALU": st.column_config.NumberColumn("RP LALU", format="%,d"),
            "QTY SO NOW": st.column_config.NumberColumn("QTY NOW", format="%,d"),
            "RP SO NOW": st.column_config.NumberColumn("RP NOW", format="%,d"),
        }

        # 1. Tabel Item NK (Minus) - BISA EDIT
        st.markdown('<div class="nk-label"><b>🟥 20 item minus (NK) terbesar harap isi keterangan!</b></div>', unsafe_allow_html=True)
        ed_nk = st.data_editor(
            df_nk[['PRDCD', 'DESC', 'QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW', 'KETERANGAN']], 
            column_config={**conf_view, "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True)}, 
            hide_index=True, use_container_width=True, key=f"ed_nk_{v_kd}"
        )

        # 2. Tabel Item NL (Plus) - PENAMPIL SAJA
        st.markdown('<div class="nl-label"><b>🟩 20 item plus terbesar (NL) hanya sebagai penampil saja!</b></div>', unsafe_allow_html=True)
        st.dataframe(df_nl[['PRDCD', 'DESC', 'QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']], 
                     column_config=conf_view, hide_index=True, use_container_width=True)

        if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
            if ed_nk['KETERANGAN'].apply(lambda x: str(x).strip() == "").any():
                st.error("⚠️ Mohon isi seluruh kolom keterangan pada tabel item minus (NK)!")
            else:
                with st.spinner("Menyimpan isian..."):
                    df_nk['KETERANGAN'] = ed_nk['KETERANGAN'].values
                    df_nl['KETERANGAN'] = "ini item nl!" # Otomasi Keterangan NL
                    
                    combined_final = pd.concat([df_nk, df_nl], ignore_index=True)
                    orig_master_cols = [c for c in df_m_in.columns if c != 'KETERANGAN']
                    
                    buf_s = io.BytesIO()
                    with pd.ExcelWriter(buf_s) as w: 
                        combined_final[orig_master_cols + ['KETERANGAN']].to_excel(w, index=False)
                    
                    p_save = f"pareto_nkl/hasil/Hasil_{v_kd}_v{v_m_in}.xlsx"
                    cloudinary.uploader.upload(buf_s.getvalue(), resource_type="raw", public_id=p_save, overwrite=True, invalidate=True)
                    
                    # ANIMASI BALLOONS & PESAN SUKSES 2 DETIK (PERMINTAAN 3)
                    st.balloons()
                    st.success("✅ Input keterangan sukses!")
                    time.sleep(2)
                    clear_all_caches()
                    st.rerun()

    if st.button("Log Out"): 
        clear_all_caches()
        st.session_state.page = "HOME"
        st.rerun()
