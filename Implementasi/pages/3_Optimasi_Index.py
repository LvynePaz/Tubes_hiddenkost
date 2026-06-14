import streamlit as st
import pandas as pd
import re
from db import run_query, run_explain

st.set_page_config(page_title="Optimasi Index – Hidden Kost", layout="wide")

st.title("⚡ Optimasi Query – Analisis Index")
st.caption(
    "Bandingkan performa query **dengan index** vs **tanpa index** menggunakan EXPLAIN ANALYZE. "
    "Index yang tersedia: `index_nama_penyewa`, `index_nomor_kamar`, `index_status_penyewa`, `index_status_kamar`."
)

# ── Helper ────────────────────────────────────────────────────────────────────
def parse_cost(lines: list[str]) -> dict:
    """Ambil cost, rows, dan waktu eksekusi dari output EXPLAIN ANALYZE."""
    hasil = {
        "Metode Akses":      "-",
        "Biaya Awal":        "-",
        "Biaya Total":       "-",
        "Estimasi Baris":    "-",
        "Waktu Perencanaan": "-",
        "Waktu Eksekusi":    "-",
    }
    for line in lines:
        # Metode akses
        if "Index Scan" in line:
            hasil["Metode Akses"] = "✅ Index Scan"
        elif "Bitmap Index Scan" in line or "Bitmap Heap Scan" in line:
            hasil["Metode Akses"] = "✅ Bitmap Index Scan"
        elif "Seq Scan" in line and hasil["Metode Akses"] == "-":
            hasil["Metode Akses"] = "🔴 Seq Scan (penuh)"

        # cost=x..y rows=z
        m = re.search(r"cost=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)", line)
        if m and hasil["Biaya Total"] == "-":
            hasil["Biaya Awal"]     = m.group(1)
            hasil["Biaya Total"]    = m.group(2)
            hasil["Estimasi Baris"] = m.group(3)

        # Planning / Execution time
        if "Planning Time" in line:
            hasil["Waktu Perencanaan"] = line.strip()
        if "Execution Time" in line:
            hasil["Waktu Eksekusi"] = line.strip()
    return hasil


def tampilkan_explain(label: str, sql: str, params=None):
    with st.spinner(f"Menjalankan EXPLAIN ANALYZE – {label} …"):
        lines  = run_explain(sql, params)
        parsed = parse_cost(lines)

    st.markdown(f"**{label}**")

    # Kartu ringkasan
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Metode Akses",   parsed["Metode Akses"])
    col2.metric("Biaya Total",    parsed["Biaya Total"])
    col3.metric("Estimasi Baris", parsed["Estimasi Baris"])
    col4.metric("Waktu Eksekusi", parsed["Waktu Eksekusi"])

    # Raw output
    with st.expander("Lihat output EXPLAIN ANALYZE lengkap"):
        st.code("\n".join(lines), language="sql")


# ── Pilih Skenario ────────────────────────────────────────────────────────────
st.divider()
st.subheader("Pilih Skenario Uji")

skenario = st.selectbox(
    "Skenario",
    [
        "1. Cari kamar berdasarkan status (index_status_kamar)",
        "2. Cari penyewa berdasarkan status (index_status_penyewa)",
        "3. Cari penyewa berdasarkan nama (index_nama_penyewa)",
        "4. Cari kamar berdasarkan nomor (index_nomor_kamar)",
        "5. JOIN sewa + penyewa + kamar dengan filter tanggal",
    ],
)

st.divider()

