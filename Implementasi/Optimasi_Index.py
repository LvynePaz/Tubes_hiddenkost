import re
import streamlit as st
import pandas as pd
from db import run_query, run_execute, run_explain

st.set_page_config(
    page_title="Hidden Kost – Optimasi Index",
    page_icon="HK",
    layout="wide",
)

st.title("Optimasi Index")
st.caption("Implementasi dan Analisis Performa Query PostgreSQL — Sistem Informasi Hidden Kost")
st.divider()


# ── Helper functions ───────────────────────────────────────────────────────────
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
#  SKENARIO 1 — Kamar berdasarkan Status (index sudah ada sejak awal)
# ══════════════════════════════════════════════════════════════════════════════
st.header("Skenario 1: Filter Kamar berdasarkan Status")
st.markdown("""
Query ini dipakai di tab **Kamar Kosong** (Penyewa). Index `index_status_kamar`
sudah dibuat sejak `DDL.SQL` awal, jadi seharusnya langsung pakai **Index Scan**.
""")

status_pilih = st.selectbox("Pilih status kamar:", ["Kosong", "Sedang disewa"], key="s1_status")
sql1 = "SELECT * FROM kamar WHERE status = %s::status_kamar"

col1, col2 = st.columns(2)
with col1:
    if st.button("Jalankan (Normal)", key="s1_normal"):
        toggle_index_scan(True)
        plan = run_explain(sql1, (status_pilih,))
        tampilkan_plan(plan, "Kondisi normal")
with col2:
    if st.button("Jalankan (Paksa Seq Scan)", key="s1_force"):
        toggle_index_scan(False)
        plan = run_explain(sql1, (status_pilih,))
        toggle_index_scan(True)
        tampilkan_plan(plan, "Index dimatikan paksa")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  SKENARIO 2 — Penyewa Aktif (selektivitas rendah, ~80% data 'Aktif')
# ══════════════════════════════════════════════════════════════════════════════
st.header("Skenario 2: Filter Penyewa berdasarkan Status (Selektivitas Rendah)")
st.markdown("""
Index `index_status_penyewa` sudah ada, tapi ±80% data `profil_penyewa`
berstatus `'Aktif'`. Planner Postgres sering tetap pilih **Seq Scan** walau
index tersedia, karena baca seluruh tabel lebih murah daripada lompat-lompat
ke index kalau hampir semua baris cocok. Ini contoh kasus "index ada, tapi
tidak dipakai".
""")

status_penyewa_pilih = st.selectbox("Pilih status penyewa:", ["Aktif", "Tidak aktif"], key="s2_status")
sql2 = "SELECT * FROM profil_penyewa WHERE status = %s::status_penyewa"

if st.button("Jalankan EXPLAIN ANALYZE", key="s2_run"):
    plan = run_explain(sql2, (status_penyewa_pilih,))
    tampilkan_plan(plan, f"Status = '{status_penyewa_pilih}'")
    st.caption("Coba bandingkan 'Aktif' (selektivitas rendah) vs 'Tidak aktif' (selektivitas tinggi) — hasil plan-nya bisa berbeda.")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  SKENARIO 3 — Pencarian Nama Penyewa: exact match vs LIKE
# ══════════════════════════════════════════════════════════════════════════════
st.header("Skenario 3: Pencarian Nama Penyewa — Exact Match vs LIKE")
st.markdown("""
Index `index_nama_penyewa` adalah B-Tree biasa. B-Tree **hanya efektif untuk
pencarian exact match (`=`)**. Begitu dipakai `LIKE '%kata%'` (wildcard di
depan), index ini **tidak akan terpakai** dan otomatis jadi Seq Scan.
""")

contoh_nama = run_query("SELECT nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")
nama_default = contoh_nama[0]["nama_lengkap"] if contoh_nama else "PYW-0001"

nama_cari = st.text_input("Cari nama (coba isi nama lengkap dari data):", value=nama_default, key="s3_nama")

