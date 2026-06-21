"""
Setup Database – Hidden Kost
Jalankan: python setup_db.py
Pastikan PostgreSQL suda    h running dan password postgres sesuai.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

# ── Konfigurasi ──────────────────────────────────────────────────────────────
DB_HOST     = "localhost"
DB_PORT     = 5432
DB_NAME     = "manajemen_kos"
DB_USER     = "postgres"
DB_PASSWORD = "1"

# ── DDL ──────────────────────────────────────────────────────────────────────
DDL = """
-- ENUM types
DO $$ BEGIN
    CREATE TYPE status_penyewa AS ENUM ('Aktif', 'Tidak aktif');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE status_kamar AS ENUM ('Sedang disewa', 'Kosong');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE status_maintenance AS ENUM ('Tertunda', 'Sedang dikerjakan', 'Selesai');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE metode_pembayaran AS ENUM ('Tunai', 'Transfer');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE status_pembayaran AS ENUM ('Gagal', 'Berhasil');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Tables
CREATE TABLE IF NOT EXISTS roles (
    id_roles SERIAL PRIMARY KEY,
    nama_role VARCHAR(25) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id_user SERIAL PRIMARY KEY,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    id_roles INT NOT NULL,
    FOREIGN KEY (id_roles) REFERENCES roles(id_roles)
);