# ── Skenario 1 ────────────────────────────────────────────────────────────────
if skenario.startswith("1"):
    st.markdown("""
    ### 🔎 Skenario 1 – Filter Status Kamar
    Kolom `status` pada tabel `kamar` sudah dibuatkan index `index_status_kamar`.
    Query mencari semua kamar dengan status **Kosong**.
    """)

    sql = "SELECT * FROM kamar WHERE status = 'Kosong'"

    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        tampilkan_explain("Dengan Index (index_status_kamar)", sql)
    with col_kanan:
        st.markdown("**Tanpa Index** *(simulasi dengan SET enable_indexscan = OFF)*")
        run_query("SET enable_indexscan = OFF; SET enable_bitmapscan = OFF")
        tampilkan_explain("Tanpa Index – Seq Scan Dipaksa", sql)
        run_query("SET enable_indexscan = ON; SET enable_bitmapscan = ON")

    st.info("""
    **Penjelasan:**
    - **Index Scan / Bitmap Index Scan** → PostgreSQL langsung melompat ke baris yang relevan menggunakan index.
    - **Seq Scan** → PostgreSQL membaca *seluruh* tabel satu per satu dari awal sampai akhir.
    - Semakin banyak data, perbedaan waktu eksekusi akan semakin terasa.
    """)

# ── Skenario 2 ────────────────────────────────────────────────────────────────
elif skenario.startswith("2"):
    st.markdown("""
    ### 🔎 Skenario 2 – Filter Status Penyewa
    Index `index_status_penyewa` dibuat di kolom `status` tabel `profil_penyewa`.
    """)

    sql = "SELECT * FROM profil_penyewa WHERE status = 'Aktif'"

    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        tampilkan_explain("Dengan Index (index_status_penyewa)", sql)
    with col_kanan:
        run_query("SET enable_indexscan = OFF; SET enable_bitmapscan = OFF")
        tampilkan_explain("Tanpa Index – Seq Scan Dipaksa", sql)
        run_query("SET enable_indexscan = ON; SET enable_bitmapscan = ON")

    st.info("""
    **Penjelasan:**
    Kolom status bertipe ENUM dengan kardinalitas rendah (hanya 2 nilai: Aktif / Tidak aktif).
    PostgreSQL kadang memilih Bitmap Index Scan karena lebih efisien untuk kardinalitas rendah.
    """)

# ── Skenario 3 ────────────────────────────────────────────────────────────────
elif skenario.startswith("3"):
    st.markdown("""
    ### 🔎 Skenario 3 – Pencarian Nama Penyewa
    Index `index_nama_penyewa` dibuat di kolom `nama_lengkap` tabel `profil_penyewa`.
    """)

    nama = st.text_input("Masukkan nama yang dicari (exact match)", value="Penyewa ke-1")
    sql  = f"SELECT * FROM profil_penyewa WHERE nama_lengkap = '{nama}'"

    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        tampilkan_explain("Dengan Index (index_nama_penyewa)", sql)
    with col_kanan:
        run_query("SET enable_indexscan = OFF; SET enable_bitmapscan = OFF")
        tampilkan_explain("Tanpa Index – Seq Scan Dipaksa", sql)
        run_query("SET enable_indexscan = ON; SET enable_bitmapscan = ON")

    st.info("""
    **Penjelasan:**
    Pencarian *exact match* (`=`) pada kolom teks sangat diuntungkan oleh index B-Tree.
    Perhatikan penurunan dramatis pada **Biaya Total** dan **Waktu Eksekusi**.
    """)

# ── Skenario 4 ────────────────────────────────────────────────────────────────
elif skenario.startswith("4"):
    st.markdown("""
    ### 🔎 Skenario 4 – Pencarian Nomor Kamar
    Index `index_nomor_kamar` dibuat di kolom `nomor` tabel `kamar`.
    """)

    nomor = st.text_input("Masukkan nomor kamar", value="O-1")
    sql   = f"SELECT * FROM kamar WHERE nomor = '{nomor}'"

    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        tampilkan_explain("Dengan Index (index_nomor_kamar)", sql)
    with col_kanan:
        run_query("SET enable_indexscan = OFF; SET enable_bitmapscan = OFF")
        tampilkan_explain("Tanpa Index – Seq Scan Dipaksa", sql)
        run_query("SET enable_indexscan = ON; SET enable_bitmapscan = ON")

    st.info("""
    **Penjelasan:**
    Nomor kamar bersifat unik atau hampir unik, sehingga index B-Tree sangat efektif —
    PostgreSQL hanya perlu membaca **1 baris** alih-alih seluruh tabel.
    """)

