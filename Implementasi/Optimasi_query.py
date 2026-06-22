import re
import streamlit as st
import pandas as pd
from db import run_query, run_execute, run_explain

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def ekstrak_algoritma(plan_lines):
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
    m = re.search(r"Execution Time:\s*([\d.]+)\s*ms", plan_text)
    return float(m.group(1)) if m else None

def ekstrak_cost(plan_lines):
    """Ambil estimated cost dari baris pertama plan."""
    if plan_lines:
        m = re.search(r"cost=([\d.]+)\.\.([\d.]+)", plan_lines[0])
        if m:
            return f"{m.group(1)}..{m.group(2)}"
    return "-"

def _get_conn():
    from db import get_connection
    return get_connection()

def run_explain_buffers_with_settings(sql, params=None, force_seqscan=False):
    """
    Jalankan EXPLAIN (ANALYZE, BUFFERS) dalam SATU koneksi dan cursor.
    force_seqscan=True → paksa Seq Scan via SET (bukan SET LOCAL karena
    db.py pakai autocommit=True sehingga tidak ada transaksi aktif).
    Setting dikembalikan ke ON setelah EXPLAIN selesai.
    """
    conn = _get_conn()
    rows = []
    with conn.cursor() as cur:
        if force_seqscan:
            cur.execute("SET enable_indexscan = off")
            cur.execute("SET enable_bitmapscan = off")
            cur.execute("SET enable_indexonlyscan = off")
        try:
            if params:
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}", params)
            else:
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}")
            rows = [row[0] for row in cur.fetchall()]
        finally:
            # Selalu kembalikan ke ON meskipun ada exception
            if force_seqscan:
                try:
                    cur.execute("SET enable_indexscan = on")
                    cur.execute("SET enable_bitmapscan = on")
                    cur.execute("SET enable_indexonlyscan = on")
                except Exception:
                    pass
    return rows

def run_explain_buffers(sql, params=None):
    """Alias — jalankan EXPLAIN tanpa memaksa Seq Scan."""
    return run_explain_buffers_with_settings(sql, params, force_seqscan=False)

def paksa_seq_scan(aktif: bool):
    """Tidak dipakai lagi — diganti run_explain_buffers_with_settings."""
    pass

def index_sudah_ada(nama):
    rows = run_query(
        "SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=%s",
        (nama,)
    )
    return len(rows) > 0

