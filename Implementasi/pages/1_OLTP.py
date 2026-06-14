import streamlit as st
import pandas as pd
from db import run_query

st.set_page_config(page_title="OLTP – Hidden Kost", layout="wide")

st.title("🏠 OLTP – Operasional Harian")
st.caption("Transaksi harian: pencarian kamar, data penyewa aktif, status sewa, dan maintenance.")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Cari Kamar Kosong",
    "👤 Penyewa Aktif",
    "📋 Sewa Berjalan",
    "🔧 Maintenance Tertunda",
])


# ── TAB 1: Cari Kamar Kosong ──────────────────────────────────────────────────
with tab1:
    st.subheader("Daftar Kamar Kosong")

    col1, col2 = st.columns(2)
    with col1:
        pilih_kos = st.selectbox(
            "Pilih Kos",
            ["Semua", "Hidden Kost Origin", "Hidden Kost Lux"],
        )
    with col2:
        pilih_tipe = st.selectbox(
            "Tipe Kamar",
            ["Semua", "Tipe A", "Tipe B", "Tipe C"],
        )

    where_kos  = "" if pilih_kos  == "Semua" else f"AND ko.nama_kos = '{pilih_kos}'"
    where_tipe = "" if pilih_tipe == "Semua" else f"AND tk.kategori = '{pilih_tipe}'"

    sql = f"""
        SELECT
            k.nomor        AS "Nomor Kamar",
            ko.nama_kos    AS "Nama Kos",
            k.lantai       AS "Lantai",
            k.luas         AS "Luas (m²)",
            tk.kategori    AS "Tipe",
            tk.harga_sewa  AS "Harga Sewa (Rp)",
            tk.deskripsi_fasilitas AS "Fasilitas"
        FROM kamar k
        JOIN kos ko        ON k.id_kos        = ko.id_kos
        JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
        WHERE k.status = 'Kosong'
        {where_kos}
        {where_tipe}
        ORDER BY ko.nama_kos, k.nomor
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if df.empty:
        st.info("Tidak ada kamar kosong untuk filter yang dipilih.")
    else:
        st.metric("Total Kamar Kosong", len(df))
        df["Harga Sewa (Rp)"] = df["Harga Sewa (Rp)"].apply(lambda x: f"Rp {x:,}")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ── TAB 2: Penyewa Aktif ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Data Penyewa Aktif")

    cari = st.text_input("Cari nama penyewa", placeholder="contoh: Penyewa ke-10")

    where_nama = f"AND p.nama_lengkap ILIKE '%{cari}%'" if cari else ""

    sql = f"""
        SELECT
            p.nama_lengkap      AS "Nama Lengkap",
            p.pekerjaan         AS "Pekerjaan",
            p.instansi          AS "Instansi",
            p.deskripsi_pekerjaan AS "Deskripsi Pekerjaan",
            p.status            AS "Status"
        FROM profil_penyewa p
        WHERE p.status = 'Aktif'
        {where_nama}
        ORDER BY p.nama_lengkap
        LIMIT 100
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if df.empty:
        st.info("Tidak ada data penyewa aktif.")
    else:
        st.metric("Total Penyewa Aktif (maks. 100 ditampilkan)", len(df))
        st.dataframe(df, use_container_width=True, hide_index=True)


# ── TAB 3: Sewa Berjalan ──────────────────────────────────────────────────────
with tab3:
    st.subheader("Sewa yang Sedang Berjalan")

    sql = """
        SELECT
            p.nama_lengkap   AS "Nama Penyewa",
            k.nomor          AS "Nomor Kamar",
            ko.nama_kos      AS "Nama Kos",
            s.tanggal_mulai  AS "Tanggal Mulai",
            s.tanggal_akhir  AS "Tanggal Akhir",
            (s.tanggal_akhir - CURRENT_DATE) AS "Sisa Hari"
        FROM sewa s
        JOIN profil_penyewa p ON s.id_penyewa = p.id_penyewa
        JOIN kamar k           ON s.id_kamar   = k.id_kamar
        JOIN kos ko            ON k.id_kos     = ko.id_kos
        WHERE s.tanggal_akhir >= CURRENT_DATE
        ORDER BY s.tanggal_akhir ASC
        LIMIT 200
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if df.empty:
        st.info("Tidak ada sewa yang sedang berjalan.")
    else:
        st.metric("Jumlah Sewa Aktif", len(df))

        # Warnai sisa hari <= 30
        def warna_sisa(val):
            if isinstance(val, int) and val <= 30:
                return "background-color: #ffe0e0"
            return ""

        st.dataframe(
            df.style.applymap(warna_sisa, subset=["Sisa Hari"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("🔴 Baris merah = sewa berakhir dalam 30 hari ke depan")


# ── TAB 4: Maintenance Tertunda ───────────────────────────────────────────────
with tab4:
    st.subheader("Request Maintenance Belum Selesai")

    sql = """
        SELECT
            p.nama_lengkap              AS "Nama Penyewa",
            rm.deskripsi                AS "Keluhan",
            COALESCE(rv.status, 'Belum ada riwayat') AS "Status",
            rv.tanggal_mulai            AS "Tanggal Mulai Pengerjaan"
        FROM request_maintenance rm
        JOIN profil_penyewa p         ON rm.id_penyewa              = p.id_penyewa
        LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
        WHERE rv.status IS NULL
           OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
        ORDER BY rv.status NULLS FIRST
        LIMIT 200
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if df.empty:
        st.success("Semua request maintenance sudah selesai! ✅")
    else:
        col_a, col_b = st.columns(2)
        col_a.metric("Total Belum Selesai", len(df))
        tertunda = len(df[df["Status"] == "Tertunda"]) if "Status" in df.columns else 0
        col_b.metric("Status Tertunda", tertunda)
        st.dataframe(df, use_container_width=True, hide_index=True)
