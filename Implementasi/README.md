# Hidden Kost – Aplikasi Streamlit

Aplikasi visualisasi manajemen kos dengan fitur OLTP, OLAP, dan Analisis Optimasi Index.

## Cara Menjalankan

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Atur koneksi database
Edit file `.streamlit/secrets.toml`:
```toml
DB_HOST     = "localhost"
DB_PORT     = 5432
DB_NAME     = "manajemen_kos"
DB_USER     = "postgres"
DB_PASSWORD = "password_kamu"
```

### 3. Pastikan database sudah diisi
Jalankan DDL.SQL lalu DML.SQL di PostgreSQL kamu terlebih dahulu.

### 4. Jalankan aplikasi
```bash
streamlit run Home.py
```

## Struktur File
```
hiddenkost/
├── Home.py                      ← Halaman utama & dashboard
├── db.py                        ← Koneksi database
├── requirements.txt
├── .streamlit/
│   └── secrets.toml             ← Konfigurasi database (jangan di-commit!)
└── pages/
    ├── 1_OLTP.py                ← Operasional harian
    ├── 2_OLAP.py                ← Analisis & laporan
    └── 3_Optimasi_Index.py      ← EXPLAIN ANALYZE & analisis index
```

## Fitur

### OLTP
- Cari kamar kosong dengan filter kos & tipe
- Daftar penyewa aktif dengan pencarian nama
- Sewa berjalan (highlight merah jika < 30 hari lagi)
- Request maintenance yang belum selesai

### OLAP
- Total pendapatan per kos & per tipe kamar (bar chart + pie chart)
- Tingkat okupansi kamar dengan progress bar
- Tren transaksi berhasil vs gagal per bulan (line chart)
- Rekap & frekuensi keluhan maintenance

### Optimasi Index
- 5 skenario EXPLAIN ANALYZE interaktif
- Perbandingan Index Scan vs Seq Scan (paksa tanpa index)
- Tabel ringkasan index yang ada
- Rekomendasi index tambahan