def tampilkan_plan_card(plan_lines, mode="index"):
    """Tampilkan EXPLAIN output dengan card berwarna sesuai mode."""
    plan_text = "\n".join(plan_lines)
    algo, tipe = ekstrak_algoritma(plan_lines)
    waktu = ekstrak_waktu(plan_lines)
    cost = ekstrak_cost(plan_lines)

    if tipe == "index":
        warna = "#22c55e"
        bg = "#0a1f12"
        icon = "🟢"
    elif tipe == "bitmap":
        warna = "#38bdf8"
        bg = "#0a1520"
        icon = "🔵"
    else:
        warna = "#f59e0b"
        bg = "#1f150a"
        icon = "🟡"

    st.markdown(
        f"""<div style="border-left:4px solid {warna}; background:{bg};
            border-radius:8px; padding:12px 16px; margin-bottom:8px;">
            <span style="color:{warna}; font-weight:700; font-size:1rem;">
                {icon} {algo}
            </span>
            <span style="color:#94a3b8; font-size:0.85rem; margin-left:16px;">
                Execution Time: <b style="color:#f1f5f9;">{f"{waktu:.3f} ms" if waktu is not None else "-"}</b>
                &nbsp;|&nbsp; Est. Cost: <b style="color:#f1f5f9;">{cost}</b>
            </span>
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("Lihat output EXPLAIN (ANALYZE, BUFFERS)"):
        st.code(plan_text, language="sql")
    return algo, waktu, cost


# ══════════════════════════════════════════════════════════════════════════════
#  DEFINISI QUERY PENGUJIAN
#  Sama persis dengan yang ada di file Explain_analyz_optimasi.sql
# ══════════════════════════════════════════════════════════════════════════════

SKENARIO = [
    {
        "no": "Q1",
        "judul": "Sewa aktif per penyewa",
        "konteks": "Dashboard Penyewa → tab Status Sewa. Dipanggil setiap penyewa login.",
        "sql": "SELECT * FROM sewa WHERE id_penyewa = %s AND tanggal_akhir >= CURRENT_DATE",
        "param_fn": lambda: (
            run_query("SELECT id_penyewa FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")[0]["id_penyewa"],
        ),
        "index_dibuat": [
            ("idx_sewa_penyewa_tglakhir", "CREATE INDEX idx_sewa_penyewa_tglakhir ON sewa(id_penyewa, tanggal_akhir)"),
        ],
        "alasan_index": "Composite index (id_penyewa, tanggal_akhir) menutup kedua kondisi WHERE sekaligus. PostgreSQL dapat melakukan Index Scan langsung ke baris penyewa tertentu yang masih aktif tanpa membaca seluruh tabel.",
    },
    {
        "no": "Q2",
        "judul": "Sewa aktif per kamar",
        "konteks": "Sinkronisasi status kamar & LATERAL subquery di tab Data Kamar.",
        "sql": "SELECT * FROM sewa WHERE id_kamar = %s AND tanggal_akhir >= CURRENT_DATE",
        "param_fn": lambda: (
            run_query("SELECT id_kamar FROM kamar ORDER BY id_kamar LIMIT 1")[0]["id_kamar"],
        ),
        "index_dibuat": [
            ("idx_sewa_kamar_tglakhir", "CREATE INDEX idx_sewa_kamar_tglakhir ON sewa(id_kamar, tanggal_akhir)"),
        ],
        "alasan_index": "Composite index (id_kamar, tanggal_akhir) memungkinkan Index Scan langsung ke kamar tertentu yang sedang aktif. Dipakai intensif saat sinkronisasi massal status 300 kamar sekaligus.",
    },
    {
        "no": "Q3",
        "judul": "Semua sewa yang masih aktif",
        "konteks": "UPDATE sinkronisasi status kamar — scan semua sewa belum berakhir.",
        "sql": "SELECT id_sewa, id_kamar FROM sewa WHERE tanggal_akhir >= CURRENT_DATE",
        "param_fn": lambda: (),
        "index_dibuat": [
            ("idx_sewa_tanggal_akhir", "CREATE INDEX idx_sewa_tanggal_akhir ON sewa(tanggal_akhir)"),
        ],
        "alasan_index": "Index pada tanggal_akhir memungkinkan Bitmap Index Scan — lebih efisien dari Seq Scan karena PostgreSQL membangun bitmap di memory lalu akses heap per page, bukan per baris.",
    },
    {
        "no": "Q4",
        "judul": "Pembayaran per sewa",
        "konteks": "JOIN ke tabel sewa saat menampilkan riwayat pembayaran penyewa.",
        "sql": "SELECT * FROM pembayaran WHERE id_sewa = %s",
        "param_fn": lambda: (
            run_query("SELECT id_sewa FROM sewa ORDER BY id_sewa LIMIT 1")[0]["id_sewa"],
        ),
        "index_dibuat": [
            ("idx_pembayaran_id_sewa", "CREATE INDEX idx_pembayaran_id_sewa ON pembayaran(id_sewa)"),
        ],
        "alasan_index": "FK id_sewa punya high selectivity — 1 sewa biasanya hanya punya 1 pembayaran. Index Scan langsung menunjuk ke 1 baris tanpa scan tabel.",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER HALAMAN
# ══════════════════════════════════════════════════════════════════════════════

def render():
    st.title("Analisis Performa Query — Sistem Hidden Kost")
    st.caption(
        "Pengujian EXPLAIN (ANALYZE, BUFFERS) sebelum dan sesudah index, "
        "sesuai metodologi Bab 6 laporan. PostgreSQL memilih algoritma optimal secara otomatis."
    )

    # ── Statistik data ──────────────────────────────────────────────────────
    try:
        stats = {
            "sewa": run_query("SELECT COUNT(*) AS n FROM sewa")[0]["n"],
            "penyewa": run_query("SELECT COUNT(*) AS n FROM profil_penyewa")[0]["n"],
            "kamar": run_query("SELECT COUNT(*) AS n FROM kamar")[0]["n"],
            "pembayaran": run_query("SELECT COUNT(*) AS n FROM pembayaran")[0]["n"],
        }
    except Exception as e:
        st.error(f"Gagal koneksi database: {e}")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baris Tabel Sewa", f"{stats['sewa']:,}")
    c2.metric("Profil Penyewa", f"{stats['penyewa']:,}")
    c3.metric("Kamar", f"{stats['kamar']:,}")
    c4.metric("Pembayaran", f"{stats['pembayaran']:,}")
    st.divider()

    # ── Pilih skenario ──────────────────────────────────────────────────────
    st.subheader("Pilih Query untuk Dianalisis")
    pilihan = st.selectbox(
        "Query:",
        [f"{s['no']} — {s['judul']}" for s in SKENARIO],
        key="oq_pilih_skenario"
    )
    idx_skenario = [f"{s['no']} — {s['judul']}" for s in SKENARIO].index(pilihan)
    s = SKENARIO[idx_skenario]

    st.markdown(f"**Konteks penggunaan:** {s['konteks']}")
    st.code(s["sql"].replace("%s", "[id]"), language="sql")
    st.divider()

    # ── Tombol jalankan ─────────────────────────────────────────────────────
    if st.button("▶ Jalankan Analisis Sebelum & Sesudah Index", type="primary", key="run_analisis"):

        params = s["param_fn"]()

        # ── STEP 1: ANALYZE supaya statistik tabel terkini ───────────────────
        # Tidak perlu DROP INDEX — paksa Seq Scan cukup via SET LOCAL di Step 2.
        # DROP index sebelumnya terbukti tidak reliable karena PK/FK index
        # lain bisa tetap dipakai planner meskipun index target sudah dihapus.
        run_execute("ANALYZE sewa; ANALYZE pembayaran;")

        # ── STEP 2: SEBELUM INDEX — paksa Seq Scan ─────────────────────────
        st.markdown("### Sebelum Index — Seq Scan (dipaksa)")
        st.caption(
            "Index dinonaktifkan sementara via `SET enable_indexscan = off` "
            "untuk memastikan PostgreSQL menggunakan Seq Scan murni, "
            "bukan bergantung pada index lain yang tersisa (PK, dll)."
        )

        # Paksa Seq Scan dalam satu cursor yang sama supaya SET LOCAL efektif
        if params:
            plan_before = run_explain_buffers_with_settings(s["sql"], params, force_seqscan=True)
        else:
            plan_before = run_explain_buffers_with_settings(s["sql"], force_seqscan=True)

        algo_before, waktu_before, cost_before = tampilkan_plan_card(plan_before, "seq")

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Algoritma", algo_before)
        col_m2.metric("Execution Time", f"{waktu_before:.3f} ms" if waktu_before else "-")
        col_m3.metric("Estimated Cost", cost_before)

        st.divider()

        # ── STEP 3: Buat index ──────────────────────────────────────────────
        for nama_idx, sql_create in s["index_dibuat"]:
            run_execute(sql_create)
        run_execute("ANALYZE sewa; ANALYZE pembayaran;")

        created_names = [n for n, _ in s["index_dibuat"]]
        st.success(f"Index dibuat: `{'`, `'.join(created_names)}`")

        # ── STEP 4: SESUDAH INDEX — biarkan planner pilih sendiri ──────────
        st.markdown("### Sesudah Index — PostgreSQL Pilih Sendiri")
        st.caption(
            "Index scan diaktifkan kembali. PostgreSQL bebas memilih algoritma "
            "terbaik berdasarkan statistik aktual data."
        )

        if params:
            plan_after = run_explain_buffers(s["sql"], params)
        else:
            plan_after = run_explain_buffers(s["sql"])

        algo_after, waktu_after, cost_after = tampilkan_plan_card(plan_after, "index")

        col_m4, col_m5, col_m6 = st.columns(3)
        col_m4.metric("Algoritma", algo_after)
        col_m5.metric("Execution Time", f"{waktu_after:.3f} ms" if waktu_after else "-")
        col_m6.metric("Estimated Cost", cost_after)

        st.divider()

        # ── STEP 5: Tabel perbandingan ──────────────────────────────────────
        st.markdown("### Perbandingan Performa")

        speedup = "-"
        if waktu_before and waktu_after and waktu_after > 0:
            rasio = waktu_before / waktu_after
            speedup = f"{rasio:.1f}× lebih cepat"

        df_perbandingan = pd.DataFrame([
            {
                "Kondisi": "Sebelum Index (Seq Scan)",
                "Algoritma": algo_before,
                "Execution Time (ms)": f"{waktu_before:.3f}" if waktu_before else "-",
                "Estimated Cost": cost_before,
            },
            {
                "Kondisi": "Sesudah Index",
                "Algoritma": algo_after,
                "Execution Time (ms)": f"{waktu_after:.3f}" if waktu_after else "-",
                "Estimated Cost": cost_after,
            },
        ])

        st.dataframe(df_perbandingan, use_container_width=True, hide_index=True)

        if speedup != "-":
            st.success(f"**Peningkatan performa: {speedup}**")

        # ── STEP 6: Penjelasan kenapa index ini dipilih ─────────────────────
        st.divider()
        st.markdown("### Kenapa PostgreSQL Memilih Algoritma Ini?")
        st.info(s["alasan_index"])

        # ── STEP 7: Index yang sekarang aktif ──────────────────────────────
        st.divider()

    # ── Section bawah: semua index aktif + analisis algoritma ──────────────
    st.subheader("Semua Index Aktif di Database")

    df_idx = pd.DataFrame(run_query("""
        SELECT tablename AS "Tabel", indexname AS "Nama Index", indexdef AS "Definisi"
        FROM pg_indexes WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """))
    if not df_idx.empty:
        st.dataframe(df_idx, use_container_width=True, hide_index=True)
        st.caption(f"Total {len(df_idx)} index (termasuk PK & Unique constraint).")

    st.divider()

    # ── Section: analisis otomatis semua query sistem ──────────────────────
    st.subheader("Pilihan Algoritma Optimal — Seluruh Query Sistem HK Kos")
    st.caption(
        "Jalankan semua query OLTP utama sistem dengan index aktif. "
        "PostgreSQL memilih sendiri algoritma terbaik per query."
    )

    QUERY_SISTEM = [
        {
            "label": "Q1 — Sewa aktif per penyewa",
            "sql": "SELECT * FROM sewa WHERE id_penyewa = %s AND tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (run_query("SELECT id_penyewa FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")[0]["id_penyewa"],),
        },
        {
            "label": "Q2 — Sewa aktif per kamar",
            "sql": "SELECT * FROM sewa WHERE id_kamar = %s AND tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (run_query("SELECT id_kamar FROM kamar ORDER BY id_kamar LIMIT 1")[0]["id_kamar"],),
        },
        {
            "label": "Q3 — Semua sewa masih aktif",
            "sql": "SELECT id_sewa, id_kamar FROM sewa WHERE tanggal_akhir >= CURRENT_DATE",
            "param_fn": lambda: (),
        },
        {
            "label": "Q4 — Cari penyewa by nama (exact)",
            "sql": "SELECT * FROM profil_penyewa WHERE nama_lengkap = %s",
            "param_fn": lambda: (run_query("SELECT nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")[0]["nama_lengkap"],),
        },
        {
            "label": "Q5 — Cari penyewa by status",
            "sql": "SELECT * FROM profil_penyewa WHERE status = 'Aktif'",
            "param_fn": lambda: (),
        },
        {
            "label": "Q6 — Cari kamar by status",
            "sql": "SELECT * FROM kamar WHERE status = 'Kosong'",
            "param_fn": lambda: (),
        },
        {
            "label": "Q7 — Cari kamar by nomor",
            "sql": "SELECT * FROM kamar WHERE nomor = %s",
            "param_fn": lambda: (run_query("SELECT nomor FROM kamar ORDER BY id_kamar LIMIT 1")[0]["nomor"],),
        },
        {
            "label": "Q8 — Pembayaran per sewa",
            "sql": "SELECT * FROM pembayaran WHERE id_sewa = %s",
            "param_fn": lambda: (run_query("SELECT id_sewa FROM sewa ORDER BY id_sewa LIMIT 1")[0]["id_sewa"],),
        },
        {
            "label": "Q9 — Periode per pembayaran",
            "sql": "SELECT * FROM periode_pembayaran WHERE id_pembayaran = %s",
            "param_fn": lambda: (run_query("SELECT id_pembayaran FROM pembayaran ORDER BY id_pembayaran LIMIT 1")[0]["id_pembayaran"],),
        },
        {
            "label": "Q10 — Request maintenance per penyewa",
            "sql": "SELECT * FROM request_maintenance WHERE id_penyewa = %s",
            "param_fn": lambda: (run_query("SELECT id_penyewa FROM request_maintenance ORDER BY id_penyewa LIMIT 1")[0]["id_penyewa"],),
        },
    ]

    ALASAN_ALGO = {
        "Index Scan": "Filter kolom punya **high selectivity** (FK/PK/unique). Hanya sedikit baris cocok → PostgreSQL langsung lompat ke baris via index, jauh lebih murah dari baca seluruh tabel.",
        "Bitmap Index Scan": "Banyak baris cocok (range query / proporsi sedang). PostgreSQL bangun bitmap di memory dari index, lalu akses heap **sekali per page** — menghindari random I/O berulang yang terjadi di Index Scan murni.",
        "Seq Scan": "Kolom filter punya **low selectivity** (ENUM 2–3 nilai, atau tabel sangat kecil). Overhead inisialisasi index lebih besar dari manfaatnya — scan linear langsung lebih efisien.",
        "Index Only Scan": "Semua kolom yang dibutuhkan sudah ada di index (covering index). PostgreSQL tidak perlu akses heap sama sekali — tercepat.",
    }

    if st.button("Analisis Semua Query", type="primary", key="run_semua"):
        hasil = []
        bar = st.progress(0, text="Menganalisis query...")

        for i, qs in enumerate(QUERY_SISTEM):
            try:
                params = qs["param_fn"]()
                if params:
                    plan = run_explain_buffers(qs["sql"], params)
                else:
                    plan = run_explain_buffers(qs["sql"])
                algo, tipe = ekstrak_algoritma(plan)
                waktu = ekstrak_waktu(plan)
                cost = ekstrak_cost(plan)
            except Exception as e:
                algo, tipe, waktu, cost, plan = f"Error: {e}", "error", None, "-", []

            hasil.append({
                "label": qs["label"],
                "algo": algo,
                "tipe": tipe,
                "waktu": waktu,
                "cost": cost,
                "plan": plan,
                "alasan": ALASAN_ALGO.get(algo, ""),
            })
            bar.progress((i + 1) / len(QUERY_SISTEM), text=f"Selesai: {qs['label']}")

        bar.empty()

        # Ringkasan metric
        n_index = sum(1 for h in hasil if h["tipe"] == "index")
        n_bitmap = sum(1 for h in hasil if h["tipe"] == "bitmap")
        n_seq = sum(1 for h in hasil if h["tipe"] == "seq")
        n_err = sum(1 for h in hasil if h["tipe"] == "error")

        col1, col2, col3 = st.columns(3)
        col1.metric("Index Scan", f"{n_index} query", delta="High selectivity" if n_index else None)
        col2.metric("Bitmap Index Scan", f"{n_bitmap} query", delta="Range / medium rows" if n_bitmap else None)
        col3.metric("Seq Scan", f"{n_seq} query", delta="Low selectivity / small table" if n_seq else None)

        st.markdown("---")

        # Tabel ringkasan dengan warna
        df_hasil = pd.DataFrame([
            {
                "Query": h["label"],
                "Algoritma Dipilih": h["algo"],
                "Execution Time (ms)": f"{h['waktu']:.3f}" if h["waktu"] else "-",
                "Estimated Cost": h["cost"],
            }
            for h in hasil if h["tipe"] != "error"
        ])

        def warna_algo(val):
            if "Index Only" in val:
                return "background-color: #0a2010; color: #86efac"
            elif "Index" in val:
                return "background-color: #0a1f12; color: #22c55e"
            elif "Bitmap" in val:
                return "background-color: #0a1520; color: #38bdf8"
            elif "Seq" in val:
                return "background-color: #1f150a; color: #f59e0b"
            return ""

        st.dataframe(
            df_hasil.style.applymap(warna_algo, subset=["Algoritma Dipilih"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")

        # Detail per query dengan expander
        st.markdown("### Detail per Query")
        for h in hasil:
            if h["tipe"] == "error":
                continue
            icon = "🟢" if h["tipe"] == "index" else "🔵" if h["tipe"] == "bitmap" else "🟡"
            with st.expander(f"{icon} {h['label']} — **{h['algo']}** ({h['waktu']:.3f} ms)" if h["waktu"] else f"{icon} {h['label']} — {h['algo']}"):
                if h["alasan"]:
                    if h["tipe"] == "index":
                        st.success(h["alasan"])
                    elif h["tipe"] == "bitmap":
                        st.info(h["alasan"])
                    else:
                        st.warning(h["alasan"])
                st.code("\n".join(h["plan"]), language="sql")

        # Kesimpulan
        st.markdown("---")
        st.markdown("### Kesimpulan Pilihan Algoritma")
        st.info(
            "**Index Scan** dipilih untuk query filter berdasarkan FK spesifik (id_penyewa, id_kamar, id_sewa, id_pembayaran) "
            "karena kolom-kolom ini memiliki high selectivity — hanya 1–3 baris yang cocok dari ratusan baris.\n\n"
            "**Bitmap Index Scan** dipilih untuk query range (tanggal_akhir >= CURRENT_DATE) yang mengembalikan banyak baris — "
            "lebih efisien dari Index Scan murni karena menghindari random heap access berulang.\n\n"
            "**Seq Scan** dipilih untuk filter kolom ENUM (status 'Aktif'/'Kosong') karena low cardinality (~80% baris cocok) "
            "dan tabel kecil (request_maintenance 182 baris) — overhead index lebih besar dari manfaatnya. "
            "Index index_status_penyewa dan index_status_kamar yang dibuat di DDL dengan sengaja diabaikan planner."
        )

    st.divider()
    st.caption("ABD KELOMPOK 2 @2026")


# Entry point jika file ini dijalankan langsung
if __name__ == "__main__" or True:
    render()