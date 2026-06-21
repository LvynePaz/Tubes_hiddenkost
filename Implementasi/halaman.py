import streamlit as st
import pandas as pd
from db import run_query, run_execute

st.set_page_config(
    page_title="Hidden Kost – Dashboard",
    page_icon="HK",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
    }
    .role-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .role-pemilik { background: #1e40af; color: #dbeafe; }
    .role-penyewa { background: #065f46; color: #d1fae5; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "role" not in st.session_state:
    st.session_state.role = "Pemilik"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Pilih Role")
    role = st.radio(
        "Masuk sebagai:",
        ["Pemilik", "Penyewa"],
        index=0 if st.session_state.role == "Pemilik" else 1,
        key="role_radio",
    )
    st.session_state.role = role

    badge_class = "role-pemilik" if role == "Pemilik" else "role-penyewa"
    st.markdown(f'<span class="role-badge {badge_class}">{role}</span>', unsafe_allow_html=True)

    st.divider()
    st.caption("KELOMPOK 2 @2026")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("KELOMPOK 2 – Sistem Manajemen Kos")
role_label = "Dashboard Pemilik" if role == "Pemilik" else "Dashboard Penyewa"
st.caption(role_label)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  PEMILIK VIEW
# ══════════════════════════════════════════════════════════════════════════════
if role == "Pemilik":
    try:
        total_kamar      = run_query("SELECT COUNT(*) AS n FROM kamar")[0]["n"]
        kamar_kosong     = run_query("SELECT COUNT(*) AS n FROM kamar WHERE status = 'Kosong'")[0]["n"]
        kamar_terisi     = run_query("SELECT COUNT(*) AS n FROM kamar WHERE status = 'Sedang disewa'")[0]["n"]
        total_penyewa    = run_query("SELECT COUNT(*) AS n FROM profil_penyewa WHERE status = 'Aktif'")[0]["n"]
        total_pendapatan = run_query("SELECT COALESCE(SUM(nominal),0) AS n FROM pembayaran")[0]["n"]
        maintenance_pending = run_query("""
            SELECT COUNT(*) AS n FROM request_maintenance rm
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rv.status IS NULL OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
        """)[0]["n"]
    except Exception as e:
        st.error(f"Gagal terhubung ke database: {e}")
        st.stop()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Kamar", f"{total_kamar:,}")
    c2.metric("Kamar Kosong", f"{kamar_kosong:,}")
    c3.metric("Kamar Terisi", f"{kamar_terisi:,}")
    c4.metric("Penyewa Aktif", f"{total_penyewa:,}")
    c5.metric("Total Pendapatan", f"Rp {total_pendapatan:,.0f}")
    c6.metric("Maintenance", f"{maintenance_pending:,}")

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_kamar, tab_pendapatan, tab_pembayaran, tab_penyewa, tab_maint = st.tabs([
        "Data Kamar", "Pendapatan", "Pembayaran", "Data Penyewa", "Maintenance"
    ])

    # ── Tab Data Kamar ────────────────────────────────────────────────────────
    with tab_kamar:
        st.subheader("Data Seluruh Kamar")
        sql = """
            SELECT k.nomor AS "Nomor",
                   ko.nama_kos AS "Kos",
                   k.lantai AS "Lantai",
                   k.luas AS "Luas (m²)",
                   tk.kategori AS "Tipe",
                   tk.harga_sewa AS "Harga (Rp)",
                   k.status::TEXT AS "Status",
                   COALESCE(pp.nama_lengkap, '-') AS "Penyewa",
                   COALESCE(pp.pekerjaan, '-') AS "Pekerjaan",
                   COALESCE(TO_CHAR(s_aktif.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Sewa Mulai",
                   COALESCE(TO_CHAR(s_aktif.tanggal_akhir, 'DD-MM-YYYY'), '-') AS "Sewa Akhir"
            FROM kamar k
            JOIN kos ko ON k.id_kos = ko.id_kos
            JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
            LEFT JOIN LATERAL (
                SELECT s.id_penyewa, s.tanggal_mulai, s.tanggal_akhir
                FROM sewa s
                WHERE s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
                ORDER BY s.tanggal_mulai DESC LIMIT 1
            ) s_aktif ON TRUE
            LEFT JOIN profil_penyewa pp ON s_aktif.id_penyewa = pp.id_penyewa
            ORDER BY ko.nama_kos, k.nomor
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)

        if not df.empty:
            # Filter
            filter_kos = st.selectbox("Filter Kos:", ["Semua"] + sorted(df["Kos"].unique().tolist()), key="filter_kos")
            filter_status = st.radio("Filter Status:", ["Semua", "Kosong", "Sedang disewa"], horizontal=True, key="filter_status")

            df_filtered = df.copy()
            if filter_kos != "Semua":
                df_filtered = df_filtered[df_filtered["Kos"] == filter_kos]
            if filter_status != "Semua":
                df_filtered = df_filtered[df_filtered["Status"] == filter_status]

            df_filtered["Harga (Rp)"] = df_filtered["Harga (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data kamar.")

    # ── Tab Pendapatan ────────────────────────────────────────────────────────
    with tab_pendapatan:
        st.subheader("Pendapatan per Kos")
        sql = """
            SELECT ko.nama_kos AS "Nama Kos",
                   COUNT(DISTINCT s.id_sewa) AS "Jumlah Sewa",
                   SUM(pb.nominal) AS "Total Pendapatan",
                   AVG(pb.nominal)::INT AS "Rata-rata"
            FROM kos ko
            JOIN kamar k ON ko.id_kos = k.id_kos
            JOIN sewa s ON k.id_kamar = s.id_kamar
            JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
            GROUP BY ko.nama_kos ORDER BY "Total Pendapatan" DESC
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            df["Total Pendapatan"] = df["Total Pendapatan"].apply(lambda x: f"Rp {x:,}")
            df["Rata-rata"] = df["Rata-rata"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Pendapatan per Tipe Kamar")
        sql2 = """
            SELECT tk.kategori AS "Tipe",
                   tk.harga_sewa AS "Harga Sewa",
                   COUNT(DISTINCT s.id_sewa) AS "Jumlah Sewa",
                   SUM(pb.nominal) AS "Total Pendapatan"
            FROM tipe_kamar tk
            JOIN kamar k ON tk.id_tipe_kamar = k.id_tipe_kamar
            JOIN sewa s ON k.id_kamar = s.id_kamar
            JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
            GROUP BY tk.kategori, tk.harga_sewa ORDER BY "Total Pendapatan" DESC
        """
        rows2 = run_query(sql2)
        df2 = pd.DataFrame(rows2)
        if not df2.empty:
            df2["Harga Sewa"] = df2["Harga Sewa"].apply(lambda x: f"Rp {x:,}")
            df2["Total Pendapatan"] = df2["Total Pendapatan"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df2, use_container_width=True, hide_index=True)

    # ── Tab Pembayaran ────────────────────────────────────────────────────────
    with tab_pembayaran:
        st.subheader("Riwayat Pembayaran")
        sql = """
            SELECT pp_penyewa.nama_lengkap AS "Penyewa",
                   k.nomor AS "Kamar",
                   ko.nama_kos AS "Kos",
                   pb.nominal AS "Nominal (Rp)",
                   pb.metode_bayar::TEXT AS "Metode",
                   per.periode_bayar AS "Periode",
                   per.status::TEXT AS "Status Bayar"
            FROM pembayaran pb
            JOIN sewa s ON pb.id_sewa = s.id_sewa
            JOIN profil_penyewa pp_penyewa ON s.id_penyewa = pp_penyewa.id_penyewa
            JOIN kamar k ON s.id_kamar = k.id_kamar
            JOIN kos ko ON k.id_kos = ko.id_kos
            JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
            ORDER BY per.periode_bayar DESC
            LIMIT 500
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            # Filter
            filter_status_bayar = st.radio("Filter Status:", ["Semua", "Berhasil", "Gagal"], horizontal=True, key="filter_bayar")
            df_filtered = df.copy()
            if filter_status_bayar != "Semua":
                df_filtered = df_filtered[df_filtered["Status Bayar"] == filter_status_bayar]

            df_filtered["Nominal (Rp)"] = df_filtered["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)

            # Summary
            st.divider()
            st.subheader("Ringkasan Metode Pembayaran")
            sql_metode = """
                SELECT pb.metode_bayar::TEXT AS "Metode",
                       COUNT(*) AS "Jumlah",
                       SUM(pb.nominal) AS "Total"
                FROM pembayaran pb
                GROUP BY pb.metode_bayar ORDER BY "Total" DESC
            """
            rows_m = run_query(sql_metode)
            df_m = pd.DataFrame(rows_m)
            if not df_m.empty:
                df_m["Total"] = df_m["Total"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data pembayaran.")

    # ── Tab Data Penyewa ──────────────────────────────────────────────────────
    with tab_penyewa:
        st.subheader("Data Penyewa Aktif")
        sql = """
            SELECT pp.nama_lengkap AS "Nama",
                   pp.pekerjaan AS "Pekerjaan",
                   pp.instansi AS "Instansi",
                   pp.status::TEXT AS "Status",
                   COALESCE(k.nomor, '-') AS "Kamar",
                   COALESCE(ko.nama_kos, '-') AS "Kos",
                   COALESCE(TO_CHAR(s.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Sewa Mulai",
                   COALESCE(TO_CHAR(s.tanggal_akhir, 'DD-MM-YYYY'), '-') AS "Sewa Akhir"
            FROM profil_penyewa pp
            LEFT JOIN LATERAL (
                SELECT s.id_kamar, s.tanggal_mulai, s.tanggal_akhir
                FROM sewa s
                WHERE s.id_penyewa = pp.id_penyewa AND s.tanggal_akhir >= CURRENT_DATE
                ORDER BY s.tanggal_mulai DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN kamar k ON s.id_kamar = k.id_kamar
            LEFT JOIN kos ko ON k.id_kos = ko.id_kos
            WHERE pp.status = 'Aktif'
            ORDER BY pp.nama_lengkap
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            st.metric("Total Penyewa Aktif", len(df))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada penyewa aktif.")

    # ── Tab Maintenance ───────────────────────────────────────────────────────
    with tab_maint:
        st.subheader("Rekap Maintenance")
        sql = """
            SELECT pp.nama_lengkap AS "Penyewa",
                   rm.deskripsi AS "Keluhan",
                   COALESCE(rv.status::TEXT, 'Belum ditangani') AS "Status",
                   COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
                   COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
            FROM request_maintenance rm
            JOIN profil_penyewa pp ON rm.id_penyewa = pp.id_penyewa
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            ORDER BY
                CASE WHEN rv.status IS NULL THEN 0
                     WHEN rv.status = 'Tertunda' THEN 1
                     WHEN rv.status = 'Sedang dikerjakan' THEN 2
                     ELSE 3 END,
                rm.id_request_maintenance DESC
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            filter_maint = st.radio("Filter Status:", ["Semua", "Belum ditangani", "Tertunda", "Sedang dikerjakan", "Selesai"], horizontal=True, key="filter_maint")
            df_filtered = df.copy()
            if filter_maint != "Semua":
                df_filtered = df_filtered[df_filtered["Status"] == filter_maint]

            st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data maintenance.")


# ══════════════════════════════════════════════════════════════════════════════
#  PENYEWA VIEW
# ══════════════════════════════════════════════════════════════════════════════
else:
    try:
        penyewa = run_query("""
            SELECT id_penyewa, nama_lengkap FROM profil_penyewa
            WHERE status = 'Aktif' ORDER BY id_penyewa LIMIT 20
        """)
    except Exception as e:
        st.error(f"Gagal terhubung ke database: {e}")
        st.stop()

    if not penyewa:
        st.warning("Tidak ada penyewa aktif di database.")
        st.stop()

    with st.sidebar:
        st.markdown("### Simulasi Login")
        nama_list = [p["nama_lengkap"] for p in penyewa]
        pilihan = st.selectbox("Pilih penyewa:", nama_list)
        id_penyewa = [p["id_penyewa"] for p in penyewa if p["nama_lengkap"] == pilihan][0]

    st.markdown(f"### Selamat datang, **{pilihan}**!")
    st.divider()

    tab_kamar, tab_sewa, tab_maint = st.tabs([
        "Kamar Kosong", "Status Sewa", "Maintenance"
    ])

    # ── Kamar Kosong ──────────────────────────────────────────────────────────
    with tab_kamar:
        st.subheader("Daftar Kamar Kosong")
        sql = """
            SELECT k.nomor AS "Nomor",
                   ko.nama_kos AS "Kos",
                   k.lantai AS "Lantai",
                   tk.kategori AS "Tipe",
                   tk.harga_sewa AS "Harga (Rp)",
                   tk.deskripsi_fasilitas AS "Fasilitas"
            FROM kamar k
            JOIN kos ko ON k.id_kos = ko.id_kos
            JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
            WHERE k.status = 'Kosong'
            ORDER BY ko.nama_kos, k.nomor
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if df.empty:
            st.info("Tidak ada kamar kosong saat ini.")
        else:
            st.metric("Kamar Tersedia", len(df))
            df["Harga (Rp)"] = df["Harga (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Status Sewa ───────────────────────────────────────────────────────────
    with tab_sewa:
        st.subheader("Sewa Aktif Saya")
        sql = f"""
            SELECT s.id_sewa,
                   k.nomor AS "Kamar",
                   ko.nama_kos AS "Kos",
                   tk.kategori AS "Tipe",
                   tk.harga_sewa AS harga,
                   s.tanggal_mulai AS "Mulai",
                   s.tanggal_akhir AS "Akhir",
                   (s.tanggal_akhir - CURRENT_DATE) AS "Sisa Hari"
            FROM sewa s
            JOIN kamar k ON s.id_kamar = k.id_kamar
            JOIN kos ko ON k.id_kos = ko.id_kos
            JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
            WHERE s.id_penyewa = {id_penyewa}
              AND s.tanggal_akhir >= CURRENT_DATE
            ORDER BY s.tanggal_mulai DESC
        """
        rows = run_query(sql)
        df_sewa = pd.DataFrame(rows)

        if df_sewa.empty:
            st.info("Tidak ada sewa aktif saat ini.")
        else:
            # Display table (hide id_sewa and harga columns)
            df_show = df_sewa.drop(columns=["id_sewa", "harga"])
            df_show_fmt = df_show.copy()
            st.dataframe(df_show_fmt, use_container_width=True, hide_index=True)

            # ── Riwayat Pembayaran ────────────────────────────────────────────
            st.divider()
            st.subheader("Riwayat Pembayaran")
            sql_bayar = f"""
                SELECT k.nomor AS "Kamar",
                       pb.nominal AS "Nominal (Rp)",
                       pb.metode_bayar::TEXT AS "Metode",
                       per.periode_bayar AS "Periode",
                       per.status::TEXT AS "Status"
                FROM sewa s
                JOIN kamar k ON s.id_kamar = k.id_kamar
                JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
                JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
                WHERE s.id_penyewa = {id_penyewa}
                ORDER BY per.periode_bayar DESC
            """
            rows_bayar = run_query(sql_bayar)
            df_bayar = pd.DataFrame(rows_bayar)
            if df_bayar.empty:
                st.info("Belum ada riwayat pembayaran.")
            else:
                df_bayar["Nominal (Rp)"] = df_bayar["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_bayar, use_container_width=True, hide_index=True)

            # ── Form Pembayaran ───────────────────────────────────────────────
            st.divider()
            st.subheader("Bayar Sewa")
            with st.form("form_bayar", clear_on_submit=True):
                # Pilih sewa aktif
                sewa_options = {
                    f"{row['Kamar']} - {row['Kos']} (Rp {row['harga']:,}/bulan)": row
                    for _, row in df_sewa.iterrows()
                }
                sewa_pilih = st.selectbox("Pilih sewa:", list(sewa_options.keys()))
                sewa_data = sewa_options[sewa_pilih]

                jumlah_bulan = st.selectbox("Jumlah bulan:", [1, 2, 3])
                metode = st.selectbox("Metode pembayaran:", ["Transfer", "Tunai"])

                nominal_per_bulan = int(sewa_data["harga"])
                total_bayar = nominal_per_bulan * jumlah_bulan
                st.info(f"Total: Rp {nominal_per_bulan:,} x {jumlah_bulan} bulan = **Rp {total_bayar:,}**")

                submitted = st.form_submit_button("Bayar Sekarang")
                if submitted:
                    try:
                        id_sewa = int(sewa_data["id_sewa"])
                        # Insert pembayaran
                        run_execute(
                            "INSERT INTO pembayaran (nominal, metode_bayar, id_sewa) VALUES (%s, %s, %s)",
                            (total_bayar, metode, id_sewa)
                        )
                        # Get new pembayaran id
                        new_pb = run_query("SELECT MAX(id_pembayaran) AS id FROM pembayaran")[0]["id"]

                        # Insert periode for each month
                        import datetime
                        today = datetime.date.today()
                        for i in range(jumlah_bulan):
                            bulan = today.month + i
                            tahun = today.year
                            if bulan > 12:
                                bulan -= 12
                                tahun += 1
                            periode = f"{tahun}-{bulan:02d}"
                            run_execute(
                                "INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran) VALUES (%s, %s, %s)",
                                (periode, "Berhasil", new_pb)
                            )

                        st.success(f"Pembayaran berhasil! {jumlah_bulan} bulan, total Rp {total_bayar:,}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal melakukan pembayaran: {e}")

    # ── Maintenance ───────────────────────────────────────────────────────────
    with tab_maint:
        st.subheader("Request Maintenance Saya")
        sql = f"""
            SELECT rm.deskripsi AS "Keluhan",
                   COALESCE(rv.status::TEXT, 'Menunggu') AS "Status",
                   COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
                   COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
            FROM request_maintenance rm
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rm.id_penyewa = {id_penyewa}
            ORDER BY rv.status NULLS FIRST
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)

        if df.empty:
            st.success("Tidak ada request maintenance.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("ABD KELOMPOK 2 @2026")
