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
    .algo-card {
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        border-left: 4px solid;
    }
    .algo-index {
        background: #0f2d1f;
        border-color: #22c55e;
    }
    .algo-seq {
        background: #2d1f0f;
        border-color: #f59e0b;
    }
    .algo-bitmap {
        background: #0f1f2d;
        border-color: #38bdf8;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "role" not in st.session_state:
    st.session_state.role = "Pemilik"
if "halaman" not in st.session_state:
    st.session_state.halaman = "Dashboard"

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
    halaman = st.radio(
        "Halaman:",
        ["Dashboard", "Optimasi Query"],
        index=0 if st.session_state.halaman == "Dashboard" else 1,
        key="halaman_radio",
    )
    st.session_state.halaman = halaman

    st.divider()
    st.caption("KELOMPOK 2 @2026")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════════════════════
def tampilkan_plan(plan_lines, label=""):
    plan_text = "\n".join(plan_lines)
    st.code(plan_text, language="sql")

    if "Index Scan" in plan_text or "Index Only Scan" in plan_text or "Bitmap Index Scan" in plan_text:
        st.success(f"{label} → memakai **Index Scan**")
    elif "Seq Scan" in plan_text:
        st.warning(f"{label} → memakai **Seq Scan** (baca seluruh tabel)")

    waktu = re.search(r"Execution Time:\s*([\d.]+)\s*ms", plan_text)
    if waktu:
        st.metric("Execution Time", f"{waktu.group(1)} ms")


def index_sudah_ada(nama_index):
    rows = run_query(
        "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s",
        (nama_index,)
    )
    return len(rows) > 0


def ekstrak_algoritma(plan_lines):
    """Ekstrak algoritma utama dari EXPLAIN ANALYZE output."""
    plan_text = "\n".join(plan_lines)
    if "Index Only Scan" in plan_text:
        return "Index Only Scan", "index"
    elif "Bitmap Index Scan" in plan_text or "Bitmap Heap Scan" in plan_text:
        return "Bitmap Index Scan", "bitmap"
    elif "Index Scan" in plan_text:
        return "Index Scan", "index"
    elif "Seq Scan" in plan_text:
        return "Seq Scan", "seq"
    return "Unknown", "seq"


def ekstrak_waktu(plan_lines):
    plan_text = "\n".join(plan_lines)
    waktu = re.search(r"Execution Time:\s*([\d.]+)\s*ms", plan_text)
    return float(waktu.group(1)) if waktu else None


# ══════════════════════════════════════════════════════════════════════════════
#  OPTIMASI QUERY PAGE
# ══════════════════════════════════════════════════════════════════════════════
if halaman == "Optimasi Query":
    st.title("Optimasi Query — Index Scan vs Seq Scan")
    st.caption("PostgreSQL otomatis memilih algoritma terbaik. Halaman ini membuktikannya.")
    st.divider()

    sewa_count = run_query("SELECT COUNT(*) AS n FROM sewa")[0]["n"]
    penyewa_count = run_query("SELECT COUNT(*) AS n FROM profil_penyewa")[0]["n"]

    c1, c2 = st.columns(2)
    c1.metric("Total Data Sewa", f"{sewa_count:,} baris")
    c2.metric("Total Data Penyewa", f"{penyewa_count:,} baris")
    st.divider()

    # ── Section 1: Perbandingan Otomatis ──────────────────────────────────────
    st.subheader("Perbandingan Otomatis — Database Pilih Sendiri")

    if st.button("Jalankan Semua Perbandingan", type="primary", key="auto_run_all"):

        # --- Skenario 1: Cari sewa per penyewa ---
        st.markdown("---")
        st.markdown("### 1. Cari Riwayat Sewa per Penyewa")
        contoh_p = run_query("SELECT id_penyewa FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")
        id_p = contoh_p[0]["id_penyewa"] if contoh_p else 1
        sql_s1 = "SELECT * FROM sewa WHERE id_penyewa = %s"

        idx_name_1 = "index_id_penyewa_sewa"
        ada_1 = index_sudah_ada(idx_name_1)

        colX, colY = st.columns(2)
        with colX:
            st.markdown("**Tanpa Index (Seq Scan)**")
            if ada_1:
                run_execute(f"DROP INDEX {idx_name_1}")
            run_execute("ANALYZE sewa")
            plan_before = run_explain(sql_s1, (id_p,))
            tampilkan_plan(plan_before, "Tanpa index")

        with colY:
            st.markdown("**Dengan Index (Index Scan)**")
            run_execute(f"CREATE INDEX {idx_name_1} ON sewa(id_penyewa)")
            run_execute("ANALYZE sewa")
            plan_after = run_explain(sql_s1, (id_p,))
            tampilkan_plan(plan_after, "Dengan index")

        # --- Skenario 2: Cari nama exact vs LIKE ---
        st.markdown("---")
        st.markdown("### 2. Cari Nama Penyewa — Exact vs LIKE")
        contoh_nama = run_query("SELECT nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")
        nama = contoh_nama[0]["nama_lengkap"] if contoh_nama else "Penyewa ke-1"

        colM, colN = st.columns(2)
        with colM:
            st.markdown(f"**Pencarian tepat** (`= '{nama}'`)")
            plan_exact = run_explain("SELECT * FROM profil_penyewa WHERE nama_lengkap = %s", (nama,))
            tampilkan_plan(plan_exact, "Exact match")
        with colN:
            st.markdown(f"**Pencarian sebagian** (`LIKE '%{nama[:5]}%'`)")
            plan_like = run_explain("SELECT * FROM profil_penyewa WHERE nama_lengkap LIKE %s", (f"%{nama[:5]}%",))
            tampilkan_plan(plan_like, "LIKE wildcard")

        # --- Skenario 3: Cari sewa per kamar ---
        st.markdown("---")
        st.markdown("### 3. Cari Riwayat Sewa per Kamar")
        contoh_k = run_query("SELECT id_kamar FROM kamar ORDER BY id_kamar LIMIT 1")
        id_k = contoh_k[0]["id_kamar"] if contoh_k else 1
        sql_s3 = "SELECT * FROM sewa WHERE id_kamar = %s"

        idx_name_3 = "index_id_kamar_sewa"
        ada_3 = index_sudah_ada(idx_name_3)

        colP, colQ = st.columns(2)
        with colP:
            st.markdown("**Tanpa Index (Seq Scan)**")
            if ada_3:
                run_execute(f"DROP INDEX {idx_name_3}")
            run_execute("ANALYZE sewa")
            plan_before_3 = run_explain(sql_s3, (id_k,))
            tampilkan_plan(plan_before_3, "Tanpa index")

        with colQ:
            st.markdown("**Dengan Index (Index Scan)**")
            run_execute(f"CREATE INDEX {idx_name_3} ON sewa(id_kamar)")
            run_execute("ANALYZE sewa")
            plan_after_3 = run_explain(sql_s3, (id_k,))
            tampilkan_plan(plan_after_3, "Dengan index")

        st.markdown("---")
        st.success("Semua perbandingan selesai!")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  Section 2: PostgreSQL Pilih Algoritma Apa untuk HK Kos?  (BARU)
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("PostgreSQL Pilih Algoritma Apa untuk Sistem HK Kos?")
    st.caption(
        "Analisis otomatis seluruh query utama sistem Hidden Kost. "
        "PostgreSQL memilih sendiri algoritma tercepat berdasarkan statistik data aktual."
    )

    # Definisi semua query utama sistem HK Kos
    QUERY_CATALOG = [
        {
            "label": "Sewa aktif per penyewa",
            "konteks": "Dipakai di Dashboard Penyewa → tab Status Sewa",
            "sql": "SELECT * FROM sewa WHERE id_penyewa = %s AND tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (run_query("SELECT id_penyewa FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")[0]["id_penyewa"],),
        },
        {
            "label": "Sewa aktif per kamar",
            "konteks": "Dipakai di sinkronisasi status kamar & Dashboard Pemilik → tab Data Kamar",
            "sql": "SELECT * FROM sewa WHERE id_kamar = %s AND tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (run_query("SELECT id_kamar FROM kamar ORDER BY id_kamar LIMIT 1")[0]["id_kamar"],),
        },
        {
            "label": "Semua sewa yang masih aktif (tanggal_akhir)",
            "konteks": "Dipakai di UPDATE sinkronisasi status kamar — scan semua sewa",
            "sql": "SELECT id_sewa, id_kamar FROM sewa WHERE tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (),
        },
        {
            "label": "Cari penyewa by nama (exact match)",
            "konteks": "Fitur pencarian nama di tab Data Penyewa",
            "sql": "SELECT * FROM profil_penyewa WHERE nama_lengkap = %s",
            "param_fn": lambda: (run_query("SELECT nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")[0]["nama_lengkap"],),
        },
        {
            "label": "Cari penyewa by status",
            "konteks": "Filter penyewa aktif / tidak aktif",
            "sql": "SELECT * FROM profil_penyewa WHERE status = 'Aktif'",
            "param_fn": lambda: (),
        },
        {
            "label": "Cari kamar by status",
            "konteks": "Filter kamar kosong / sedang disewa",
            "sql": "SELECT * FROM kamar WHERE status = 'Kosong'",
            "param_fn": lambda: (),
        },
        {
            "label": "Cari kamar by nomor",
            "konteks": "Lookup kamar spesifik",
            "sql": "SELECT * FROM kamar WHERE nomor = %s",
            "param_fn": lambda: (run_query("SELECT nomor FROM kamar ORDER BY id_kamar LIMIT 1")[0]["nomor"],),
        },
        {
            "label": "Pembayaran per sewa",
            "konteks": "JOIN ke tabel sewa saat tampil riwayat pembayaran",
            "sql": "SELECT * FROM pembayaran WHERE id_sewa = %s",
            "param_fn": lambda: (run_query("SELECT id_sewa FROM sewa ORDER BY id_sewa LIMIT 1")[0]["id_sewa"],),
        },
        {
            "label": "Periode per pembayaran",
            "konteks": "JOIN ke pembayaran saat hitung jumlah bulan bayar",
            "sql": "SELECT * FROM periode_pembayaran WHERE id_pembayaran = %s",
            "param_fn": lambda: (run_query("SELECT id_pembayaran FROM pembayaran ORDER BY id_pembayaran LIMIT 1")[0]["id_pembayaran"],),
        },
        {
            "label": "Request maintenance per penyewa",
            "konteks": "Tab Maintenance di Dashboard Penyewa",
            "sql": "SELECT * FROM request_maintenance WHERE id_penyewa = %s",
            "param_fn": lambda: (run_query("SELECT id_penyewa FROM request_maintenance ORDER BY id_penyewa LIMIT 1")[0]["id_penyewa"],),
        },
    ]

    if st.button("Analisis Semua Query Sistem HK Kos", type="primary", key="analisis_algo"):
        hasil = []
        progress = st.progress(0, text="Menjalankan analisis...")

        for i, q in enumerate(QUERY_CATALOG):
            try:
                params = q["param_fn"]()
                if params:
                    plan = run_explain(q["sql"], params)
                else:
                    plan = run_explain(q["sql"])
                algo, tipe = ekstrak_algoritma(plan)
                waktu = ekstrak_waktu(plan)
                hasil.append({
                    "query": q["label"],
                    "konteks": q["konteks"],
                    "algoritma": algo,
                    "tipe": tipe,
                    "waktu_ms": waktu,
                    "plan": plan,
                })
            except Exception as e:
                hasil.append({
                    "query": q["label"],
                    "konteks": q["konteks"],
                    "algoritma": f"Error: {e}",
                    "tipe": "error",
                    "waktu_ms": None,
                    "plan": [],
                })
            progress.progress((i + 1) / len(QUERY_CATALOG), text=f"Menganalisis: {q['label']}...")

        progress.empty()

        # ── Ringkasan hasil ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Ringkasan — Algoritma yang Dipilih PostgreSQL")

        n_index = sum(1 for h in hasil if h["tipe"] == "index")
        n_bitmap = sum(1 for h in hasil if h["tipe"] == "bitmap")
        n_seq = sum(1 for h in hasil if h["tipe"] == "seq")

        col1, col2, col3 = st.columns(3)
        col1.metric("Index Scan", f"{n_index} query", help="PostgreSQL yakin index lebih cepat karena selectivity tinggi")
        col2.metric("Bitmap Index Scan", f"{n_bitmap} query", help="Dipakai saat banyak baris cocok — gabungan index + heap")
        col3.metric("Seq Scan", f"{n_seq} query", help="PostgreSQL pilih ini karena lebih murah dari index untuk data besar / low selectivity")

        st.markdown("---")

        # ── Tabel ringkasan ────────────────────────────────────────────────
        df_ringkasan = pd.DataFrame([
            {
                "Query": h["query"],
                "Konteks Penggunaan": h["konteks"],
                "Algoritma Dipilih": h["algoritma"],
                "Execution Time (ms)": f"{h['waktu_ms']:.3f}" if h["waktu_ms"] else "-",
            }
            for h in hasil
        ])

        def warna_algo(val):
            if "Index" in val:
                return "background-color: #0f2d1f; color: #22c55e"
            elif "Seq" in val:
                return "background-color: #2d1f0f; color: #f59e0b"
            return ""

        st.dataframe(
            df_ringkasan.style.applymap(warna_algo, subset=["Algoritma Dipilih"]),
            use_container_width=True,
            hide_index=True,
        )

        # ── Detail per query ───────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Detail EXPLAIN ANALYZE per Query")

        ALASAN = {
            "index": "PostgreSQL memilih **Index Scan** karena query memfilter kolom yang punya index dengan **selectivity tinggi** — hanya sedikit baris yang cocok, lebih efisien langsung loncat ke baris via index daripada baca seluruh tabel.",
            "bitmap": "PostgreSQL memilih **Bitmap Index Scan** karena cukup banyak baris yang cocok. Lebih efisien dari Index Scan murni untuk kasus ini — baca index dulu, buat bitmap di memory, baru akses heap sekali.",
            "seq": "PostgreSQL memilih **Seq Scan** karena query ini mengambil **proporsi besar** dari tabel (misal: semua status 'Aktif' = ~80% baris), sehingga biaya membaca index + heap lebih mahal dari langsung scan seluruh tabel.",
        }

        for h in hasil:
            tipe = h["tipe"]
            if tipe == "error":
                continue

            with st.expander(f"{'🟢' if tipe == 'index' else '🟡' if tipe == 'seq' else '🔵'} {h['query']} — {h['algoritma']}"):
                st.caption(f"**Konteks:** {h['konteks']}")
                if h["waktu_ms"]:
                    st.metric("Execution Time", f"{h['waktu_ms']:.3f} ms")

                # Penjelasan alasan
                alasan = ALASAN.get(tipe, "")
                if alasan:
                    if tipe == "index":
                        st.success(alasan)
                    elif tipe == "seq":
                        st.warning(alasan)
                    else:
                        st.info(alasan)

                # EXPLAIN output
                st.code("\n".join(h["plan"]), language="sql")

        # ── Kesimpulan ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Kesimpulan Pilihan Algoritma Sistem HK Kos")

        st.info(
            "**PostgreSQL memilih Index Scan** untuk query yang memfilter berdasarkan ID spesifik "
            "(id_penyewa, id_kamar, id_sewa, id_pembayaran) karena kolom-kolom ini punya **high selectivity** — "
            "hasil query hanya beberapa baris dari ratusan/ribuan baris.\n\n"
            "**PostgreSQL memilih Seq Scan** untuk filter berdasarkan kolom ENUM seperti `status = 'Aktif'` atau "
            "`status = 'Kosong'` karena **low selectivity** — nilai ENUM hanya 2-3 pilihan sehingga banyak baris "
            "cocok, membuat index tidak efisien.\n\n"
            "Ini membuktikan bahwa index di `kamar(status)` dan `profil_penyewa(status)` yang sudah ada di DDL "
            "kemungkinan **tidak dipakai** oleh planner PostgreSQL — sesuai dengan teori bahwa index pada kolom "
            "low cardinality sering diabaikan planner demi Seq Scan yang lebih murah."
        )

    # Semua index yang ada
    st.divider()
    st.subheader("Semua Index di Database")
    sql_idx = """
        SELECT tablename AS "Tabel", indexname AS "Nama Index", indexdef AS "Definisi"
        FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname
    """
    df_idx = pd.DataFrame(run_query(sql_idx))
    if not df_idx.empty:
        st.dataframe(df_idx, use_container_width=True, hide_index=True)
        st.caption(f"Total {len(df_idx)} index (termasuk PK & Unique constraint).")

    st.divider()
    st.caption("ABD KELOMPOK 2 @2026")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.title("HK – Sistem Manajemen Kos")
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
        total_pendapatan = run_query("SELECT COALESCE(SUM(nominal),0) AS n FROM pembayaran")[0]["n"]
        maintenance_pending = run_query("""
            SELECT COUNT(*) AS n FROM request_maintenance rm
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rv.status IS NULL OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
        """)[0]["n"]
    except Exception as e:
        st.error(f"Gagal terhubung ke database: {e}")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Kamar", f"{total_kamar:,}")
    c2.metric("Kamar Kosong", f"{kamar_kosong:,}")
    c3.metric("Kamar Terisi", f"{kamar_terisi:,}")
    c4.metric("Total Pendapatan", f"Rp {total_pendapatan:,.0f}")
    c5.metric("Maintenance", f"{maintenance_pending:,}")

    st.divider()

    tab_kamar, tab_pendapatan, tab_pembayaran, tab_penyewa, tab_maint = st.tabs([
        "Data Kamar", "Pendapatan", "Pembayaran", "Data Penyewa", "Maintenance"
    ])

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
                   COALESCE(pp.id_penyewa::TEXT, '-') AS "ID Penyewa",
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
            WHERE s.tanggal_akhir >= CURRENT_DATE
            ORDER BY per.periode_bayar DESC
            LIMIT 500
        """
        rows = run_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            filter_status_bayar = st.radio("Filter Status:", ["Semua", "Berhasil", "Gagal"], horizontal=True, key="filter_bayar")
            df_filtered = df.copy()
            if filter_status_bayar != "Semua":
                df_filtered = df_filtered[df_filtered["Status Bayar"] == filter_status_bayar]
            df_filtered["Nominal (Rp)"] = df_filtered["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Ringkasan Metode Pembayaran")
            sql_metode = """
                SELECT pb.metode_bayar::TEXT AS "Metode",
                       COUNT(*) AS "Jumlah",
                       SUM(pb.nominal) AS "Total"
                FROM pembayaran pb
                JOIN sewa s ON pb.id_sewa = s.id_sewa
                WHERE s.tanggal_akhir >= CURRENT_DATE
                GROUP BY pb.metode_bayar ORDER BY "Total" DESC
            """
            rows_m = run_query(sql_metode)
            df_m = pd.DataFrame(rows_m)
            if not df_m.empty:
                df_m["Total"] = df_m["Total"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data pembayaran untuk sewa yang aktif.")

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

            status_baru = st.selectbox("Ubah status menjadi:", ["Tertunda", "Sedang dikerjakan", "Selesai"], key="status_baru_maint")

            if st.button("Update Status", use_container_width=True, type="primary", key="btn_update_maint"):
                try:
                    existing = run_query(
                        "SELECT id_riwayat_maintenance FROM riwayat_maintenance WHERE id_request_maintenance = %s",
                        (data_pilih["id_request_maintenance"],)
                    )
                    if status_baru == "Tertunda":
                        if existing:
                            run_execute("UPDATE riwayat_maintenance SET status = 'Tertunda', tanggal_mulai = NULL, tanggal_selesai = NULL WHERE id_request_maintenance = %s", (data_pilih["id_request_maintenance"],))
                        else:
                            run_execute("INSERT INTO riwayat_maintenance (status, id_request_maintenance) VALUES ('Tertunda', %s)", (data_pilih["id_request_maintenance"],))
                    elif status_baru == "Sedang dikerjakan":
                        if existing:
                            run_execute("UPDATE riwayat_maintenance SET status = 'Sedang dikerjakan', tanggal_mulai = CURRENT_DATE, tanggal_selesai = NULL WHERE id_request_maintenance = %s", (data_pilih["id_request_maintenance"],))
                        else:
                            run_execute("INSERT INTO riwayat_maintenance (tanggal_mulai, status, id_request_maintenance) VALUES (CURRENT_DATE, 'Sedang dikerjakan', %s)", (data_pilih["id_request_maintenance"],))
                    else:
                        if existing:
                            run_execute("UPDATE riwayat_maintenance SET status = 'Selesai', tanggal_mulai = COALESCE(tanggal_mulai, CURRENT_DATE), tanggal_selesai = CURRENT_DATE WHERE id_request_maintenance = %s", (data_pilih["id_request_maintenance"],))
                        else:
                            run_execute("INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance) VALUES (CURRENT_DATE, CURRENT_DATE, 'Selesai', %s)", (data_pilih["id_request_maintenance"],))
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

    tab_kamar, tab_sewa, tab_maint = st.tabs(["Kamar Kosong", "Status Sewa", "Maintenance"])

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
            WHERE s.id_penyewa = %s AND s.tanggal_akhir >= CURRENT_DATE
            ORDER BY s.tanggal_mulai DESC
        """
        rows = run_query(sql, (id_penyewa,))
        df_sewa = pd.DataFrame(rows)

        if df_sewa.empty:
            st.info("Tidak ada sewa aktif saat ini.")
        else:
            today = datetime.date.today()
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

            df_show = df_sewa.drop(columns=["id_sewa", "harga", "jumlah_bulan_bayar", "jatuh_tempo"])
            st.dataframe(df_show, use_container_width=True, hide_index=True)

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
                WHERE s.id_penyewa = %s AND s.tanggal_akhir >= CURRENT_DATE
                ORDER BY per.periode_bayar DESC
            """
            rows_bayar = run_query(sql_bayar, (id_penyewa,))
            df_bayar = pd.DataFrame(rows_bayar)
            if df_bayar.empty:
                st.info("Belum ada riwayat pembayaran.")
            else:
                df_bayar["Nominal (Rp)"] = df_bayar["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_bayar, use_container_width=True, hide_index=True)

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
                        run_execute("INSERT INTO pembayaran (nominal, metode_bayar, id_sewa) VALUES (%s, %s, %s)", (total_bayar, metode, id_sewa))
                        new_pb = run_query("SELECT MAX(id_pembayaran) AS id FROM pembayaran")[0]["id"]
                        jatuh_tempo_awal = sewa_data["jatuh_tempo"]
                        for i in range(jumlah_bulan):
                            periode = (pd.Timestamp(jatuh_tempo_awal) + pd.DateOffset(months=i)).strftime("%Y-%m")
                            run_execute("INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran) VALUES (%s, %s, %s)", (periode, "Berhasil", new_pb))
                        st.success(f"Pembayaran berhasil! {jumlah_bulan} bulan, total Rp {total_bayar:,}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal melakukan pembayaran: {e}")

    with tab_maint:
        st.subheader("Request Maintenance Saya")
        sql = """
            SELECT rm.deskripsi AS "Keluhan",
                   COALESCE(rv.status::TEXT, 'Menunggu') AS "Status",
                   COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
                   COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
            FROM request_maintenance rm
            LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
            WHERE rm.id_penyewa = %s ORDER BY rv.status NULLS FIRST
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
            keluhan = st.text_area("Deskripsi keluhan:", placeholder="Contoh: Lampu kamar mati, AC tidak dingin, keran bocor, dll.")
            submitted_maint = st.form_submit_button("Ajukan")
            if submitted_maint:
                if keluhan.strip() == "":
                    st.warning("Deskripsi keluhan tidak boleh kosong.")
                else:
                    try:
                        run_execute("INSERT INTO request_maintenance (deskripsi, id_penyewa) VALUES (%s, %s)", (keluhan.strip(), id_penyewa))
                        st.success("Request maintenance berhasil diajukan.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal mengajukan: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("ABD KELOMPOK 2 @2026")