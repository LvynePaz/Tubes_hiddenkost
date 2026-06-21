import re
import datetime
import streamlit as st
import pandas as pd
from db import run_query, run_execute, run_explain

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
st.title("HK – Sistem Manajemen Kos")
role_label = "Dashboard Pemilik" if role == "Pemilik" else "Dashboard Penyewa"
st.caption(role_label)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — OPTIMASI INDEX (dipakai di sub-section tab Data Kamar)
# ══════════════════════════════════════════════════════════════════════════════
def tampilkan_plan(plan_lines, label=""):
    """Tampilkan plan EXPLAIN ANALYZE + highlight Seq Scan / Index Scan + waktu eksekusi."""
    plan_text = "\n".join(plan_lines)
    st.code(plan_text, language="sql")

    if "Index Scan" in plan_text or "Index Only Scan" in plan_text or "Bitmap Index Scan" in plan_text:
        st.success(f"{label} → memakai **Index Scan**")
    elif "Seq Scan" in plan_text:
        st.warning(f"{label} → memakai **Seq Scan** (baca seluruh tabel baris per baris)")

    waktu = re.search(r"Execution Time:\s*([\d.]+)\s*ms", plan_text)
    if waktu:
        st.metric("Execution Time", f"{waktu.group(1)} ms")


def index_sudah_ada(nama_index):
    rows = run_query(
        "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s",
        (nama_index,)
    )
    return len(rows) > 0