col3, col4 = st.columns(2)
with col3:
    if st.button("Jalankan Exact Match ( = )", key="s3_exact"):
        plan = run_explain("SELECT * FROM profil_penyewa WHERE nama_lengkap = %s", (nama_cari,))
        tampilkan_plan(plan, "WHERE nama_lengkap = ...")
with col4:
    if st.button("Jalankan LIKE ( %...% )", key="s3_like"):
        plan = run_explain("SELECT * FROM profil_penyewa WHERE nama_lengkap LIKE %s", (f"%{nama_cari}%",))
        tampilkan_plan(plan, "WHERE nama_lengkap LIKE '%...%'")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  SKENARIO 4 & 5 — Foreign Key tanpa index (sewa.id_kamar, sewa.id_penyewa)
# ══════════════════════════════════════════════════════════════════════════════
st.header("Skenario 4: Riwayat Sewa berdasarkan Kamar (Foreign Key, belum ada index)")
st.markdown("""
Foreign key di PostgreSQL **tidak otomatis dapat index** (berbeda dengan
Primary Key). Query ini dipakai di fitur **Riwayat Penghuni Kamar**
(Pemilik) dan **Status Sewa** (Penyewa), tapi kolom `sewa.id_kamar` belum
ada index-nya.
""")

ada_index_kamar = index_sudah_ada("index_id_kamar_sewa")
if ada_index_kamar:
    st.info("Index `index_id_kamar_sewa` sudah dibuat.")
else:
    st.warning("Index `index_id_kamar_sewa` **belum ada** — query di bawah seharusnya Seq Scan.")

contoh_kamar = run_query("SELECT id_kamar, nomor FROM kamar ORDER BY id_kamar LIMIT 1")
id_kamar_contoh = contoh_kamar[0]["id_kamar"] if contoh_kamar else 1
nomor_contoh = contoh_kamar[0]["nomor"] if contoh_kamar else "-"

id_kamar_input = st.number_input(f"id_kamar (contoh: {id_kamar_contoh} = {nomor_contoh}):", min_value=1, value=int(id_kamar_contoh), key="s4_id")

col5, col6 = st.columns(2)
with col5:
    if st.button("Jalankan EXPLAIN ANALYZE", key="s4_run"):
        plan = run_explain("SELECT * FROM sewa WHERE id_kamar = %s", (id_kamar_input,))
        tampilkan_plan(plan, "Sebelum/sesudah index")
with col6:
    if not ada_index_kamar:
        if st.button("Buat Index Sekarang", key="s4_create"):
            try:
                run_execute("CREATE INDEX index_id_kamar_sewa ON sewa(id_kamar)")
                st.success("Index `index_id_kamar_sewa` berhasil dibuat. Jalankan ulang EXPLAIN ANALYZE di atas untuk lihat perubahannya.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal membuat index: {e}")
    else:
        if st.button("Hapus Index (untuk demo ulang)", key="s4_drop"):
            try:
                run_execute("DROP INDEX index_id_kamar_sewa")
                st.success("Index dihapus.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menghapus index: {e}")

st.divider()

st.header("Skenario 5: Riwayat Sewa berdasarkan Penyewa (Foreign Key, belum ada index)")
st.markdown("""
Sama seperti skenario 4, tapi untuk kolom `sewa.id_penyewa`. Query ini
dipakai untuk menampilkan sewa aktif seorang penyewa.
""")

ada_index_penyewa = index_sudah_ada("index_id_penyewa_sewa")
if ada_index_penyewa:
    st.info("Index `index_id_penyewa_sewa` sudah dibuat.")
else:
    st.warning("Index `index_id_penyewa_sewa` **belum ada** — query di bawah seharusnya Seq Scan.")

contoh_penyewa = run_query("SELECT id_penyewa, nama_lengkap FROM profil_penyewa ORDER BY id_penyewa LIMIT 1")
id_penyewa_contoh = contoh_penyewa[0]["id_penyewa"] if contoh_penyewa else 1
nama_penyewa_contoh = contoh_penyewa[0]["nama_lengkap"] if contoh_penyewa else "-"

