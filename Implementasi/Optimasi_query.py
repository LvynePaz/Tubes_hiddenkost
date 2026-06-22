import re, streamlit as st, pandas as pd
from db import run_query, run_execute

def _conn():
    from db import get_connection
    return get_connection()

def _explain(sql, params=None, force_seq=False):
    conn = _conn()
    with conn.cursor() as cur:
        if force_seq:
            cur.execute("SET enable_indexscan = off")
            cur.execute("SET enable_bitmapscan = off")
            cur.execute("SET enable_indexonlyscan = off")
        try:
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}", params)
            rows = [r[0] for r in cur.fetchall()]
        finally:
            if force_seq:
                try:
                    cur.execute("SET enable_indexscan = on")
                    cur.execute("SET enable_bitmapscan = on")
                    cur.execute("SET enable_indexonlyscan = on")
                except Exception: pass
        return rows

def _algo(lines):
    txt = "\n".join(lines)
    if "Index Only Scan" in txt: return "Index Only Scan"
    if "Bitmap Index Scan" in txt or "Bitmap Heap Scan" in txt: return "Bitmap Index Scan"
    if "Index Scan" in txt: return "Index Scan"
    if "Seq Scan" in txt: return "Seq Scan"
    return "Unknown"

def _waktu(lines):
    m = re.search(r"Execution Time:\s*([\d.]+)", "\n".join(lines))
    return float(m.group(1)) if m else None

def _cost(lines):
    if lines:
        m = re.search(r"cost=([\d.]+)\.\.([\d.]+)", lines[0])
        if m: return f"{m.group(1)}..{m.group(2)}"
    return "-"

# Query yang diuji
QUERIES = [
    ("Sewa aktif per penyewa",
     "SELECT * FROM sewa WHERE id_penyewa = %s AND tanggal_akhir >= CURRENT_DATE",
     lambda: (run_query("SELECT id_penyewa FROM profil_penyewa LIMIT 1")[0]["id_penyewa"],),
     "Filter FK id_penyewa — high selectivity, 1-2 baris dari ribuan",
     [("idx_sewa_penyewa_tglakhir", "CREATE INDEX IF NOT EXISTS idx_sewa_penyewa_tglakhir ON sewa(id_penyewa, tanggal_akhir)")]),

    ("Sewa aktif per kamar",
     "SELECT * FROM sewa WHERE id_kamar = %s AND tanggal_akhir >= CURRENT_DATE",
     lambda: (run_query("SELECT id_kamar FROM kamar LIMIT 1")[0]["id_kamar"],),
     "Filter FK id_kamar — 1 kamar punya 1-3 sewa",
     [("idx_sewa_kamar_tglakhir", "CREATE INDEX IF NOT EXISTS idx_sewa_kamar_tglakhir ON sewa(id_kamar, tanggal_akhir)")]),

    ("Semua sewa masih aktif",
     "SELECT id_sewa, id_kamar FROM sewa WHERE tanggal_akhir >= CURRENT_DATE",
     lambda: (),
     "Range query tanggal — banyak baris cocok, bitmap scan per page",
     [("idx_sewa_tanggal_akhir", "CREATE INDEX IF NOT EXISTS idx_sewa_tanggal_akhir ON sewa(tanggal_akhir)")]),

    ("Pembayaran per sewa",
     "SELECT * FROM pembayaran WHERE id_sewa = %s",
     lambda: (run_query("SELECT id_sewa FROM sewa LIMIT 1")[0]["id_sewa"],),
     "FK id_sewa sangat selektif — 1 sewa = 1 pembayaran",
     [("idx_pembayaran_id_sewa", "CREATE INDEX IF NOT EXISTS idx_pembayaran_id_sewa ON pembayaran(id_sewa)")]),
]

