import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils
import hashlib
import requests
import io
import json
import time
import os
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Web Monitoring IC Bali", 
    layout="wide", 
    page_icon="🏢"
)

# --- 2. KONFIGURASI GLOBAL ---
USER_DB_PATH = "Config/users_area.json"       
LOG_DB_PATH = "Config/activity_log_area.json"
RUSAK_PABRIK_DB = "Config/data_rusak_pabrik.json" 
RUSAK_PABRIK_IMG_FOLDER = "Area/RusakPabrik/Foto"

# Link File Statis (Pastikan file ini ada di GitHub/Cloudinary Anda)
URL_CONTOH_BA = "https://res.cloudinary.com/demo/image/upload/sample.jpg" 

# --- 3. CSS & TEMA (Default System) ---
def atur_tema():
    if 'current_theme' not in st.session_state:
        st.session_state['current_theme'] = "System" 

    # CSS Global (Hide Toolbar & Fix Layout)
    st.markdown("""
        <style>
            [data-testid="stToolbar"] {visibility: hidden; display: none !important;}
            [data-testid="stDecoration"] {visibility: hidden; display: none !important;}
            footer {visibility: hidden; display: none;}
            .main .block-container {padding-top: 2rem;}
            [data-testid="stSidebarCollapsedControl"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
    
    # Otomatis mengikuti System, tapi kita beri CSS fix untuk Dark Mode agar kontras
    st.markdown("""
        <style>
            @media (prefers-color-scheme: dark) {
                .stApp { background-color: #0E1117; color: #FFFFFF; }
                div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
                    background-color: #FFFFFF !important; border: 1px solid #ccc !important;
                }
                div[data-baseweb="select"] span { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
                div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; caret-color: #000 !important; }
                ul[data-baseweb="menu"] { background-color: #FFFFFF !important; }
                li[role="option"] span { color: #000000 !important; }
            }
        </style>
    """, unsafe_allow_html=True)

atur_tema()

# --- 4. CONFIG DATA (HANYA AREA) ---
ADMIN_CONFIG = {
    "AREA_INTRANSIT": {"username": "admin_area_prof", "password": "123", "folder": "Area/Intransit", "label": "Area - Intransit/Proforma"},
    "AREA_NKL": {"username": "admin_area_nkl", "password": "123", "folder": "Area/NKL", "label": "Area - NKL"},
    "AREA_RUSAK": {"username": "admin_area_rusak", "password": "123", "folder": "Area/BarangRusak", "label": "Area - Barang Rusak"}
}

DATA_CONTACT = {
    "AREA_NKL": [("Putu IC", "087850110155"), ("Priyadi IC", "087761390987")],
    "AREA_INTRANSIT": [("Muklis IC", "081934327289"), ("Proforma - Ari IC", "081353446516"), ("NRB - Yani IC", "087760346299"), ("BPB/TAT - Tulasi IC", "081805347302")],
    "AREA_RUSAK": [("Putu IC", "087850110155"), ("Dwi IC", "083114444424"), ("Gean IC", "087725860048")]
}

# --- 5. SYSTEM FUNCTIONS ---
def init_cloudinary():
    if "cloudinary" not in st.secrets:
        st.error("⚠️ Kunci Cloudinary belum dipasang!")
        st.stop()
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True
    )

@st.cache_data(ttl=600, show_spinner=False) 
def get_all_files_cached():
    try:
        raw = cloudinary.api.resources(resource_type="raw", type="upload", max_results=500)
        return raw.get('resources', [])
    except:
        return []

def upload_file(file_upload, folder_path):
    public_id_path = f"{folder_path}/{file_upload.name}"
    res = cloudinary.uploader.upload(file_upload, resource_type="raw", public_id=public_id_path, overwrite=True)
    return res

def upload_image_error(image_file):
    res = cloudinary.uploader.upload(image_file, folder="ReportError", resource_type="image")
    return res

def hapus_file(public_id, res_type="raw"):
    try:
        cloudinary.api.delete_resources([public_id], resource_type=res_type, type="upload")
        return True
    except:
        return False

# --- FUNGSI DATABASE (REALTIME) ---
def get_json_fresh(public_id):
    try:
        resource = cloudinary.api.resource(public_id, resource_type="raw")
        url = resource.get('secure_url')
        if url:
            url_no_cache = f"{url}?t={int(time.time())}"
            resp = requests.get(url_no_cache)
            if resp.status_code == 200:
                return resp.json()
        return {}
    except:
        return {}

def upload_json_to_cloud(data_dict, public_id):
    json_data = json.dumps(data_dict)
    cloudinary.uploader.upload(
        io.BytesIO(json_data.encode('utf-8')), 
        resource_type="raw", 
        public_id=public_id,
        overwrite=True
    )

def catat_login_activity(username):
    try:
        log_data = get_json_fresh(LOG_DB_PATH)
        now = datetime.utcnow() + timedelta(hours=8)
        tanggal_str = now.strftime("%Y-%m-%d")
        if tanggal_str not in log_data: log_data[tanggal_str] = {}
        if username not in log_data[tanggal_str]: log_data[tanggal_str][username] = 0
        log_data[tanggal_str][username] += 1
        upload_json_to_cloud(log_data, LOG_DB_PATH)
    except Exception as e: print(f"Log Error: {e}")

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- FUNGSI KHUSUS RUSAK PABRIK ---
def simpan_data_rusak_pabrik(kode_toko, no_nrb, tgl_nrb, file_foto):
    try:
        if len(kode_toko) != 4:
            return False, "⚠️ Gagal: Kode Toko harus tepat 4 karakter."
        if file_foto.size > 2 * 1024 * 1024:
            return False, "⚠️ Gagal: Ukuran foto melebihi 2 MB."

        kode_clean = kode_toko.upper().replace(" ", "")
        nrb_clean = no_nrb.upper().replace(" ", "")
        tgl_str = tgl_nrb.strftime("%d%m%Y")
        folder_bulan = datetime.now().strftime("%Y-%m")
        nama_file_unik = f"{kode_clean}_{nrb_clean}_{tgl_str}"
        public_id = f"{RUSAK_PABRIK_IMG_FOLDER}/{folder_bulan}/{nama_file_unik}"
        
        res = cloudinary.uploader.upload(
            file_foto, resource_type="image", public_id=public_id, overwrite=True,
            transformation=[{'width': 800, 'crop': "limit"}, {'quality': "auto:eco"}, {'fetch_format': "auto"}]
        )
        url_foto = res.get('secure_url')

        data_lama = get_json_fresh(RUSAK_PABRIK_DB)
        if isinstance(data_lama, dict) and not data_lama: data_lama = [] 
        
        entry_baru = {
            "Input_Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Bulan_Upload": folder_bulan, 
            "Kode_Toko": kode_clean, "No_NRB": nrb_clean, "Tanggal_NRB": str(tgl_nrb),
            "Bukti_Foto": url_foto, "User_Input": st.session_state.get('area_user_name', 'Unknown')
        }
        data_lama.append(entry_baru)
        upload_json_to_cloud(data_lama, RUSAK_PABRIK_DB)
        return True, "✅ Data & Foto Berhasil Disimpan!"
    except Exception as e: return False, f"Error System: {e}"

def hapus_data_bulan_tertentu(bulan_target):
    try:
        prefix_folder = f"{RUSAK_PABRIK_IMG_FOLDER}/{bulan_target}/"
        cloudinary.api.delete_resources_by_prefix(prefix_folder, resource_type="image")
        try: cloudinary.api.delete_folder(prefix_folder)
        except: pass 
        data_lama = get_json_fresh(RUSAK_PABRIK_DB)
        if isinstance(data_lama, list):
            data_baru = [d for d in data_lama if d.get('Bulan_Upload') != bulan_target]
            upload_json_to_cloud(data_baru, RUSAK_PABRIK_DB)
        return True, f"Semua data bulan {bulan_target} berhasil dihapus."
    except Exception as e: return False, f"Gagal menghapus: {e}"

# --- EXCEL FUNCTIONS ---
@st.cache_data(ttl=600, show_spinner=False)
def load_excel_data(url, sheet_name, header_row, force_text=False):
    try:
        response = requests.get(url)
        file_content = io.BytesIO(response.content)
        row_idx = header_row - 1 if header_row > 0 else 0
        if force_text:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=row_idx, dtype=str).fillna("")
        else:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=row_idx)
        df.columns = df.columns.astype(str)
        return df
    except:
        return None

@st.cache_data(ttl=600, show_spinner=False)
def get_sheet_names(url):
    try:
        response = requests.get(url)
        return pd.ExcelFile(io.BytesIO(response.content)).sheet_names
    except:
        return []

def format_ribuan_indo(nilai):
    try:
        if float(nilai) % 1 != 0:
            val = "{:,.2f}".format(float(nilai)) 
        else:
            val = "{:,.0f}".format(float(nilai))
        translation = val.maketrans({",": ".", ".": ","})
        return val.translate(translation)
    except:
        return nilai

# --- UI COMPONENTS ---
def tampilkan_kontak(divisi_key):
    if not divisi_key: return
    kontak = DATA_CONTACT.get(divisi_key, [])
    if kontak:
        judul = divisi_key.replace("AREA_", "Divisi ").replace("_", " ")
        with st.expander(f"📞 Contact Person (CP) - {judul}"):
            cols = st.columns(4)
            for i, (nama, telp) in enumerate(kontak):
                wa = "62" + telp[1:] if telp.startswith("0") else telp
                cols[i%4].info(f"**{nama}**\n[{telp}](https://wa.me/{wa})")

def proses_tampilkan_excel(url, key_unik):
    sheets = get_sheet_names(url)
    if sheets:
        c1, c2 = st.columns(2)
        sh = c1.selectbox("Sheet:", sheets, key=f"sh_{key_unik}")
        hd = c2.number_input("Header:", 1, key=f"hd_{key_unik}")
        c3, c4 = st.columns([2, 1])
        src = c3.text_input("Cari:", key=f"src_{key_unik}")
        fmt = c4.checkbox("Jaga Semua Teks (No HP/NIK)", key=f"fmt_{key_unik}")
        
        with st.spinner("Loading Data..."): 
            df_raw = load_excel_data(url, sh, hd, fmt)
        
        if df_raw is not None:
            if src:
                try:
                    mask = df_raw.astype(str).apply(lambda x: x.str.contains(src, case=False, na=False)).any(axis=1)
                    df_raw = df_raw[mask]
                except: pass

            df_display = df_raw.copy()
            if not fmt:
                num_cols = df_display.select_dtypes(include=['float64', 'int64']).columns.tolist()
                kw_raw_code = ['prdcd', 'plu', 'barcode', 'kode', 'id', 'nik', 'no', 'nomor']
                for col in num_cols:
                    try:
                        col_str = str(col).lower()
                        if any(k in col_str for k in kw_raw_code):
                            df_display[col] = df_display[col].astype(str).str.replace(r'\.0$', '', regex=True)
                        elif pd.api.types.is_numeric_dtype(df_display[col]):
                            df_display[col] = df_display[col].apply(format_ribuan_indo)
                    except: continue

            st.write("")
            with st.expander("📏 Pengaturan Tampilan Tabel"):
                col_fz, col_mode, col_h = st.columns(3)
                with col_fz:
                    pilihan_kolom = ["Tidak Ada"] + df_display.columns.tolist()
                    freeze_col = st.selectbox("❄️ Freeze Kolom Kiri:", pilihan_kolom, key=f"fz_{key_unik}")
                with col_mode:
                    st.write("↔️ Mode Lebar")
                    use_full_width = st.checkbox("Fit Screen", value=False, key=f"fw_{key_unik}")
                with col_h:
                    table_height = st.slider("↕️ Tinggi (px):", 200, 1000, 500, 50, key=f"th_{key_unik}")
            
            if freeze_col != "Tidak Ada":
                df_display = df_display.set_index(freeze_col)

            st.dataframe(df_display, use_container_width=use_full_width, height=table_height)
            
            csv = df_raw.to_csv(index=False).encode('utf-8')
            col_info, col_dl = st.columns([3, 1])
            with col_info: st.caption(f"Total: {len(df_raw)} Baris")
            with col_dl:
                st.download_button("📥 Download CSV", csv, f"Data_Export_{sh}.csv", "text/csv", key=f"dl_{key_unik}")
        else: st.warning("⚠️ Gagal membaca data. Cek Header.")

def tampilkan_viewer(judul_tab, folder_target, semua_files, kode_kontak=None):
    tampilkan_kontak(kode_kontak)
    prefix = folder_target + "/"
    files_filtered = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    if not files_filtered:
        st.info(f"📭 Data Kosong: {folder_target}")
        return
    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in files_filtered}
    unik = f"std_{folder_target}"
    pilih = st.selectbox(f"Pilih File {judul_tab}:", list(dict_files.keys()), key=f"sel_{unik}")
    if pilih: proses_tampilkan_excel(dict_files[pilih], unik)

def tampilkan_viewer_area_rusak(folder_target, semua_files, kode_kontak=None):
    tampilkan_kontak(kode_kontak)
    st.markdown("### ⚠️ Area - Barang Rusak")
    
    tab_mon, tab_input = st.tabs(["📂 Monitoring Data (Excel)", "🏭 Input Rusak Pabrik"])
    
    with tab_mon:
        kat = st.radio("Filter:", ["Semua Data", "Say Bread", "Mr Bread", "Fried Chicken", "Onigiri", "DRY"], horizontal=True)
        st.divider()
        prefix = folder_target + "/"
        files_in = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
        if kat == "Semua Data": ff = files_in
        elif kat == "Say Bread": ff = [f for f in files_in if "say bread" in f['public_id'].lower()]
        elif kat == "Mr Bread": ff = [f for f in files_in if "mr bread" in f['public_id'].lower()]
        elif kat == "Fried Chicken": ff = [f for f in files_in if "fried chicken" in f['public_id'].lower()]
        elif kat == "Onigiri": ff = [f for f in files_in if "onigiri" in f['public_id'].lower()]
        elif kat == "DRY": ff = [f for f in files_in if "dry" in f['public_id'].lower()]
        else: ff = []

        if not ff: st.warning(f"File '{kat}' tidak ditemukan.")
        else:
            dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in ff}
            unik = "area_rusak_special"
            pilih = st.selectbox(f"Pilih File ({kat}):", list(dict_files.keys()), key=f"sel_{unik}")
            if pilih: proses_tampilkan_excel(dict_files[pilih], unik)

    with tab_input:
        st.info("Formulir Input Berita Acara Rusak Pabrik")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                in_kode = st.text_input("Kode Toko (4 Digit)", max_chars=4, placeholder="Cth: F08C")
            with col2:
                in_nrb = st.text_input("Nomor NRB Rusak Pabrik")
            in_tgl = st.date_input("Tanggal NRB")
            st.markdown("---")
            in_foto = st.file_uploader("Upload Foto Berita Acara", type=['jpg', 'jpeg', 'png'])
            st.caption("ℹ️ Size maksimal 2 MB. Jika hasil foto lebih besar harap screenshot dahulu lalu upload ulang.")
            
            if st.button("Kirim Laporan", type="primary", use_container_width=True):
                if in_kode and in_nrb and in_foto:
                    with st.spinner("Sedang memproses foto & data..."):
                        sukses, pesan = simpan_data_rusak_pabrik(in_kode, in_nrb, in_tgl, in_foto)
                        if sukses:
                            st.success(pesan)
                            st.balloons()
                        else: st.error(pesan)
                else: st.warning("Mohon lengkapi semua data.")
        
        st.write("")
        with st.expander("ℹ️ Lihat Contoh Format BA (Klik Disini)"):
            c_img_ex, c_dl_ex = st.columns([1, 1])
            with c_img_ex:
                st.image(URL_CONTOH_BA, caption="Contoh Format BA", use_container_width=True)
            with c_dl_ex:
                st.info("Pastikan foto yang diupload jelas dan sesuai format di samping.")
        
        st.write("")
        with st.expander("Riwayat Inputan Anda (Hari Ini)"):
            try:
                raw_data = get_json_fresh(RUSAK_PABRIK_DB)
                if isinstance(raw_data, list) and raw_data:
                    df_rusak = pd.DataFrame(raw_data)
                    curr_user = st.session_state.get('area_user_name', '')
                    if curr_user:
                        df_rusak = df_rusak[df_rusak['User_Input'] == curr_user]
                    st.dataframe(df_rusak.tail(5), use_container_width=True) 
                else: st.caption("Belum ada data.")
            except: pass

def tampilkan_viewer_area_intransit(folder_target, semua_files, kode_kontak=None):
    tampilkan_kontak(kode_kontak)
    st.markdown("### 🚛 Area - Intransit/Proforma")
    kat = st.radio("Filter Kategori:", ["Semua Data", "NRB Intransit", "BPB/TAT Intransit"], horizontal=True)
    if kat == "NRB Intransit":
        st.markdown("""<div style="background-color: #550000; padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid red;"><marquee style="color: #ffcccc; font-weight: bold; font-size: 16px;">📢 JIKA NRB TELAH DIKIRIM KE DC/DEPO, TOLONG KONFIRMASI KE YANI IC</marquee></div>""", unsafe_allow_html=True)
    elif kat == "BPB/TAT Intransit":
        st.markdown("""<div style="background-color: #004400; padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid green;"><marquee style="color: #ccffcc; font-weight: bold; font-size: 16px;">📢 JIKA BPB DAN TAT TELAH DIPROSES DAN FISIK DITERIMA TOKO, TOLONG KONFIRMASI KE TULASI IC</marquee></div>""", unsafe_allow_html=True)
    st.divider()
    prefix = folder_target + "/"
    files_in = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    if kat == "Semua Data": ff = files_in
    elif kat == "NRB Intransit": ff = [f for f in files_in if "nrb" in f['public_id'].lower()]
    elif kat == "BPB/TAT Intransit": ff = [f for f in files_in if "bpb" in f['public_id'].lower() or "tat" in f['public_id'].lower()]
    else: ff = []
    if not ff:
        st.warning(f"File kategori '{kat}' tidak ditemukan.")
        return
    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in ff}
    unik = "area_intransit_special"
    pilih = st.selectbox(f"Pilih File ({kat}):", list(dict_files.keys()), key=f"sel_{unik}")
    if pilih: proses_tampilkan_excel(dict_files[pilih], unik)

# --- MAIN APP ---
def main():
    if 'auth_area' not in st.session_state: st.session_state['auth_area'] = False
    if 'area_user_name' not in st.session_state: st.session_state['area_user_name'] = ""
    if 'admin_logged_in_key' not in st.session_state: st.session_state['admin_logged_in_key'] = None

    init_cloudinary()
    all_files = get_all_files_cached()

    st.title("📊 Monitoring IC Bali")
    
    menu_options = ["Area", "Lapor Error", "🔐 Admin Panel"]
    menu = st.radio("Navigasi:", menu_options, horizontal=True)
    st.divider()

    # --- 1. AREA ---
    if menu == "Area":
        if not st.session_state['auth_area']:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.info("🔒 Silakan Login untuk akses menu Area")
                
                # Cek file lokal 'juklak.pdf'
                juklak_file = "juklak.pdf"
                if os.path.exists(juklak_file):
                    with open(juklak_file, "rb") as f:
                        st.download_button("📥 Download Buku Panduan (Juklak)", f, "Panduan_Web_Monitoring.pdf", "application/pdf", use_container_width=True)

                st.write("") 
                tab_login, tab_daftar = st.tabs(["Masuk (Login)", "Daftar Akun Baru"])
                
                with tab_login:
                    with st.form("login_area"):
                        u = st.text_input("Username")
                        p = st.text_input("Password", type="password")
                        if st.form_submit_button("Masuk"):
                            with st.spinner("Memverifikasi..."):
                                db_users = get_json_fresh(USER_DB_PATH) 
                                p_hash = hash_password(p)
                                if u in db_users and db_users[u] == p_hash:
                                    st.session_state['auth_area'] = True
                                    st.session_state['area_user_name'] = u
                                    catat_login_activity(u) 
                                    st.success("Login Berhasil!")
                                    st.rerun()
                                else: st.error("Username atau Password Salah")
                    with st.expander("❓ Lupa Password?"):
                        st.write("Silakan hubungi Gean untuk reset password.")
                        st.markdown("""<a href="https://wa.me/6287725860048?text=Halo%20Gean,%20saya%20lupa%20password%20Web%20Monitoring%20Area" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">📲 Hubungi Gean via WhatsApp</button></a>""", unsafe_allow_html=True)

                with tab_daftar:
                    with st.form("daftar_area"):
                        st.write("Buat akun baru")
                        new_u = st.text_input("Username Baru")
                        new_p = st.text_input("Password Baru", type="password")
                        c_btn, c_note = st.columns([1, 2])
                        with c_btn: submit_daftar = st.form_submit_button("Daftar Akun")
                        with c_note: st.caption("ℹ️ **AS & AM** sebaiknya menggunakan inisial nama untuk username.")
                        if submit_daftar:
                            if new_u and new_p:
                                with st.spinner("Mendaftarkan..."):
                                    db_users = get_json_fresh(USER_DB_PATH)
                                    if new_u in db_users: st.error("Username sudah dipakai!")
                                    else:
                                        db_users[new_u] = hash_password(new_p)
                                        upload_json_to_cloud(db_users, USER_DB_PATH)
                                        time.sleep(2)
                                        st.success(f"✅ Akun '{new_u}' Berhasil Dibuat!")
                                        st.info("Silakan pindah ke Tab 'Masuk' dan Login menggunakan password yang baru dibuat.")
                            else: st.warning("Isi data dengan lengkap")
        else:
            c_info, c_out = st.columns([5, 1])
            with c_info: st.success(f"👋 Halo, {st.session_state['area_user_name']}")
            with c_out: 
                if st.button("Logout Area"):
                    st.session_state['auth_area'] = False
                    st.rerun()
            st.divider()
            t1, t2, t3 = st.tabs(["Intransit", "NKL", "Barang Rusak"])
            with t1: tampilkan_viewer_area_intransit(ADMIN_CONFIG["AREA_INTRANSIT"]["folder"], all_files, "AREA_INTRANSIT")
            with t2: tampilkan_viewer("NKL", ADMIN_CONFIG["AREA_NKL"]["folder"], all_files, "AREA_NKL")
            with t3: tampilkan_viewer_area_rusak(ADMIN_CONFIG["AREA_RUSAK"]["folder"], all_files, "AREA_RUSAK")

    # --- 2. LAPOR ERROR ---
    elif menu == "Lapor Error":
        st.subheader("🚨 Lapor Error")
        up = st.file_uploader("Upload Screenshot", type=['png', 'jpg', 'jpeg'])
        if up and st.button("Kirim"):
            with st.spinner("Sending..."):
                upload_image_error(up)
                st.success("terima kasih, error anda akan diselesaikan sesuai mood admin :)")
                st.balloons()
    
    # --- 3. ADMIN PANEL ---
    elif menu == "🔐 Admin Panel":
        st.subheader("⚙️ Kelola Data (Admin Only)")
        
        if st.session_state['admin_logged_in_key'] is None:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                with st.container(border=True):
                    st.write("Login Admin")
                    # Hanya satu departemen "Area" karena yang lain dihapus
                    dept = st.selectbox("Departemen:", ["Area"]) 
                    pilihan_sub = [("Intransit", "AREA_INTRANSIT"), ("NKL", "AREA_NKL"), ("Barang Rusak", "AREA_RUSAK")]
                    
                    sub_nm, sub_kd = st.selectbox("Target Menu:", pilihan_sub, format_func=lambda x: x[0])
                    u = st.text_input("Username Admin")
                    p = st.text_input("Password", type="password")
                    
                    if st.button("Masuk Panel Admin", use_container_width=True):
                        cfg = ADMIN_CONFIG[sub_kd]
                        if u == cfg['username'] and p == cfg['password']:
                            st.session_state['admin_logged_in_key'] = sub_kd
                            st.rerun()
                        else: st.error("Username atau Password Salah")
        else:
            key = st.session_state['admin_logged_in_key']
            cfg = ADMIN_CONFIG[key]
            
            c_head, c_out = st.columns([6, 1])
            with c_head: st.success(f"✅ Login Berhasil: {cfg['label']}")
            with c_out: 
                if st.button("Logout"): st.session_state['admin_logged_in_key']=None; st.rerun()
            
            tab_file, tab_user_mgr, tab_rusak_pabrik = st.tabs(["📂 Manajemen File/Foto", "👥 Manajemen User & Monitoring", "🏭 Rekap Rusak Pabrik"])
            
            with tab_file:
                col_up, col_del = st.columns(2)
                with col_up:
                    st.markdown(f"#### 📤 Upload ({cfg['label']})")
                    with st.container(border=True):
                        st.info(f"Target: `{cfg['folder']}`")
                        up = st.file_uploader("Pilih Excel", type=['xlsx'], key="admin_up_xls")
                        if up and st.button("Upload Excel", use_container_width=True):
                            with st.spinner("Uploading..."):
                                upload_file(up, cfg['folder'])
                                get_all_files_cached.clear()
                                st.success("Selesai!")
                                st.rerun()

                with col_del:
                    st.markdown("#### 🗑️ Hapus File")
                    with st.container(border=True):
                        prefix = cfg['folder'] + "/"
                        my_files = [f for f in all_files if f['public_id'].startswith(prefix) and f['resource_type'] == 'raw']
                        if my_files:
                            d_del = {f['public_id'].replace(prefix, ""): f['public_id'] for f in my_files}
                            sel_del = st.selectbox("Pilih File:", list(d_del.keys()), key="admin_del")
                            if st.button("Hapus Permanen", type="primary", use_container_width=True):
                                with st.spinner("Deleting..."):
                                    hapus_file(d_del[sel_del], "raw")
                                    get_all_files_cached.clear()
                                    st.success("Terhapus.")
                                    st.rerun()
                        else: st.caption("Folder kosong.")

            with tab_user_mgr:
                col_users, col_monitor = st.columns([1, 2])
                with col_users:
                    st.markdown("#### 🛠️ Kelola User Area")
                    with st.container(border=True):
                        if st.button("🔄 Reload Data User"): st.rerun()
                        db_users = get_json_fresh(USER_DB_PATH)
                        if db_users:
                            st.write(f"Total User: **{len(db_users)}**")
                            pilih_user = st.selectbox("Pilih Username:", list(db_users.keys()), key="sel_user_mgr")
                            st.markdown("---")
                            new_pass = st.text_input("Password Baru:", type="password", key="inp_new_pass")
                            if st.button("Simpan Password Baru", use_container_width=True):
                                if new_pass:
                                    db_users[pilih_user] = hash_password(new_pass)
                                    upload_json_to_cloud(db_users, USER_DB_PATH)
                                    st.success(f"Password '{pilih_user}' berhasil diubah!")
                                else: st.warning("Password kosong!")
                            st.markdown("---")
                            if st.button("❌ Hapus User Ini", type="primary", use_container_width=True):
                                try:
                                    del db_users[pilih_user]
                                    upload_json_to_cloud(db_users, USER_DB_PATH)
                                    st.success(f"User '{pilih_user}' telah dihapus!")
                                    time.sleep(1)
                                    st.rerun()
                                except: st.error("Gagal")
                        else: st.info("Belum ada user.")

                with col_monitor:
                    st.markdown("#### 📊 Monitoring Aktivitas")
                    with st.container(border=True):
                        if st.button("🔄 Refresh Monitoring"): st.rerun()
                        log_data = get_json_fresh(LOG_DB_PATH)
                        if log_data:
                            rekap_list = []
                            total_hits = 0
                            for tgl, users in log_data.items():
                                for usr, count in users.items():
                                    rekap_list.append({"Tanggal": tgl, "Username": usr, "Jumlah Akses": count})
                                    total_hits += count
                            df_log = pd.DataFrame(rekap_list)
                            df_log = df_log.sort_values(by="Tanggal", ascending=False)
                            m1, m2 = st.columns(2)
                            m1.metric("Total Login (All Time)", total_hits)
                            st.dataframe(df_log, use_container_width=True, height=300)
                            csv_log = df_log.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 Download Log (CSV)", csv_log, "Activity_Log.csv", "text/csv", use_container_width=True)
                        else: st.info("Log aktivitas kosong.")

            with tab_rusak_pabrik:
                st.markdown("#### 🏭 Rekap & Download Foto Rusak Pabrik")
                c_toko, c_nrb, c_bln = st.columns(3)
                with c_toko: cari_toko = st.text_input("Kode Toko:", placeholder="T001")
                with c_nrb: cari_nrb = st.text_input("No NRB:", placeholder="12345")
                with c_bln: cari_bulan = st.text_input("Bulan (YYYY-MM):", placeholder="2026-01")

                if st.button("🔍 Cari Foto", use_container_width=True):
                    data_rusak = get_json_fresh(RUSAK_PABRIK_DB)
                    if isinstance(data_rusak, list) and data_rusak:
                        df_rusak = pd.DataFrame(data_rusak)
                        mask = pd.Series([True] * len(df_rusak))
                        if cari_toko: mask &= df_rusak['Kode_Toko'].str.contains(cari_toko.upper(), na=False)
                        if cari_nrb: mask &= df_rusak['No_NRB'].str.contains(cari_nrb.upper(), na=False)
                        if cari_bulan: mask &= (df_rusak['Tanggal_NRB'].astype(str).str.contains(cari_bulan) | df_rusak.get('Bulan_Upload', '').astype(str).str.contains(cari_bulan))
                        hasil = df_rusak[mask]
                        if not hasil.empty:
                            st.success(f"Ditemukan {len(hasil)} Data.")
                            for index, row in hasil.iterrows():
                                with st.container(border=True):
                                    c_img, c_det = st.columns([1, 2])
                                    with c_img:
                                        thumb = row['Bukti_Foto'].replace("/upload/", "/upload/w_200,c_scale/")
                                        st.image(thumb, width=150)
                                    with c_det:
                                        st.write(f"**{row['Kode_Toko']} - NRB {row['No_NRB']}**")
                                        st.caption(f"Tgl: {row['Tanggal_NRB']}")
                                        dl = row['Bukti_Foto'].replace("/upload/", "/upload/fl_attachment/")
                                        st.markdown(f"[📥 Download]({dl})")
                        else: st.warning("Data tidak ditemukan.")
                    else: st.info("Database kosong.")

                st.divider()
                st.markdown("#### 📋 Tabel Semua Data")
                if st.button("🔄 Refresh Tabel"): st.rerun()
                try:
                    raw_data = get_json_fresh(RUSAK_PABRIK_DB)
                    if isinstance(raw_data, list) and raw_data:
                        df_table = pd.DataFrame(raw_data)
                        if "Input_Time" in df_table.columns: df_table = df_table.sort_values(by="Input_Time", ascending=False)
                        st.dataframe(df_table, use_container_width=True)
                        csv_rsk = df_table.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Rekap (CSV)", csv_rsk, "Rekap_Rusak.csv", "text/csv", use_container_width=True)
                except: pass

                st.write("")
                with st.expander("🚨 Danger Zone: Hapus Data Bulanan (Bersih-bersih)"):
                    st.error("Perhatian: Fitur ini akan menghapus SELURUH foto dan data pada bulan yang dipilih. Tidak bisa dibatalkan!")
                    raw_data_del = get_json_fresh(RUSAK_PABRIK_DB)
                    list_bulan = []
                    if isinstance(raw_data_del, list):
                        list_bulan = sorted(list(set([d.get('Bulan_Upload') for d in raw_data_del if d.get('Bulan_Upload')])))
                    
                    if list_bulan:
                        bulan_target = st.selectbox("Pilih Bulan yang akan dihapus total:", list_bulan)
                        pass_confirm = st.text_input("Masukkan Password Konfirmasi (123456):", type="password")
                        confirm_check = st.checkbox(f"Saya yakin ingin menghapus semua data bulan {bulan_target}")
                        if st.button("🔥 Hapus Semua Data Bulan Ini", type="primary"):
                            if pass_confirm == "123456" and confirm_check:
                                with st.spinner("Menghapus data di Cloudinary & Database..."):
                                    sukses_del, msg_del = hapus_data_bulan_tertentu(bulan_target)
                                    if sukses_del:
                                        st.success(msg_del)
                                        time.sleep(2)
                                        st.rerun()
                                    else: st.error(msg_del)
                            else: st.warning("Password salah atau checkbox belum dicentang.")
                    else: st.info("Tidak ada data bulan yang bisa dihapus.")

    st.markdown("""<div style='position: fixed; bottom: 0; right: 0; padding: 10px; opacity: 0.5; font-size: 12px; color: grey;'>Monitoring IC Bali System</div>""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