id_penyewa_input = st.number_input(
    f"id_penyewa (contoh: {id_penyewa_contoh} = {nama_penyewa_contoh}):",
    min_value=1, value=int(id_penyewa_contoh), key="s5_id"
)

col7, col8 = st.columns(2)
with col7:
    if st.button("Jalankan EXPLAIN ANALYZE", key="s5_run"):
        plan = run_explain("SELECT * FROM sewa WHERE id_penyewa = %s", (id_penyewa_input,))
        tampilkan_plan(plan, "Sebelum/sesudah index")
with col8:
    if not ada_index_penyewa:
        if st.button("Buat Index Sekarang", key="s5_create"):
            try:
                run_execute("CREATE INDEX index_id_penyewa_sewa ON sewa(id_penyewa)")
                st.success("Index `index_id_penyewa_sewa` berhasil dibuat. Jalankan ulang EXPLAIN ANALYZE di atas untuk lihat perubahannya.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal membuat index: {e}")
    else:
        if st.button("Hapus Index (untuk demo ulang)", key="s5_drop"):
            try:
                run_execute("DROP INDEX index_id_penyewa_sewa")
                st.success("Index dihapus.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menghapus index: {e}")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  TABEL RINGKASAN INDEX YANG ADA
# ══════════════════════════════════════════════════════════════════════════════
st.header("Ringkasan Seluruh Index di Database")
sql_ringkasan = """
    SELECT tablename AS "Tabel",
           indexname AS "Nama Index",
           indexdef AS "Definisi"
    FROM pg_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname
"""
rows_index = run_query(sql_ringkasan)
df_index = pd.DataFrame(rows_index)
if not df_index.empty:
    st.dataframe(df_index, use_container_width=True, hide_index=True)
    st.caption(f"Total {len(df_index)} index ditemukan (termasuk index otomatis dari Primary Key & Unique constraint).")
else:
    st.info("Belum ada index.")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  REKOMENDASI INDEX TAMBAHAN
# ══════════════════════════════════════════════════════════════════════════════
st.header("Rekomendasi Index Tambahan")
st.markdown("""
Kolom foreign key di bawah ini sering dipakai untuk JOIN/filter di aplikasi
tapi belum punya index. Direkomendasikan ditambahkan untuk mempercepat query.
""")

rekomendasi = [
    ("sewa", "id_kamar", "index_id_kamar_sewa"),
    ("sewa", "id_penyewa", "index_id_penyewa_sewa"),
    ("pembayaran", "id_sewa", "index_id_sewa_pembayaran"),
    ("periode_pembayaran", "id_pembayaran", "index_id_pembayaran_periode"),
    ("request_maintenance", "id_penyewa", "index_id_penyewa_request"),
]

data_rekomendasi = []
for tabel, kolom, nama_idx in rekomendasi:
    status_idx = "Sudah ada" if index_sudah_ada(nama_idx) else "Belum ada"
    data_rekomendasi.append({
        "Tabel": tabel,
        "Kolom": kolom,
        "Nama Index Disarankan": nama_idx,
        "Status": status_idx,
    })

df_rekom = pd.DataFrame(data_rekomendasi)
st.dataframe(df_rekom, use_container_width=True, hide_index=True)

if st.button("Buat Semua Index yang Direkomendasikan", type="primary"):
    berhasil = 0
    for tabel, kolom, nama_idx in rekomendasi:
        if not index_sudah_ada(nama_idx):
            try:
                run_execute(f"CREATE INDEX {nama_idx} ON {tabel}({kolom})")
                berhasil += 1
            except Exception as e:
                st.error(f"Gagal membuat {nama_idx}: {e}")
    if berhasil > 0:
        st.success(f"{berhasil} index baru berhasil dibuat.")
        st.rerun()
    else:
        st.info("Semua index rekomendasi sudah ada.")

st.divider()
st.caption("ABD KELOMPOK 2 @2026")