QUERY_MONITORING = [
    ("Sewa aktif per penyewa",
     "SELECT * FROM sewa WHERE id_penyewa = %s AND tanggal_akhir >= CURRENT_DATE",
     lambda: (run_query("SELECT id_penyewa FROM profil_penyewa LIMIT 1")[0]["id_penyewa"],)),
    ("Sewa aktif per kamar",
     "SELECT * FROM sewa WHERE id_kamar = %s AND tanggal_akhir >= CURRENT_DATE",
     lambda: (run_query("SELECT id_kamar FROM kamar LIMIT 1")[0]["id_kamar"],)),
    ("Semua sewa masih aktif",
     "SELECT id_sewa, id_kamar FROM sewa WHERE tanggal_akhir >= CURRENT_DATE",
     lambda: ()),
    ("Cari penyewa by nama",
     "SELECT * FROM profil_penyewa WHERE nama_lengkap = %s",
     lambda: (run_query("SELECT nama_lengkap FROM profil_penyewa LIMIT 1")[0]["nama_lengkap"],)),
    ("Cari penyewa by status",
     "SELECT * FROM profil_penyewa WHERE status = 'Aktif'",
     lambda: ()),
    ("Cari kamar by nomor",
     "SELECT * FROM kamar WHERE nomor = %s",
     lambda: (run_query("SELECT nomor FROM kamar LIMIT 1")[0]["nomor"],)),
    ("Pembayaran per sewa",
     "SELECT * FROM pembayaran WHERE id_sewa = %s",
     lambda: (run_query("SELECT id_sewa FROM sewa LIMIT 1")[0]["id_sewa"],)),
    ("Periode per pembayaran",
     "SELECT * FROM periode_pembayaran WHERE id_pembayaran = %s",
     lambda: (run_query("SELECT id_pembayaran FROM pembayaran LIMIT 1")[0]["id_pembayaran"],)),
    ("Maintenance per penyewa",
     "SELECT * FROM request_maintenance WHERE id_penyewa = %s",
     lambda: (run_query("SELECT id_penyewa FROM request_maintenance LIMIT 1")[0]["id_penyewa"],)),
]


