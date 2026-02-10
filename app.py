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
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { 
        background-color: rgba(255,255,255,0.05); 
        border-radius: 10px; padding: 10px; 
    }
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.2);
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

@st.cache_data(ttl=2) 
def get_master_data():
    try:
        v = datetime.now().strftime("%m-%Y") 
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", cache_control="no-cache")
        url_master = f"{res['secure_url']}?t={int(time.time())}"
        resp = requests.get(url_master)
        df = pd.read_excel(io.BytesIO(resp.content))
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            if col in ['QTY', 'RUPIAH']:
                df[col] = df[col].apply(clean_numeric)
            else:
                df[col] = df[col].fillna("")
        return df, v
    except: return None, datetime.now().strftime("%m-%Y")

def get_existing_result(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}?t={int(time.time())}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            df_res = pd.read_excel(io.BytesIO(resp.content))
            df_res.columns = [str(c).strip().upper() for c in df_res.columns]
            return df_res
    except: pass
    return None

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(new_db).encode()), 
            resource_type="raw", public_id=USER_DB, overwrite=True, invalidate=True
        )
        return True
    except: return False

def get_progress_data(df_m, version):
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_", max_results=500)
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

# =================================================================
# 3. ROUTING & HOME
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

if st.session_state.page == "HOME":
    st.title("📑 Sistem Penjelasan Pareto NKL")
    
    df_m_prog, v_prog = get_master_data()
    if df_m_prog is not None:
        df_u, finished_list = get_progress_data(df_m_prog, v_prog)
        total_t, sudah_t = len(df_u), df_u['STATUS'].sum()
        belum_t = total_t - sudah_t
        persen_t = (sudah_t / total_t) if total_t > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Toko", total_t)
        c2.metric("Sudah Input", sudah_t, f"{persen_t:.1%}")
        c3.metric("Belum Input", belum_t, f"-{belum_t}", delta_color="inverse")
        
        st.write("---")
        st.write("### 📊 Progres Input PER AM (Urutan Terendah di Atas)")
        am_sum = df_u.groupby('AM').agg(Target_Toko=('KDTOKO', 'count'), Sudah_Input=('STATUS', 'sum')).reset_index()
        am_sum['Belum_Input'] = am_sum['Target_Toko'] - am_sum['Sudah_Input']
        am_sum['Progres_Val'] = (am_sum['Sudah_Input'] / am_sum['Target_Toko']).round(2)
        am_sum = am_sum.sort_values('Progres_Val')
        st.dataframe(am_sum, column_config={"AM": "AM", "Target_Toko": "Target Toko Input", "Sudah_Input": "Sudah Input", "Belum_Input": "Belum Input", "Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("### 📊 Progres Input PER AS (Urutan Terendah di Atas)")
        as_sum = df_u.groupby('AS').agg(Target_Toko=('KDTOKO', 'count'), Sudah_Input=('STATUS', 'sum')).reset_index()
        as_sum['Belum_Input'] = as_sum['Target_Toko'] - as_sum['Sudah_Input']
        as_sum['Progres_Val'] = (as_sum['Sudah_Input'] / as_sum['Target_Toko']).round(2)
        as_sum = as_sum.sort_values('Progres_Val')
        st.dataframe(as_sum, column_config={"AS": "AS", "Target_Toko": "Target Toko SO", "Sudah_Input": "Sudah Input", "Belum_Input": "Belum Input", "Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("---")
        df_belum_all = df_u[df_u['STATUS'] == 0].copy()
        with st.expander("🔍 Detail Toko Belum Input Per AM"):
            if not df_belum_all.empty:
                list_am_belum = sorted(df_belum_all['AM'].unique())
                sel_am_det = st.selectbox("Pilih AM:", options=list_am_belum, key="sel_am_det")
                df_det_am = df_belum_all[df_belum_all['AM'] == sel_am_det][['KDTOKO', 'NAMA TOKO']]
                df_det_am.columns = ['Kode', 'Nama']
                st.dataframe(df_det_am, hide_index=True, use_container_width=True)
        with st.expander("🔍 Detail Toko Belum Input Per AS"):
            if not df_belum_all.empty:
                list_as_belum = sorted(df_belum_all['AS'].unique())
                sel_as_det = st.selectbox("Pilih AS:", options=list_as_belum, key="sel_as_det")
                df_det_as = df_belum_all[df_belum_all['AS'] == sel_as_det][['KDTOKO', 'NAMA TOKO']]
                df_det_as.columns = ['Kode', 'Nama']
                st.dataframe(df_det_as, hide_index=True, use_container_width=True)

    st.write("---")
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
        if pw == "icnkl034": 
            st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    tab_rek, tab_mas, tab_usr, tab_res = st.tabs(["📊 Rekap", "📤 Master", "👤 Kelola User", "🔥 Reset"])
    
    with tab_rek:
        df_m, v_aktif = get_master_data()
        st.info(f"Seri Data Saat Ini: {v_aktif}")
        target_v = st.text_input("Tarik Data Seri (MM-YYYY):", value=v_aktif)
        if st.button("📥 Download Gabungan (Full Master)", use_container_width=True):
            with st.spinner("Menggabungkan data..."):
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/Hasil_")
                filtered = [f for f in res.get('resources', []) if f"v{target_v}" in f['public_id']]
                if filtered:
                    combined_list = []
                    for f in filtered:
                        try:
                            df_temp = pd.read_excel(f"{f['secure_url']}?t={int(time.time())}")
                            df_temp.columns = [str(c).upper().strip() for c in df_temp.columns]
                            combined_list.append(df_temp)
                        except: pass
                    if combined_list:
                        combined_input = pd.concat(combined_list, ignore_index=True)
                        cols_to_use = [c for c in ['KDTOKO', 'PLU', 'KETERANGAN'] if c in combined_input.columns]
                        input_data = combined_input[cols_to_use].copy().drop_duplicates(subset=['KDTOKO', 'PLU'])
                    else: input_data = pd.DataFrame(columns=['KDTOKO', 'PLU', 'KETERANGAN'])
                else: input_data = pd.DataFrame(columns=['KDTOKO', 'PLU', 'KETERANGAN'])
                master_cols_original = list(df_m.columns)
                df_m_for_merge = df_m.drop(columns=['KETERANGAN']) if 'KETERANGAN' in df_m.columns else df_m.copy()
                final_df = df_m_for_merge.merge(input_data, on=['KDTOKO', 'PLU'], how='left')
                if 'KETERANGAN' not in final_df.columns: final_df['KETERANGAN'] = ""
                final_df['KETERANGAN'] = final_df['KETERANGAN'].fillna("")
                final_columns_order = master_cols_original if 'KETERANGAN' in master_cols_original else master_cols_original + ['KETERANGAN']
                final_df = final_df[final_columns_order]
                out = io.BytesIO()
                with pd.ExcelWriter(out) as w: final_df.to_excel(w, index=False)
                st.download_button("📥 Klik Download File", out.getvalue(), f"Full_Rekap_{target_v}.xlsx")

    with tab_mas:
        f_up = st.file_uploader("Upload Data Toko Tambahan", type=["xlsx"])
        if f_up and st.button("🚀 Update Master"):
            old_df, _ = get_master_data()
            new_df = pd.read_excel(f_up)
            new_df.columns = [str(c).strip().upper() for c in new_df.columns]
            final_master = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PLU'], keep='last')
            if 'KETERANGAN' in final_master.columns: final_master['KETERANGAN'] = ""
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as w: final_master.to_excel(w, index=False)
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            st.cache_data.clear()
            st.success("Master diperbarui!"); time.sleep(1); st.rerun()

        st.divider()
        st.subheader("🗑️ Hapus Master Aktif")
        with st.container(border=True):
            opsi_hapus_hasil = st.checkbox("Ikut hapus seluruh hasil input user berjalan?", value=False)
            konfirmasi_del = st.text_input("Ketik 'HAPUS' untuk menghapus Master Aktif:")
            if st.button("🔥 Eksekusi Hapus Master", type="primary"):
                if konfirmasi_del == "HAPUS":
                    cloudinary.uploader.destroy(MASTER_PATH, resource_type="raw")
                    if opsi_hapus_hasil:
                        res_del = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                        p_ids = [f['public_id'] for f in res_del.get('resources', [])]
                        if p_ids: cloudinary.api.delete_resources(p_ids, resource_type="raw")
                    st.cache_data.clear()
                    st.success("Berhasil dihapus!"); time.sleep(1); st.rerun()

    with tab_usr:
        st.subheader("Reset Password User")
        url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
        try:
            db_u = requests.get(url_user).json()
            nik_manual = st.text_input("Ketik NIK User:")
            if nik_manual and nik_manual in db_u:
                st.success(f"User ditemukan")
                pass_baru = st.text_input("Password Baru:", type="password")
                if st.button("Update Password"):
                    db_u[nik_manual] = pass_baru
                    if update_user_db(db_u): st.success("Berhasil!"); st.rerun()
            elif nik_manual: st.error("NIK tidak ditemukan.")
        except: pass

    with tab_res:
        konfirmasi = st.text_input("Ketik 'KONFIRMASI' untuk reset hasil:")
        if st.button("🔥 RESET HASIL INPUT", type="primary"):
            if konfirmasi == "KONFIRMASI":
                res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                p_ids = [f['public_id'] for f in res.get('resources', [])]
                if p_ids: cloudinary.api.delete_resources(p_ids, resource_type="raw")
                st.cache_data.clear() 
                st.success("Dibersihkan!"); time.sleep(2); st.rerun()

    # FIX PROBLEM 2: Tombol Logout Admin berada di dalam kategori ADMIN_PANEL
    st.write("---")
    if st.button("🚪 Logout Admin", use_container_width=True, key="btn_logout_admin"): 
        st.cache_data.clear()
        st.session_state.page = "HOME"
        st.rerun()

# =================================================================
# 5. USER INPUT (FIX SINKRONISASI DATA LAMA)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Pareto")
    df_m, v_master = get_master_data()
    if df_m is not None:
        # --- Filter AM & Toko ---
        list_am = sorted(df_m['AM'].astype(str).str.upper().unique())
        sel_am = st.selectbox("1. PILIH AM:", list_am)
        df_f_am = df_m[df_m['AM'].astype(str).str.upper() == sel_am]
        list_nama_toko = sorted(df_f_am['NAMA TOKO'].astype(str).str.upper().unique())
        sel_nama_toko = st.selectbox("2. PILIH NAMA TOKO:", list_nama_toko)
        df_selected = df_f_am[df_f_am['NAMA TOKO'].astype(str).str.upper() == sel_nama_toko]
        val_kdtoko, val_as = str(df_selected['KDTOKO'].iloc[0]), str(df_selected['AS'].iloc[0])
        
        c1, c2 = st.columns(2)
        c1.metric("KDTOKO:", val_kdtoko); c2.metric("AS:", val_as)

        # --- PROSES SINKRONISASI (MERGE MASTER + CLOUD) ---
        existing_df = get_existing_result(val_kdtoko, v_master)
        
        # 1. Siapkan Data Master terbaru (sebagai pondasi)
        data_toko_final = df_selected.copy()
        # Pastikan PLU di Master adalah String & tidak ada spasi
        data_toko_final['PLU'] = data_toko_final['PLU'].astype(str).str.strip()

        if existing_df is not None:
            # 2. Siapkan Data Lama dari Cloud
            cloud_input = existing_df.copy()
            # Bersihkan nama kolom & paksa PLU ke string untuk kecocokan 100%
            cloud_input.columns = [str(c).upper().strip() for c in cloud_input.columns]
            
            if 'KETERANGAN' in cloud_input.columns:
                # Ambil hanya PLU dan KETERANGAN, hapus duplikat PLU
                cloud_data = cloud_input[['PLU', 'KETERANGAN']].copy()
                cloud_data['PLU'] = cloud_data['PLU'].astype(str).str.strip()
                cloud_data = cloud_data.drop_duplicates(subset=['PLU'], keep='last')
                
                # 3. Hapus kolom KETERANGAN di Master agar tidak jadi KETERANGAN_x
                if 'KETERANGAN' in data_toko_final.columns:
                    data_toko_final = data_toko_final.drop(columns=['KETERANGAN'])
                
                # 4. Gabungkan (Left Join): Master + Keterangan dari Cloud
                data_toko_final = data_toko_final.merge(cloud_data, on='PLU', how='left')
                st.success(f"✅ Sinkronisasi Berhasil: Isian lama untuk Seri {v_master} telah dimuat.")
        
        # Jaminan: Jika tidak ada data lama atau PLU baru, kolom KETERANGAN tetap ada tapi kosong
        if 'KETERANGAN' not in data_toko_final.columns: 
            data_toko_final['KETERANGAN'] = ""
        data_toko_final['KETERANGAN'] = data_toko_final['KETERANGAN'].fillna("")

        # --- CLEANING DATA UNTUK EDITOR ---
        for col in ['PLU', 'DESC', 'KETERANGAN']:
            if col in data_toko_final.columns:
                data_toko_final[col] = data_toko_final[col].astype(str).replace(['nan', 'None', 'NaN'], '')
        
        for col in ['QTY', 'RUPIAH']:
            if col in data_toko_final.columns:
                data_toko_final[col] = pd.to_numeric(data_toko_final[col], errors='coerce').fillna(0)

        # --- TAMPILAN EDITOR ---
        disp_cols = ['PLU', 'DESC', 'QTY', 'RUPIAH', 'KETERANGAN']
        config = {
            "PLU": st.column_config.TextColumn("PLU", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", format="%.0f", disabled=True),
            "RUPIAH": st.column_config.NumberColumn("RUPIAH", format="%.0f", disabled=True),
            "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True),
        }
        
        # Gunakan hash data agar editor reset jika master berganti
        data_hash = hashlib.md5(pd.util.hash_pandas_object(data_toko_final[disp_cols]).values).hexdigest()
        edited_df = st.data_editor(
            data_toko_final[disp_cols], 
            column_config=config, 
            hide_index=True, 
            use_container_width=True, 
            key=f"ed_{val_kdtoko}_{data_hash}"
        )
        
        if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
            if edited_df['KETERANGAN'].apply(lambda x: str(x).strip() == "").any():
                st.error("⚠️ Semua kolom KETERANGAN wajib diisi!")
            else:
                # Ambil urutan kolom asli dari master (NO, KDTOKO, NAMA TOKO, AM, AS, PLU, DESC, QTY, RUPIAH)
                original_cols = [c for c in df_m.columns if c != 'KETERANGAN']
                # Tambahkan KETERANGAN di paling akhir
                save_cols_order = original_cols + ['KETERANGAN']
                
                # Masukkan hasil edit user ke dataframe final
                data_toko_final['KETERANGAN'] = edited_df['KETERANGAN'].values
                final_save_df = data_toko_final[save_cols_order]
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w: 
                    final_save_df.to_excel(w, index=False)
                
                p_id = f"pareto_nkl/hasil/Hasil_{val_kdtoko}_v{v_master}.xlsx"
                cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.cache_data.clear() 
                st.success("✅ DATA TERSIMPAN!"); time.sleep(1); st.rerun()

    if st.button("🚪 Keluar (Logout)", use_container_width=True): 
        st.cache_data.clear()
        st.session_state.page = "HOME"
        st.rerun()