def toggle_index_scan(aktif: bool):
    """aktif=False -> paksa planner pilih Seq Scan walau index ada."""
    if aktif:
        run_execute("SET enable_indexscan = on; SET enable_bitmapscan = on;")
    else:
        run_execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")


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

        # ════════════════════════════════════════════════════════════════════
        #  SUB-SECTION: COBA OPTIMASI QUERY (EXPLAIN ANALYZE & INDEX)
        # ════════════════════════════════════════════════════════════════════
        st.divider()
        st.subheader("Coba Optimasi Query — Index Scan vs Seq Scan")
        st.caption("Analisis performa query PostgreSQL pada Sistem Informasi Hidden Kost menggunakan EXPLAIN ANALYZE.")

        opt1, opt2, opt3 = st.tabs([
            "1. Filter Status Kamar",
            "2. Exact Match vs LIKE",
            "3. Foreign Key (Before/After Index)",
        ])

        # ── Skenario 1: Filter status kamar (index sudah ada) ──────────────
        with opt1:
            st.markdown("""
            Query ini sama dengan filter **Status** di atas. Kolom `kamar.status`
            sudah punya index (`index_status_kamar`) sejak awal, jadi planner
            seharusnya langsung memilih **Index Scan**.
            """)

            status_pilih = st.selectbox(
                "Pilih status kamar:", ["Kosong", "Sedang disewa"], key="o1_status"
            )
            sql_o1 = "SELECT * FROM kamar WHERE status = %s::status_kamar"

            colA, colB = st.columns(2)
            with colA:
                if st.button("Jalankan (Normal, pakai index)", key="o1_normal"):
                    toggle_index_scan(True)
                    plan = run_explain(sql_o1, (status_pilih,))
                    tampilkan_plan(plan, "Kondisi normal")
            with colB:
                if st.button("Jalankan (Paksa Seq Scan)", key="o1_force"):
                    toggle_index_scan(False)
                    plan = run_explain(sql_o1, (status_pilih,))
                    toggle_index_scan(True)
                    tampilkan_plan(plan, "Index dimatikan paksa")

        # ── Skenario 2: Exact match vs LIKE ──────────────────────────────────
        with opt2:
            st.markdown("""
            Index `index_nama_penyewa` adalah B-Tree biasa. B-Tree **hanya
            efektif untuk pencarian exact match (`=`)**. Begitu dipakai
            `LIKE '%kata%'` (wildcard di depan), index ini **tidak terpakai**
            dan otomatis jadi Seq Scan.
            """)

            contoh_nama = run_query("SELECT nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")
            nama_default = contoh_nama[0]["nama_lengkap"] if contoh_nama else "Penyewa ke-1"

            nama_cari = st.text_input(
                "Cari nama (isi nama lengkap dari data):", value=nama_default, key="o2_nama"
            )

            colC, colD = st.columns(2)
            with colC:
                if st.button("Jalankan Exact Match ( = )", key="o2_exact"):
                    plan = run_explain(
                        "SELECT * FROM profil_penyewa WHERE nama_lengkap = %s", (nama_cari,)
                    )
                    tampilkan_plan(plan, "WHERE nama_lengkap = ...")
            with colD:
                if st.button("Jalankan LIKE ( %...% )", key="o2_like"):
                    plan = run_explain(
                        "SELECT * FROM profil_penyewa WHERE nama_lengkap LIKE %s", (f"%{nama_cari}%",)
                    )
                    tampilkan_plan(plan, "WHERE nama_lengkap LIKE '%...%'")

        # ── Skenario 3: FK sewa.id_kamar belum ada index ─────────────────────
        with opt3:
            st.markdown("""
            Foreign key di PostgreSQL **tidak otomatis dapat index** (berbeda
            dengan Primary Key). Kolom `sewa.id_kamar` dipakai untuk
            menampilkan riwayat sewa per kamar, tapi belum ada index-nya.
            Bandingkan performa **sebelum** dan **sesudah** index dibuat.
            """)

            ada_index_kamar = index_sudah_ada("index_id_kamar_sewa")
            if ada_index_kamar:
                st.info("Index `index_id_kamar_sewa` sudah dibuat.")
            else:
                st.warning("Index `index_id_kamar_sewa` **belum ada** — query di bawah seharusnya Seq Scan.")

            contoh_kamar = run_query("SELECT id_kamar, nomor FROM kamar ORDER BY id_kamar LIMIT 1")
            id_kamar_contoh = contoh_kamar[0]["id_kamar"] if contoh_kamar else 1
            nomor_contoh = contoh_kamar[0]["nomor"] if contoh_kamar else "-"

            id_kamar_input = st.number_input(
                f"id_kamar (contoh: {id_kamar_contoh} = {nomor_contoh}):",
                min_value=1, value=int(id_kamar_contoh), key="o3_id"
            )

            colE, colF = st.columns(2)
            with colE:
                if st.button("Jalankan EXPLAIN ANALYZE", key="o3_run"):
                    plan = run_explain("SELECT * FROM sewa WHERE id_kamar = %s", (id_kamar_input,))
                    tampilkan_plan(plan, "Sebelum/sesudah index")
            with colF:
                if not ada_index_kamar:
                    if st.button("Buat Index Sekarang", key="o3_create"):
                        try:
                            run_execute("CREATE INDEX index_id_kamar_sewa ON sewa(id_kamar)")
                            st.success("Index berhasil dibuat. Jalankan ulang EXPLAIN ANALYZE di atas untuk lihat perubahannya.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal membuat index: {e}")
                else:
                    if st.button("Hapus Index (untuk demo ulang)", key="o3_drop"):
                        try:
                            run_execute("DROP INDEX index_id_kamar_sewa")
                            st.success("Index dihapus.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menghapus index: {e}")

            st.divider()
            st.markdown("**Ringkasan index aktif di tabel `kamar` & `sewa`:**")
            sql_idx = """
                SELECT tablename AS "Tabel", indexname AS "Nama Index", indexdef AS "Definisi"
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename IN ('kamar', 'sewa')
                ORDER BY tablename, indexname
            """
            df_idx = pd.DataFrame(run_query(sql_idx))
            if not df_idx.empty:
                st.dataframe(df_idx, use_container_width=True, hide_index=True)

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
            SELECT rm.id_request_maintenance AS "ID",
                   pp.nama_lengkap AS "Penyewa",
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

        st.divider()
        st.subheader("Kelola Maintenance")

        pending = run_query("""
            SELECT rm.id_request_maintenance, rm.deskripsi, pp.nama_lengkap,
                   COALESCE(rv.status::TEXT, 'Belum ditangani') AS status
            FROM request_maintenance rm
            JOIN profil_penyewa pp ON rm.id_penyewa = pp.id_penyewa
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rv.status IS NULL OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
            ORDER BY rm.id_request_maintenance DESC
        """)

        if not pending:
            st.success("Semua maintenance sudah ditangani / selesai.")
        else:
            opsi = {
                f"#{p['id_request_maintenance']} – {p['nama_lengkap']} – {p['deskripsi']} ({p['status']})": p
                for p in pending
            }
            pilih = st.selectbox("Pilih request untuk dikelola:", list(opsi.keys()), key="pilih_maint")
            data_pilih = opsi[pilih]

            status_baru = st.selectbox(
                "Ubah status menjadi:",
                ["Tertunda", "Sedang dikerjakan", "Selesai"],
                key="status_baru_maint"
            )

            if st.button("Update Status", use_container_width=True, type="primary", key="btn_update_maint"):
                try:
                    existing = run_query(
                        "SELECT id_riwayat_maintenance FROM riwayat_maintenance WHERE id_request_maintenance = %s",
                        (data_pilih["id_request_maintenance"],)
                    )

                    if status_baru == "Tertunda":
                        if existing:
                            run_execute(
                                "UPDATE riwayat_maintenance SET status = 'Tertunda', tanggal_mulai = NULL, tanggal_selesai = NULL WHERE id_request_maintenance = %s",
                                (data_pilih["id_request_maintenance"],)
                            )
                        else:
                            run_execute(
                                "INSERT INTO riwayat_maintenance (status, id_request_maintenance) VALUES ('Tertunda', %s)",
                                (data_pilih["id_request_maintenance"],)
                            )
                    elif status_baru == "Sedang dikerjakan":
                        if existing:
                            run_execute(
                                "UPDATE riwayat_maintenance SET status = 'Sedang dikerjakan', tanggal_mulai = CURRENT_DATE, tanggal_selesai = NULL WHERE id_request_maintenance = %s",
                                (data_pilih["id_request_maintenance"],)
                            )
                        else:
                            run_execute(
                                "INSERT INTO riwayat_maintenance (tanggal_mulai, status, id_request_maintenance) VALUES (CURRENT_DATE, 'Sedang dikerjakan', %s)",
                                (data_pilih["id_request_maintenance"],)
                            )
                    else:  # Selesai
                        if existing:
                            run_execute(
                                "UPDATE riwayat_maintenance SET status = 'Selesai', tanggal_mulai = COALESCE(tanggal_mulai, CURRENT_DATE), tanggal_selesai = CURRENT_DATE WHERE id_request_maintenance = %s",
                                (data_pilih["id_request_maintenance"],)
                            )
                        else:
                            run_execute(
                                "INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance) VALUES (CURRENT_DATE, CURRENT_DATE, 'Selesai', %s)",
                                (data_pilih["id_request_maintenance"],)
                            )

                    st.success(f"Status diubah menjadi '{status_baru}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal mengubah status: {e}")


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
        sql = """
            SELECT s.id_sewa,
                   k.nomor AS "Kamar",
                   ko.nama_kos AS "Kos",
                   tk.kategori AS "Tipe",
                   tk.harga_sewa AS harga,
                   s.tanggal_mulai AS "Mulai",
                   s.tanggal_akhir AS "Akhir",
                   (s.tanggal_akhir - CURRENT_DATE) AS "Sisa Hari",
                   COALESCE(bayar.jumlah_bulan_bayar, 0) AS jumlah_bulan_bayar,
                   (s.tanggal_mulai + (COALESCE(bayar.jumlah_bulan_bayar, 0) * INTERVAL '1 month'))::date AS jatuh_tempo
            FROM sewa s
            JOIN kamar k ON s.id_kamar = k.id_kamar
            JOIN kos ko ON k.id_kos = ko.id_kos
            JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS jumlah_bulan_bayar
                FROM pembayaran pb
                JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
                WHERE pb.id_sewa = s.id_sewa AND per.status = 'Berhasil'
            ) bayar ON TRUE
            WHERE s.id_penyewa = %s
              AND s.tanggal_akhir >= CURRENT_DATE
            ORDER BY s.tanggal_mulai DESC
        """
        rows = run_query(sql, (id_penyewa,))
        df_sewa = pd.DataFrame(rows)

        if df_sewa.empty:
            st.info("Tidak ada sewa aktif saat ini.")
        else:
            today = datetime.date.today()

            # ── Kartu jatuh tempo per sewa ──────────────────────────────────
            for _, row in df_sewa.iterrows():
                jatuh_tempo = row["jatuh_tempo"]
                sisa_hari_bayar = (jatuh_tempo - today).days

                cols = st.columns(4)
                cols[0].metric("Kamar", f"{row['Kamar']} ({row['Kos']})")
                cols[1].metric("Mulai Sewa", row["Mulai"].strftime("%d-%m-%Y"))
                cols[2].metric("Jatuh Tempo Bayar", jatuh_tempo.strftime("%d-%m-%Y"))
                if sisa_hari_bayar <= 7:
                    cols[3].metric("Sisa Waktu Bayar", f"{sisa_hari_bayar} hari", delta="Segera bayar!", delta_color="inverse")
                else:
                    cols[3].metric("Sisa Waktu Bayar", f"{sisa_hari_bayar} hari")
                st.divider()

            # Display table (hide internal columns)
            df_show = df_sewa.drop(columns=["id_sewa", "harga", "jumlah_bulan_bayar", "jatuh_tempo"])
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            # ── Riwayat Pembayaran ────────────────────────────────────────────
            st.divider()
            st.subheader("Riwayat Pembayaran")
            sql_bayar = """
                SELECT k.nomor AS "Kamar",
                       pb.nominal AS "Nominal (Rp)",
                       pb.metode_bayar::TEXT AS "Metode",
                       per.periode_bayar AS "Periode",
                       per.status::TEXT AS "Status"
                FROM sewa s
                JOIN kamar k ON s.id_kamar = k.id_kamar
                JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
                JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
                WHERE s.id_penyewa = %s
                ORDER BY per.periode_bayar DESC
            """
            rows_bayar = run_query(sql_bayar, (id_penyewa,))
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
                sewa_options = {
                    f"{row['Kamar']} - {row['Kos']} (Rp {row['harga']:,}/bulan) - Jatuh tempo {row['jatuh_tempo'].strftime('%d-%m-%Y')}": row
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

                        # Insert periode untuk setiap bulan, mulai dari jatuh tempo berjalan
                        jatuh_tempo_awal = sewa_data["jatuh_tempo"]
                        for i in range(jumlah_bulan):
                            periode = (pd.Timestamp(jatuh_tempo_awal) + pd.DateOffset(months=i)).strftime("%Y-%m")
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
        sql = """
            SELECT rm.deskripsi AS "Keluhan",
                   COALESCE(rv.status::TEXT, 'Menunggu') AS "Status",
                   COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
                   COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
            FROM request_maintenance rm
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rm.id_penyewa = %s
            ORDER BY rv.status NULLS FIRST
        """
        rows = run_query(sql, (id_penyewa,))
        df = pd.DataFrame(rows)

        if df.empty:
            st.success("Tidak ada request maintenance.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Ajukan Maintenance Baru")
        with st.form("form_maintenance", clear_on_submit=True):
            keluhan = st.text_area(
                "Deskripsi keluhan:",
                placeholder="Contoh: Lampu kamar mati, AC tidak dingin, keran bocor, dll."
            )
            submitted_maint = st.form_submit_button("Ajukan")
            if submitted_maint:
                if keluhan.strip() == "":
                    st.warning("Deskripsi keluhan tidak boleh kosong.")
                else:
                    try:
                        run_execute(
                            "INSERT INTO request_maintenance (deskripsi, id_penyewa) VALUES (%s, %s)",
                            (keluhan.strip(), id_penyewa)
                        )
                        st.success("Request maintenance berhasil diajukan.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal mengajukan: {e}")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("ABD KELOMPOK 2 @2026")