def render():
    st.title("Optimasi Query — Hidden Kost")
    st.caption("Identifikasi query lambat, analisis execution plan, benchmarking sebelum & sesudah optimasi")

    # Statistik dataset
    try:
        stats = {
            "sewa": run_query("SELECT COUNT(*) AS n FROM sewa")[0]["n"],
            "penyewa": run_query("SELECT COUNT(*) AS n FROM profil_penyewa")[0]["n"],
            "kamar": run_query("SELECT COUNT(*) AS n FROM kamar")[0]["n"],
            "pembayaran": run_query("SELECT COUNT(*) AS n FROM pembayaran")[0]["n"],
        }
    except Exception as e:
        st.error(f"Gagal koneksi: {e}"); return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baris Sewa", f"{stats['sewa']:,}")
    c2.metric("Profil Penyewa", f"{stats['penyewa']:,}")
    c3.metric("Kamar", f"{stats['kamar']:,}")
    c4.metric("Pembayaran", f"{stats['pembayaran']:,}")
    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "Benchmarking Sebelum & Sesudah",
        "Monitoring Query",
        "Index Aktif",
    ])

    # ── TAB 1: BENCHMARKING ──
    with tab1:
        st.subheader("Benchmarking — Sebelum vs Sesudah Index")
        st.caption("Bandingkan performa query tanpa index (Seq Scan dipaksa) vs dengan index (planner bebas)")

        pilihan = st.selectbox("Pilih Query:", [q[0] for q in QUERIES], key="bench_q")
        idx = [q[0] for q in QUERIES].index(pilihan)
        label, sql, param_fn, alasan, indexes = QUERIES[idx]

        st.code(sql.replace("%s", "[id]"), language="sql")

        if st.button("Jalankan Benchmarking", type="primary", key="btn_bench"):
            params = param_fn()
            p = params if params else None

            run_execute("ANALYZE sewa")
            run_execute("ANALYZE pembayaran")

            # SEBELUM — paksa Seq Scan
            st.markdown("#### Sebelum Index (Seq Scan dipaksa)")
            plan_before = _explain(sql, p, force_seq=True)
            algo_b = _algo(plan_before)
            waktu_b = _waktu(plan_before)
            cost_b = _cost(plan_before)

            cb1, cb2, cb3 = st.columns(3)
            cb1.metric("Algoritma", algo_b)
            cb2.metric("Waktu", f"{waktu_b:.3f} ms" if waktu_b else "-")
            cb3.metric("Cost", cost_b)
            with st.expander("EXPLAIN output — Sebelum"):
                st.code("\n".join(plan_before), language="sql")

            # Buat index
            for nama, ddl in indexes:
                run_execute(ddl)
            run_execute("ANALYZE sewa")
            run_execute("ANALYZE pembayaran")
            st.success(f"Index dibuat: {', '.join(n for n,_ in indexes)}")

            # SESUDAH — planner bebas
            st.markdown("#### Sesudah Index (planner bebas)")
            plan_after = _explain(sql, p, force_seq=False)
            algo_a = _algo(plan_after)
            waktu_a = _waktu(plan_after)
            cost_a = _cost(plan_after)

            ca1, ca2, ca3 = st.columns(3)
            ca1.metric("Algoritma", algo_a)
            ca2.metric("Waktu", f"{waktu_a:.3f} ms" if waktu_a else "-")
            ca3.metric("Cost", cost_a)
            with st.expander("EXPLAIN output — Sesudah"):
                st.code("\n".join(plan_after), language="sql")

            # Tabel perbandingan
            st.divider()
            st.markdown("#### Perbandingan")
            df_cmp = pd.DataFrame([
                {"Kondisi": "Sebelum (Seq Scan)", "Algoritma": algo_b,
                 "Waktu (ms)": f"{waktu_b:.3f}" if waktu_b else "-", "Cost": cost_b},
                {"Kondisi": "Sesudah (Index)", "Algoritma": algo_a,
                 "Waktu (ms)": f"{waktu_a:.3f}" if waktu_a else "-", "Cost": cost_a},
            ])
            st.dataframe(df_cmp, use_container_width=True, hide_index=True)

            if waktu_b and waktu_a and waktu_a > 0:
                st.success(f"Peningkatan: {waktu_b/waktu_a:.1f}x lebih cepat")

            st.markdown(f"**Alasan:** {alasan}")

    # ── TAB 2: MONITORING ──
    with tab2:
        st.subheader("Monitoring Performa Query")
        st.caption("Eksekusi semua query sistem, lihat algoritma dan waktu yang dipilih PostgreSQL")

        if st.button("Jalankan Monitoring", type="primary", key="btn_mon"):
            hasil = []
            bar = st.progress(0)

            for i, (label, sql, param_fn) in enumerate(QUERY_MONITORING):
                try:
                    params = param_fn()
                    plan = _explain(sql, params if params else None)
                    algo = _algo(plan)
                    waktu = _waktu(plan)
                    cost = _cost(plan)
                except Exception as e:
                    algo, waktu, cost, plan = str(e), None, "-", []
                hasil.append((label, algo, waktu, cost, plan))
                bar.progress((i + 1) / len(QUERY_MONITORING))
            bar.empty()

            # Ringkasan
            n_idx = sum(1 for h in hasil if "Index" in h[1] and "Bitmap" not in h[1])
            n_bmp = sum(1 for h in hasil if "Bitmap" in h[1])
            n_seq = sum(1 for h in hasil if "Seq" in h[1])

            m1, m2, m3 = st.columns(3)
            m1.metric("Index Scan", f"{n_idx} query")
            m2.metric("Bitmap Scan", f"{n_bmp} query")
            m3.metric("Seq Scan", f"{n_seq} query")
            st.divider()

            # Tabel
            df = pd.DataFrame([
                {"Query": h[0], "Algoritma": h[1],
                 "Waktu (ms)": f"{h[2]:.3f}" if h[2] else "-", "Cost": h[3]}
                for h in hasil
            ])

            def warna(val):
                if "Index Only" in val: return "background-color:#0a2010;color:#86efac"
                if "Index" in val: return "background-color:#0a1f12;color:#22c55e"
                if "Bitmap" in val: return "background-color:#0a1520;color:#38bdf8"
                if "Seq" in val: return "background-color:#1f150a;color:#f59e0b"
                return ""

            st.dataframe(df.style.applymap(warna, subset=["Algoritma"]),
                         use_container_width=True, hide_index=True)



    # ── TAB 3: INDEX AKTIF ──
    with tab3:
        st.subheader("Index Aktif di Database")
        df_idx = pd.DataFrame(run_query(
            "SELECT tablename AS \"Tabel\", indexname AS \"Index\", indexdef AS \"Definisi\" "
            "FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname"
        ))
        if not df_idx.empty:
            st.dataframe(df_idx, use_container_width=True, hide_index=True)
            st.caption(f"Total {len(df_idx)} index")

    st.divider()
    st.caption("ABD KELOMPOK 2 @2026")

if __name__ == "__main__" or True:
    render()