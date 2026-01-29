import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import io
import requests
from datetime import datetime

# 1. Konfigurasi Cloudinary (Ambil dari Secrets)
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Cloudinary tidak ditemukan!")

st.set_page_config(page_title="Input Penjelasan Pareto NKL", layout="wide")

# 2. Fungsi Load & Save
def load_data_pareto(toko_id, bulan):
    # Logika: Mencari file hasil di cloud, jika tidak ada ambil dari master
    # Untuk permulaan, kita buat dummy data berdasarkan kolom di foto
    p_id = f"pareto_nkl/hasil/Pareto_{toko_id}_{bulan}.xlsx"
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return pd.read_excel(io.BytesIO(resp.content))
    except:
        pass
    
    # Jika file belum ada, buat DataFrame kosong dengan struktur sesuai foto
    return pd.DataFrame([
        {"TOKO": toko_id, "TANGGAL": "2026-01-08", "PRDCD": "20140865", "DESC": "FD SAY BREAD TA (DC) NUTEL..", "QTY": -19, "RP_JUAL": -342000, "PENJELASAN": ""},
        {"TOKO": toko_id, "TANGGAL": "2026-01-08", "PRDCD": "20137293", "DESC": "POINT COFFEE KONVERSI OVO..", "QTY": 644, "RP_JUAL": -322000, "PENJELASAN": ""},
    ])

def save_data_pareto(df, toko_id, bulan):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False)
    p_id = f"pareto_nkl/hasil/Pareto_{toko_id}_{bulan}.xlsx"
    cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True)

# 3. Antarmuka (UI) - Sesuai Foto
st.title("Input Penjelasan Pareto Nkl Toko")

with st.container(border=True):
    col1, col2, col3 = st.columns([3, 3, 2])
    with col1:
        toko_opt = ["TQ86 - fresh gatot subroto timur - de", "TQ87 - contoh toko lain"]
        selected_toko = st.selectbox("PILIH TOKO", toko_opt)
    with col2:
        # Input bulan seperti pada foto
        selected_bulan = st.date_input("BULAN", value=datetime(2026, 1, 1))
    with col3:
        st.write("##") # Spasi
        btn_view = st.button("🔍 View Data", type="primary", use_container_width=True)

# 4. Tabel Input (Mekanisme Data Editor)
if btn_view or 'current_df' in st.session_state:
    toko_code = selected_toko.split(" - ")[0]
    bulan_str = selected_bulan.strftime("%Y-%m")
    
    if btn_view:
        st.session_state.current_df = load_data_pareto(toko_code, bulan_str)

    st.subheader("Data Pareto Nkl")
    
    # Menggunakan st.data_editor agar user bisa mengisi kolom Penjelasan
    edited_df = st.data_editor(
        st.session_state.current_df,
        column_config={
            "TOKO": st.column_config.TextColumn("TOKO", disabled=True),
            "TANGGAL": st.column_config.TextColumn("TANGGAL", disabled=True),
            "PRDCD": st.column_config.TextColumn("PRDCD", disabled=True),
            "DESC": st.column_config.TextColumn("DESC", disabled=True),
            "QTY": st.column_config.NumberColumn("QTY", disabled=True),
            "RP_JUAL": st.column_config.NumberColumn("RP_JUAL", format="Rp %d", disabled=True),
            "PENJELASAN": st.column_config.TextColumn("PENJELASAN", help="Isi penjelasan alfa-numerik di sini"),
        },
        hide_index=True,
        use_container_width=True,
        key="editor_pareto"
    )

    if st.button("💾 Simpan Penjelasan", type="primary"):
        save_data_pareto(edited_df, toko_code, bulan_str)
        st.success(f"✅ Penjelasan untuk {toko_code} berhasil disimpan!")