# ── Skenario 5 ────────────────────────────────────────────────────────────────
elif skenario.startswith("5"):
    st.markdown("""
    ### 🔎 Skenario 5 – JOIN Multi-Tabel dengan Filter Tanggal
    Query ini menggabungkan tabel `sewa`, `profil_penyewa`, dan `kamar`
    dengan filter `tanggal_akhir`. Kolom ini **belum diindex** — cocok
    untuk melihat dampak Seq Scan vs Index Scan.
    """)

    tgl = st.date_input("Filter sewa berakhir setelah tanggal", value=pd.Timestamp("2025-01-01"))
    sql = f"""
        SELECT p.nama_lengkap, k.nomor, s.tanggal_mulai
        FROM sewa s
        JOIN profil_penyewa p ON s.id_penyewa = p.id_penyewa
        JOIN kamar          k ON s.id_kamar   = k.id_kamar
        WHERE s.tanggal_akhir >= '{tgl}'
    """

    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        tampilkan_explain("Kondisi Saat Ini (tanpa index tanggal_akhir)", sql)
    with col_kanan:
        st.markdown("**Rekomendasi:** Tambahkan index berikut")
        st.code("CREATE INDEX index_tanggal_akhir_sewa ON sewa (tanggal_akhir);", language="sql")
        st.caption(
            "Setelah index dibuat, jalankan kembali halaman ini — "
            "PostgreSQL akan menggunakan Index Scan dan biaya query akan turun signifikan."
        )

    st.info("""
    **Penjelasan:**
    Kolom `tanggal_akhir` sering digunakan untuk mencari sewa aktif, namun belum ada index-nya.
    Dengan menambahkan index, PostgreSQL tidak perlu memindai seluruh tabel sewa
    — khususnya saat jumlah baris bertambah banyak.
    """)

# ── Tabel Ringkasan Index ─────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Ringkasan Index yang Tersedia")

data_index = {
    "Nama Index":        [
        "index_status_kamar",
        "index_status_penyewa",
        "index_nama_penyewa",
        "index_nomor_kamar",
    ],
    "Tabel":             ["kamar", "profil_penyewa", "profil_penyewa", "kamar"],
    "Kolom":             ["status", "status", "nama_lengkap", "nomor"],
    "Jenis":             ["B-Tree", "B-Tree", "B-Tree", "B-Tree"],
    "Kegunaan":          [
        "Filter kamar kosong / sedang disewa",
        "Filter penyewa aktif / tidak aktif",
        "Pencarian nama penyewa (exact match)",
        "Pencarian nomor kamar",
    ],
}
st.dataframe(pd.DataFrame(data_index), use_container_width=True, hide_index=True)

st.subheader("💡 Rekomendasi Index Tambahan")
data_rekomendasi = {
    "Tabel":   ["sewa", "sewa", "pembayaran"],
    "Kolom":   ["tanggal_akhir", "id_penyewa", "id_sewa"],
    "Alasan":  [
        "Sering difilter untuk cari sewa aktif (WHERE tanggal_akhir >= ...)",
        "Sering di-JOIN dengan profil_penyewa",
        "Sering di-JOIN dengan sewa pada query pembayaran",
    ],
    "Perintah SQL": [
        "CREATE INDEX idx_sewa_tanggal_akhir ON sewa (tanggal_akhir);",
        "CREATE INDEX idx_sewa_penyewa      ON sewa (id_penyewa);",
        "CREATE INDEX idx_pembayaran_sewa   ON pembayaran (id_sewa);",
    ],
}
st.dataframe(pd.DataFrame(data_rekomendasi), use_container_width=True, hide_index=True)
