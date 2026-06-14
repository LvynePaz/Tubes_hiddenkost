import streamlit as st
import pandas as pd
from db import run_query

st.set_page_config(
    page_title="Hidden Kost – Dashboard",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Hidden Kost – Sistem Manajemen Kos")
st.caption("Dashboard utama | OLTP · OLAP · Optimasi Index")

st.divider()

# ── Kartu ringkasan ───────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

try:
    total_kamar   = run_query("SELECT COUNT(*) AS n FROM kamar")[0]["n"]
    kamar_kosong  = run_query("SELECT COUNT(*) AS n FROM kamar WHERE status = 'Kosong'")[0]["n"]
    total_penyewa = run_query("SELECT COUNT(*) AS n FROM profil_penyewa WHERE status = 'Aktif'")[0]["n"]
    sewa_aktif    = run_query("SELECT COUNT(*) AS n FROM sewa WHERE tanggal_akhir >= CURRENT_DATE")[0]["n"]
    total_pendapatan = run_query("SELECT COALESCE(SUM(nominal),0) AS n FROM pembayaran")[0]["n"]

    col1.metric("Total Kamar",        f"{total_kamar:,}")
    col2.metric("Kamar Kosong",       f"{kamar_kosong:,}")
    col3.metric("Penyewa Aktif",      f"{total_penyewa:,}")
    col4.metric("Sewa Berjalan",      f"{sewa_aktif:,}")
    col5.metric("Total Pendapatan",   f"Rp {total_pendapatan:,.0f}")

except Exception as e:
    st.error(f"Gagal terhubung ke database: {e}")
    st.stop()

st.divider()

# ── Navigasi ──────────────────────────────────────────────────────────────────
st.subheader("Navigasi")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("""
    ### 📋 OLTP
    **Operasional Harian**

    - Cari kamar kosong
    - Daftar penyewa aktif
    - Sewa yang sedang berjalan
    - Maintenance tertunda

    ➡️ Gunakan menu **OLTP** di sidebar kiri.
    """)

with col_b:
    st.markdown("""
    ### 📊 OLAP
    **Analisis & Laporan**

    - Pendapatan per kos & tipe kamar
    - Tingkat okupansi kamar
    - Tren pembayaran bulanan
    - Rekap status maintenance

    ➡️ Gunakan menu **OLAP** di sidebar kiri.
    """)

with col_c:
    st.markdown("""
    ### ⚡ Optimasi Index
    **EXPLAIN ANALYZE**

    - Bandingkan Index Scan vs Seq Scan
    - 5 skenario query nyata
    - Ringkasan index yang ada
    - Rekomendasi index tambahan

    ➡️ Gunakan menu **Optimasi Index** di sidebar kiri.
    """)

st.divider()

# ── Perbedaan OLTP vs OLAP ────────────────────────────────────────────────────
st.subheader("Perbedaan OLTP dan OLAP")

tabel = pd.DataFrame({
    "Aspek": [
        "Tujuan",
        "Jenis Operasi",
        "Volume Data",
        "Kecepatan Transaksi",
        "Contoh Query",
        "Pengguna",
    ],
    "OLTP (Online Transaction Processing)": [
        "Mengelola transaksi harian secara real-time",
        "INSERT, UPDATE, DELETE, SELECT sederhana",
        "Data per transaksi kecil, tapi banyak transaksi",
        "Sangat cepat, milidetik per transaksi",
        "Cari kamar kosong, input data sewa baru",
        "Staff operasional, aplikasi front-end",
    ],
    "OLAP (Online Analytical Processing)": [
        "Menganalisis data historis untuk pengambilan keputusan",
        "SELECT kompleks dengan agregasi (SUM, COUNT, AVG, GROUP BY)",
        "Baca data dalam jumlah besar sekaligus",
        "Lebih lambat, tapi hasil komprehensif",
        "Total pendapatan per bulan, tingkat okupansi kamar",
        "Manajer, analis bisnis, laporan",
    ],
})

st.dataframe(tabel, use_container_width=True, hide_index=True)

st.divider()
st.caption("Dibuat untuk Tugas Besar Administrasi Basis Data – Hidden Kost Balikpapan")