CREATE TABLE IF NOT EXISTS profil_penyewa (
    id_penyewa SERIAL PRIMARY KEY,
    nama_lengkap VARCHAR(100) NOT NULL,
    pekerjaan VARCHAR(50) NOT NULL,
    instansi VARCHAR(50) NOT NULL,
    deskripsi_pekerjaan VARCHAR(100) NOT NULL,
    status status_penyewa NOT NULL DEFAULT 'Tidak aktif',
    url_ktp VARCHAR(255) NOT NULL,
    id_user INT NOT NULL UNIQUE,
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS kos (
    id_kos SERIAL PRIMARY KEY,
    nama_kos VARCHAR(50) NOT NULL,
    alamat TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tipe_kamar (
    id_tipe_kamar SERIAL PRIMARY KEY,
    kategori VARCHAR(50) NOT NULL,
    deskripsi_fasilitas VARCHAR(255) NOT NULL,
    harga_sewa INT NOT NULL
);

CREATE TABLE IF NOT EXISTS kamar (
    id_kamar SERIAL PRIMARY KEY,
    nomor VARCHAR(8) NOT NULL,
    luas INT NOT NULL,
    lantai VARCHAR(2) NOT NULL,
    status status_kamar NOT NULL DEFAULT 'Kosong',
    id_tipe_kamar INT NOT NULL,
    id_kos INT NOT NULL,
    FOREIGN KEY (id_tipe_kamar) REFERENCES tipe_kamar(id_tipe_kamar),
    FOREIGN KEY (id_kos) REFERENCES kos(id_kos)
);

CREATE TABLE IF NOT EXISTS sewa (
    id_sewa SERIAL PRIMARY KEY,
    tanggal_mulai DATE NOT NULL,
    tanggal_akhir DATE NOT NULL,
    id_penyewa INT NOT NULL,
    id_kamar INT NOT NULL,
    FOREIGN KEY (id_penyewa) REFERENCES profil_penyewa(id_penyewa),
    FOREIGN KEY (id_kamar) REFERENCES kamar(id_kamar)
);

CREATE TABLE IF NOT EXISTS pembayaran (
    id_pembayaran SERIAL PRIMARY KEY,
    nominal INT NOT NULL,
    metode_bayar metode_pembayaran NOT NULL,
    id_sewa INT NOT NULL,
    FOREIGN KEY (id_sewa) REFERENCES sewa(id_sewa)
);

CREATE TABLE IF NOT EXISTS periode_pembayaran (
    id_periode SERIAL PRIMARY KEY,
    periode_bayar VARCHAR(10) NOT NULL,
    status status_pembayaran NOT NULL,
    id_pembayaran INT NOT NULL,
    FOREIGN KEY (id_pembayaran) REFERENCES pembayaran(id_pembayaran)
);

CREATE TABLE IF NOT EXISTS request_maintenance (
    id_request_maintenance SERIAL PRIMARY KEY,
    deskripsi VARCHAR(255) NOT NULL,
    id_penyewa INT NOT NULL,
    FOREIGN KEY (id_penyewa) REFERENCES profil_penyewa(id_penyewa)
);

CREATE TABLE IF NOT EXISTS riwayat_maintenance (
    id_riwayat_maintenance SERIAL PRIMARY KEY,
    tanggal_mulai DATE,
    tanggal_selesai DATE,
    status status_maintenance NOT NULL DEFAULT 'Tertunda',
    id_request_maintenance INT NOT NULL UNIQUE,
    FOREIGN KEY (id_request_maintenance) REFERENCES request_maintenance(id_request_maintenance)
);

-- Indexes
CREATE INDEX IF NOT EXISTS index_nama_penyewa ON profil_penyewa (nama_lengkap);
CREATE INDEX IF NOT EXISTS index_nomor_kamar ON kamar (nomor);
CREATE INDEX IF NOT EXISTS index_status_penyewa ON profil_penyewa (status);
CREATE INDEX IF NOT EXISTS index_status_kamar ON kamar(status);
"""

# ── DML (seed data) ─────────────────────────────────────────────────────────
DML_STEPS = [
# Step 1: Roles
"""
INSERT INTO roles (nama_role) VALUES ('admin'), ('penyewa')
ON CONFLICT (nama_role) DO NOTHING;
""",

# Step 2: Admin users
"""
INSERT INTO users(email, password, id_roles) VALUES
('admin1@hiddenkost.com', 'admin123', 1),
('admin2@hiddenkost.com', 'admin123', 1)
ON CONFLICT (email) DO NOTHING;
""",

# Step 3: Penyewa users (998)
"""
INSERT INTO users(email, password, id_roles)
SELECT 'penyewa' || gs || '@gmail.com', 'password123', 2
FROM generate_series(1,998) gs
ON CONFLICT (email) DO NOTHING;
""",

# Step 4: Profil penyewa (450)
"""
INSERT INTO profil_penyewa
(nama_lengkap, pekerjaan, instansi, deskripsi_pekerjaan, status, url_ktp, id_user)
SELECT
    'Penyewa ke-' || gs,
    (ARRAY['Mahasiswa','Karyawan Swasta','Pegawai BUMN','Guru','Siswa','Wiraswasta'])[floor(random()*6+1)],
    (ARRAY['Institut Teknologi Kalimantan','Universitas Balikpapan','Politeknik Negeri Balikpapan','STT Migas','PT PLN Nusa Daya','PT Pertamina Hulu Mahakam','PT Pamapersada Nusantara','PT Kilang Pertamina Balikpapan'])[floor(random()*8+1)],
    (ARRAY['Sistem Informasi','Informatika','Teknik Elektro','Operator','Staff Administrasi','Supervisor','Guru Matematika','Marketing'])[floor(random()*8+1)],
    CASE WHEN random() < 0.8 THEN 'Aktif' ELSE 'Tidak aktif' END::status_penyewa,
    'ktp_' || gs || '.jpg',
    gs + 2
FROM generate_series(1,450) gs
ON CONFLICT (id_user) DO NOTHING;
""",

# Step 5: Kos
"""
INSERT INTO kos(nama_kos, alamat) VALUES
('Hidden Kost Origin', 'Jl. Giri Rejo II No. 4B, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127'),
('Hidden Kost Lux', 'Jl. Giri Rejo II No. 42 RT.032, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127')
ON CONFLICT DO NOTHING;
""",

# Step 6: Tipe kamar
"""
INSERT INTO tipe_kamar (kategori, deskripsi_fasilitas, harga_sewa) VALUES
('Tipe A', 'Kasur, dipan, bantal guling, bantal kepala, sprei, AC, lemari, meja, kursi, gantungan baju, kamar mandi dalam', 1200000),
('Tipe B', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja, kursi, gantungan baju, kamar mandi dalam', 1000000),
('Tipe C', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja, kursi, gantungan baju', 850000)
ON CONFLICT DO NOTHING;
""",

# Step 7: Kamar
"""
INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT 'O-' || gs, 12+(random()*4)::int,
       CASE WHEN gs<=4 THEN '1' ELSE '2' END,
       CASE WHEN random()<0.7 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
       (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori='Tipe C'),
       (SELECT id_kos FROM kos WHERE nama_kos='Hidden Kost Origin')
FROM generate_series(1,8) gs
WHERE NOT EXISTS (SELECT 1 FROM kamar WHERE nomor='O-' || gs);

INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT 'LA-' || gs, 15+(random()*3)::int, ((gs-1)/4+1)::text,
       CASE WHEN random()<0.75 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
       (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori='Tipe A'),
       (SELECT id_kos FROM kos WHERE nama_kos='Hidden Kost Lux')
FROM generate_series(1,8) gs
WHERE NOT EXISTS (SELECT 1 FROM kamar WHERE nomor='LA-' || gs);

INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT 'LB-' || gs, 14+(random()*3)::int, ((gs-1)/4+1)::text,
       CASE WHEN random()<0.75 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
       (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori='Tipe B'),
       (SELECT id_kos FROM kos WHERE nama_kos='Hidden Kost Lux')
FROM generate_series(1,8) gs
WHERE NOT EXISTS (SELECT 1 FROM kamar WHERE nomor='LB-' || gs);

INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT 'LC-' || gs, 12+(random()*2)::int, ((gs-1)/4+1)::text,
       CASE WHEN random()<0.75 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
       (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori='Tipe C'),
       (SELECT id_kos FROM kos WHERE nama_kos='Hidden Kost Lux')
FROM generate_series(1,8) gs
WHERE NOT EXISTS (SELECT 1 FROM kamar WHERE nomor='LC-' || gs);
""",

# Step 8: Sewa (600 records) — use actual existing IDs
"""
INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
SELECT
    start_date,
    start_date + (ARRAY[30,90,180,365,730])[floor(random()*5+1)] * INTERVAL '1 day',
    p.id_penyewa,
    k.id_kamar
FROM (
    SELECT CURRENT_DATE - ((random()*1500)::int * INTERVAL '1 day') AS start_date,
           row_number() OVER () AS rn
    FROM generate_series(1,600)
) t
CROSS JOIN LATERAL (
    SELECT id_penyewa FROM profil_penyewa ORDER BY random() LIMIT 1
) p
CROSS JOIN LATERAL (
    SELECT id_kamar FROM kamar ORDER BY random() LIMIT 1
) k;
""",

# Step 9: Pembayaran
"""
INSERT INTO pembayaran (nominal, metode_bayar, id_sewa)
SELECT
    CASE WHEN random()<0.33 THEN 850000 WHEN random()<0.66 THEN 1000000 ELSE 1200000 END,
    CASE WHEN random()<0.5 THEN 'Transfer' ELSE 'Tunai' END::metode_pembayaran,
    id_sewa
FROM sewa
WHERE id_sewa NOT IN (SELECT id_sewa FROM pembayaran);
""",

# Step 10: Periode pembayaran
"""
INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran)
SELECT
    TO_CHAR(CURRENT_DATE - ((random()*365)::int), 'YYYY-MM'),
    CASE WHEN random()<0.9 THEN 'Berhasil' ELSE 'Gagal' END::status_pembayaran,
    id_pembayaran
FROM pembayaran
WHERE id_pembayaran NOT IN (SELECT id_pembayaran FROM periode_pembayaran);
""",

# Step 11: Request maintenance
"""
INSERT INTO request_maintenance (deskripsi, id_penyewa)
SELECT
    (ARRAY['Lampu kamar mati','AC tidak dingin','Kipas rusak','Kunci pintu rusak','Keran bocor','WC mampet','Stop kontak bermasalah','Jaringan internet lambat'])[floor(random()*8+1)],
    id_penyewa
FROM profil_penyewa
WHERE random() < 0.4
  AND id_penyewa NOT IN (SELECT id_penyewa FROM request_maintenance);
""",

# Step 12: Riwayat maintenance
"""
INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance)
SELECT
    CURRENT_DATE - ((random()*90)::int),
    CURRENT_DATE - ((random()*30)::int),
    (ARRAY['Tertunda','Sedang dikerjakan','Selesai'])[floor(random()*3+1)]::status_maintenance,
    id_request_maintenance
FROM request_maintenance
WHERE id_request_maintenance NOT IN (SELECT id_request_maintenance FROM riwayat_maintenance);
""",
]

def main():
    print("=" * 60)
    print("  SETUP DATABASE - HIDDEN KOST")
    print("=" * 60)

    # Step 1: Buat database jika belum ada
    print("\n[1/3] Membuat database ...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cur.fetchone():
            print(f"  [OK] Database '{DB_NAME}' sudah ada.")
        else:
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"  [OK] Database '{DB_NAME}' berhasil dibuat.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [GAGAL] Koneksi ke PostgreSQL: {e}")
        print("\n  Pastikan:")
        print("    1. PostgreSQL sudah running (cek Services)")
        print(f"    2. User '{DB_USER}' dengan password '{DB_PASSWORD}' benar")
        print(f"    3. PostgreSQL listening di {DB_HOST}:{DB_PORT}")
        sys.exit(1)

    # Step 2: Buat tabel (DDL)
    print("\n[2/3] Membuat tabel & index ...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            dbname=DB_NAME
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(DDL)
        print("  [OK] Semua tabel & index berhasil dibuat.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [GAGAL] DDL: {e}")
        sys.exit(1)

    # Step 3: Seed data (DML)
    print("\n[3/3] Memasukkan data sampel ...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            dbname=DB_NAME
        )
        conn.autocommit = True
        cur = conn.cursor()

        for i, step_sql in enumerate(DML_STEPS, 1):
            cur.execute(step_sql)
            print(f"  [OK] DML step {i}/{len(DML_STEPS)}")

        # Cek jumlah data
        tables = ["roles", "users", "profil_penyewa", "kos", "tipe_kamar",
                  "kamar", "sewa", "pembayaran", "periode_pembayaran",
                  "request_maintenance", "riwayat_maintenance"]
        print()
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"  {t:30s} -> {count:,} baris")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [GAGAL] DML: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  SETUP SELESAI!")
    print("  Jalankan Streamlit:")
    print("    cd Implementasi")
    print("    streamlit run halaman.py")
    print("=" * 60)




if __name__ == "__main__":
    main()

