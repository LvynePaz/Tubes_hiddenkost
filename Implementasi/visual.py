import datetime, streamlit as st, pandas as pd
from db import run_query, run_execute
import oltp_olap_visual as q

st.set_page_config(page_title="Hidden Kost – Dashboard", page_icon="HK", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569; border-radius: 12px;
        padding: 16px 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 0.85rem !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-weight: 700 !important; }
    .role-badge { display:inline-block; padding:4px 14px; border-radius:20px; font-weight:600; font-size:0.85rem; }
    .role-pemilik { background:#1e40af; color:#dbeafe; }
    .role-penyewa { background:#065f46; color:#d1fae5; }
</style>
""", unsafe_allow_html=True)

if "role" not in st.session_state: st.session_state.role = "Pemilik"
if "halaman" not in st.session_state: st.session_state.halaman = "Dashboard"

with st.sidebar:
    st.markdown("## Pilih Role")
    role = st.radio("Masuk sebagai:", ["Pemilik", "Penyewa"],
        index=0 if st.session_state.role == "Pemilik" else 1, key="role_radio")
    st.session_state.role = role
    badge = "role-pemilik" if role == "Pemilik" else "role-penyewa"
    st.markdown(f'<span class="role-badge {badge}">{role}</span>', unsafe_allow_html=True)
    st.divider()
    halaman = st.radio("Halaman:", ["Dashboard", "Optimasi Query"],
        index=0 if st.session_state.halaman == "Dashboard" else 1, key="halaman_radio")
    st.session_state.halaman = halaman
    st.divider()
    st.caption("KELOMPOK 2 @2026")

# Optimasi Query page
if halaman == "Optimasi Query":
    import importlib.util as _ilu, sys as _sys, os as _os
    _dir = _os.path.dirname(_os.path.abspath(__file__))
    _candidates = [f for f in _os.listdir(_dir) if f.lower() == "optimasi_query.py"]
    if not _candidates:
        st.error("File optimasi_query.py tidak ditemukan.")
        st.stop()
    _name = "optimasi_query"
    if _name in _sys.modules: del _sys.modules[_name]
    _spec = _ilu.spec_from_file_location(_name, _os.path.join(_dir, _candidates[0]))
    _mod = _ilu.module_from_spec(_spec)
    _sys.modules[_name] = _mod
    _spec.loader.exec_module(_mod)
    st.stop()

# Auto-sync status kamar (sekali per session)
if "kamar_synced" not in st.session_state:
    try:
        run_execute("""
            UPDATE kamar k SET status = (
                CASE WHEN EXISTS (SELECT 1 FROM sewa s WHERE s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE)
                THEN 'Sedang disewa' ELSE 'Kosong' END
            )::status_kamar
        """)
        st.session_state.kamar_synced = True
    except Exception: pass

st.title("HK – Sistem Manajemen Kos")
st.caption("Dashboard Pemilik" if role == "Pemilik" else "Dashboard Penyewa")
st.divider()

# ── PEMILIK ──
if role == "Pemilik":
    try:
        total_kamar = run_query(q.OLAP_KPI_TOTAL_KAMAR)[0]["n"]
        kamar_kosong = run_query(q.OLAP_KPI_KAMAR_KOSONG)[0]["n"]
        kamar_terisi = run_query(q.OLAP_KPI_KAMAR_TERISI)[0]["n"]
        total_pendapatan = run_query(q.OLAP_KPI_TOTAL_PENDAPATAN)[0]["n"]
        maint_pending = run_query(q.OLAP_KPI_MAINTENANCE_PENDING)[0]["n"]
    except Exception as e:
        st.error(f"Gagal terhubung ke database: {e}"); st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Kamar", f"{total_kamar:,}")
    c2.metric("Kamar Kosong", f"{kamar_kosong:,}")
    c3.metric("Kamar Terisi", f"{kamar_terisi:,}")
    c4.metric("Total Pendapatan", f"Rp {total_pendapatan:,.0f}")
    c5.metric("Maintenance", f"{maint_pending:,}")
    st.divider()

    tab_kamar, tab_pendapatan, tab_pembayaran, tab_penyewa, tab_maint = st.tabs(
        ["Data Kamar", "Pendapatan", "Pembayaran", "Data Penyewa", "Maintenance"])

    with tab_kamar:
        st.subheader("Data Seluruh Kamar")
        df = pd.DataFrame(run_query(q.OLTP_DATA_KAMAR_PEMILIK))
        if not df.empty:
            fk = st.selectbox("Filter Kos:", ["Semua"] + sorted(df["Kos"].unique().tolist()), key="fk")
            fs = st.radio("Filter Status:", ["Semua", "Kosong", "Sedang disewa"], horizontal=True, key="fs")
            df_f = df.copy()
            if fk != "Semua": df_f = df_f[df_f["Kos"] == fk]
            if fs != "Semua": df_f = df_f[df_f["Status"] == fs]
            df_f["Harga (Rp)"] = df_f["Harga (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df_f, use_container_width=True, hide_index=True)
        else: st.info("Belum ada data kamar.")

    with tab_pendapatan:
        st.subheader("Pendapatan per Kos")
        df = pd.DataFrame(run_query(q.OLAP_PENDAPATAN_PER_KOS))
        if not df.empty:
            df["Total Pendapatan"] = df["Total Pendapatan"].apply(lambda x: f"Rp {x:,}")
            df["Rata-rata"] = df["Rata-rata"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("Pendapatan per Tipe Kamar")
        df2 = pd.DataFrame(run_query(q.OLAP_PENDAPATAN_PER_TIPE_KAMAR))
        if not df2.empty:
            df2["Harga Sewa"] = df2["Harga Sewa"].apply(lambda x: f"Rp {x:,}")
            df2["Total Pendapatan"] = df2["Total Pendapatan"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df2, use_container_width=True, hide_index=True)

    with tab_pembayaran:
        st.subheader("Riwayat Pembayaran")
        df = pd.DataFrame(run_query(q.OLTP_RIWAYAT_PEMBAYARAN_PEMILIK))
        if not df.empty:
            fb = st.radio("Filter Status:", ["Semua", "Berhasil", "Gagal"], horizontal=True, key="fb")
            df_f = df.copy()
            if fb != "Semua": df_f = df_f[df_f["Status Bayar"] == fb]
            df_f["Nominal (Rp)"] = df_f["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df_f, use_container_width=True, hide_index=True)
            st.divider()
            st.subheader("Ringkasan Metode Pembayaran")
            df_m = pd.DataFrame(run_query(q.OLAP_RINGKASAN_METODE_BAYAR))
            if not df_m.empty:
                df_m["Total"] = df_m["Total"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_m, use_container_width=True, hide_index=True)
        else: st.info("Belum ada data pembayaran.")

    with tab_penyewa:
        st.subheader("Data Penyewa Aktif")
        df = pd.DataFrame(run_query(q.OLTP_DATA_PENYEWA_AKTIF))
        if not df.empty:
            st.metric("Total Penyewa Aktif", len(df))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("Belum ada penyewa aktif.")

    with tab_maint:
        st.subheader("Rekap Maintenance")
        df = pd.DataFrame(run_query(q.OLTP_REKAP_MAINTENANCE))
        if not df.empty:
            fm = st.radio("Filter Status:", ["Semua", "Belum ditangani", "Tertunda", "Sedang dikerjakan", "Selesai"],
                          horizontal=True, key="fm")
            df_f = df.copy()
            if fm != "Semua": df_f = df_f[df_f["Status"] == fm]
            st.dataframe(df_f, use_container_width=True, hide_index=True)
        else: st.info("Belum ada data maintenance.")

        st.divider()
        st.subheader("Kelola Maintenance")
        pending = run_query(q.OLTP_MAINTENANCE_PENDING)
        if not pending:
            st.success("Semua maintenance sudah ditangani / selesai.")
        else:
            opsi = {f"#{p['id_request_maintenance']} – {p['nama_lengkap']} – {p['deskripsi']} ({p['status']})": p for p in pending}
            pilih = st.selectbox("Pilih request:", list(opsi.keys()), key="pm")
            data = opsi[pilih]
            status_baru = st.selectbox("Ubah status:", ["Tertunda", "Sedang dikerjakan", "Selesai"], key="sm")
            if st.button("Update Status", use_container_width=True, type="primary", key="um"):
                try:
                    existing = run_query(q.OLTP_CEK_RIWAYAT_MAINTENANCE_EXIST, (data["id_request_maintenance"],))
                    rid = data["id_request_maintenance"]
                    if status_baru == "Tertunda":
                        if existing: run_execute("UPDATE riwayat_maintenance SET status='Tertunda', tanggal_mulai=NULL, tanggal_selesai=NULL WHERE id_request_maintenance=%s", (rid,))
                        else: run_execute("INSERT INTO riwayat_maintenance (status, id_request_maintenance) VALUES ('Tertunda', %s)", (rid,))
                    elif status_baru == "Sedang dikerjakan":
                        if existing: run_execute("UPDATE riwayat_maintenance SET status='Sedang dikerjakan', tanggal_mulai=CURRENT_DATE, tanggal_selesai=NULL WHERE id_request_maintenance=%s", (rid,))
                        else: run_execute("INSERT INTO riwayat_maintenance (tanggal_mulai, status, id_request_maintenance) VALUES (CURRENT_DATE, 'Sedang dikerjakan', %s)", (rid,))
                    else:
                        if existing: run_execute("UPDATE riwayat_maintenance SET status='Selesai', tanggal_mulai=COALESCE(tanggal_mulai,CURRENT_DATE), tanggal_selesai=CURRENT_DATE WHERE id_request_maintenance=%s", (rid,))
                        else: run_execute("INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance) VALUES (CURRENT_DATE, CURRENT_DATE, 'Selesai', %s)", (rid,))
                    st.success(f"Status diubah menjadi '{status_baru}'."); st.rerun()
                except Exception as e: st.error(f"Gagal: {e}")

# ── PENYEWA ──
else:
    try: penyewa = run_query(q.OLTP_DAFTAR_PENYEWA_AKTIF_LOGIN)
    except Exception as e: st.error(f"Gagal: {e}"); st.stop()

    if not penyewa: st.warning("Tidak ada penyewa aktif."); st.stop()

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
        df = pd.DataFrame(run_query(q.OLTP_KAMAR_KOSONG_PENYEWA))
        if df.empty: st.info("Tidak ada kamar kosong.")
        else:
            st.metric("Kamar Tersedia", len(df))
            df["Harga (Rp)"] = df["Harga (Rp)"].apply(lambda x: f"Rp {x:,}")
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_sewa:
        st.subheader("Sewa Aktif Saya")
        df_sewa = pd.DataFrame(run_query(q.OLTP_SEWA_AKTIF_PENYEWA, (id_penyewa,)))
        if df_sewa.empty: st.info("Tidak ada sewa aktif.")
        else:
            today = datetime.date.today()
            for _, row in df_sewa.iterrows():
                sisa = (row["jatuh_tempo"] - today).days
                cols = st.columns(4)
                cols[0].metric("Kamar", f"{row['Kamar']} ({row['Kos']})")
                cols[1].metric("Mulai Sewa", row["Mulai"].strftime("%d-%m-%Y"))
                cols[2].metric("Jatuh Tempo", row["jatuh_tempo"].strftime("%d-%m-%Y"))
                if sisa <= 7: cols[3].metric("Sisa Waktu", f"{sisa} hari", delta="Segera bayar!", delta_color="inverse")
                else: cols[3].metric("Sisa Waktu", f"{sisa} hari")
                st.divider()

            st.dataframe(df_sewa.drop(columns=["id_sewa", "harga", "jumlah_bulan_bayar", "jatuh_tempo"]),
                         use_container_width=True, hide_index=True)
            st.divider()

            st.subheader("Riwayat Pembayaran")
            df_bayar = pd.DataFrame(run_query(q.OLTP_RIWAYAT_BAYAR_PENYEWA, (id_penyewa,)))
            if df_bayar.empty: st.info("Belum ada riwayat.")
            else:
                df_bayar["Nominal (Rp)"] = df_bayar["Nominal (Rp)"].apply(lambda x: f"Rp {x:,}")
                st.dataframe(df_bayar, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Bayar Sewa")
            with st.form("form_bayar", clear_on_submit=True):
                sewa_opts = {f"{r['Kamar']} - {r['Kos']} (Rp {r['harga']:,}/bulan)": r for _, r in df_sewa.iterrows()}
                sp = st.selectbox("Pilih sewa:", list(sewa_opts.keys()))
                sd = sewa_opts[sp]
                jml = st.selectbox("Jumlah bulan:", [1, 2, 3])
                metode = st.selectbox("Metode:", ["Transfer", "Tunai"])
                total = int(sd["harga"]) * jml
                st.info(f"Total: Rp {int(sd['harga']):,} × {jml} bulan = **Rp {total:,}**")
                if st.form_submit_button("Bayar Sekarang"):
                    try:
                        run_execute(q.OLTP_INSERT_PEMBAYARAN, (total, metode, int(sd["id_sewa"])))
                        new_pb = run_query(q.OLTP_GET_LAST_ID_PEMBAYARAN)[0]["id"]
                        for i in range(jml):
                            periode = (pd.Timestamp(sd["jatuh_tempo"]) + pd.DateOffset(months=i)).strftime("%Y-%m")
                            run_execute(q.OLTP_INSERT_PERIODE_PEMBAYARAN, (periode, "Berhasil", new_pb))
                        st.success(f"Pembayaran berhasil! {jml} bulan, total Rp {total:,}"); st.rerun()
                    except Exception as e: st.error(f"Gagal: {e}")

    with tab_maint:
        st.subheader("Request Maintenance Saya")
        df = pd.DataFrame(run_query(q.OLTP_MAINT_PENYEWA, (id_penyewa,)))
        if df.empty: st.success("Tidak ada request maintenance.")
        else: st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Ajukan Maintenance Baru")
        with st.form("form_maintenance", clear_on_submit=True):
            keluhan = st.text_area("Deskripsi keluhan:", placeholder="Lampu mati, AC tidak dingin, dll.")
            if st.form_submit_button("Ajukan"):
                if not keluhan.strip(): st.warning("Deskripsi tidak boleh kosong.")
                else:
                    try:
                        run_execute(q.OLTP_INSERT_MAINTENANCE, (keluhan.strip(), id_penyewa))
                        st.success("Request berhasil diajukan."); st.rerun()
                    except Exception as e: st.error(f"Gagal: {e}")

st.divider()
st.caption("ABD KELOMPOK 2 @2026")