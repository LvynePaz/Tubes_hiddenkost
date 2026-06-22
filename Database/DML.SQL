-- =====================================================================
-- 02. DML — Data Manipulation Language (Data Dummy / Seeding)
-- Proyek: Hidden Kost
-- Urutan WAJIB ikut urutan ini karena ada dependensi Foreign Key.
-- Sumber asli: Database/DML.SQL
-- =====================================================================

-- 1) ROLES
INSERT INTO roles (nama_role) VALUES
('admin'),
('penyewa');

-- 2) USERS — 2 admin + 998 akun penyewa (generate_series untuk volume)
INSERT INTO users(email, password, id_roles) VALUES
('admin1@hiddenkost.com', 'admin123', 1),
('admin2@hiddenkost.com', 'admin123', 1);

INSERT INTO users(email, password, id_roles)
SELECT 'penyewa' || gs || '@gmail.com', 'password123', 2
FROM generate_series(1,998) gs;

-- 3) PROFIL_PENYEWA — 450 profil dengan data acak realistis
INSERT INTO profil_penyewa
(nama_lengkap, pekerjaan, instansi, deskripsi_pekerjaan, status, url_ktp, id_user)
SELECT
    'Penyewa ke-' || gs,
    (ARRAY['Mahasiswa','Karyawan Swasta','Pegawai BUMN','Guru','Siswa','Wiraswasta'])[floor(random()*6+1)],
    (ARRAY['Institut Teknologi Kalimantan','Universitas Balikpapan','Politeknik Negeri Balikpapan',
           'STT Migas','PT PLN Nusa Daya','PT Pertamina Hulu Mahakam',
           'PT Pamapersada Nusantara','PT Kilang Pertamina Balikpapan'])[floor(random()*8+1)],
    (ARRAY['Sistem Informasi','Informatika','Teknik Elektro','Operator',
           'Staff Administrasi','Supervisor','Guru Matematika','Marketing'])[floor(random()*8+1)],
    CASE WHEN random() < 0.8 THEN 'Aktif' ELSE 'Tidak aktif' END::status_penyewa,
    'ktp_' || gs || '.jpg',
    gs + 2
FROM generate_series(1,450) gs;

-- 4) KOS — 2 properti
INSERT INTO kos(nama_kos, alamat) VALUES
('Hidden Kost Origin', 'Jl. Giri Rejo II No. 4B, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127'),
('Hidden Kost Lux', 'Jl. Giri Rejo II No. 42 RT.032, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127');

-- 5) TIPE_KAMAR — 3 tipe + harga sewa
INSERT INTO tipe_kamar (kategori, deskripsi_fasilitas, harga_sewa) VALUES
('Tipe A', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja belajar, kursi, gantungan baju, WC luar', 850000),
('Tipe B', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja belajar, kursi, gantungan baju, WC dalam', 1000000),
('Tipe C', 'Kasur, dipan, bantal guling, bantal kepala, sprei, AC, lemari, meja belajar, kursi, gantungan baju, WC dalam', 1500000);

-- 6) KAMAR — Hidden Kost Origin (150 kamar)
INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'O-' || gs,
    12 + (random()*4)::int,
    (((gs - 1) / 30) + 1)::text,
    CASE WHEN random() < 0.6 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
    (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori = (ARRAY['Tipe A','Tipe B','Tipe C'])[((gs - 1) % 3) + 1]),
    (SELECT id_kos FROM kos WHERE nama_kos = 'Hidden Kost Origin')
FROM generate_series(1, 150) gs;

-- 7) KAMAR — Hidden Kost Lux (150 kamar)
INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'L-' || gs,
    14 + (random()*4)::int,
    (((gs - 1) / 30) + 1)::text,
    CASE WHEN random() < 0.65 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
    (SELECT id_tipe_kamar FROM tipe_kamar WHERE kategori = (ARRAY['Tipe A','Tipe B','Tipe C'])[((gs - 1) % 3) + 1]),
    (SELECT id_kos FROM kos WHERE nama_kos = 'Hidden Kost Lux')
FROM generate_series(1, 150) gs;

-- 8) SEWA — 600 transaksi (data ini yang membuat tabel "sewa" jadi tabel
--    OLTP paling sibuk -> alasan kenapa index khusus dibuat di file 05)
INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
SELECT
    t.start_date,
    t.start_date + (ARRAY[30,90,180,365,730])[floor(random()*5+1)] * INTERVAL '1 day',
    p.id_penyewa,
    k.id_kamar
FROM (
    SELECT CURRENT_DATE - ((random()*1500)::int * INTERVAL '1 day') AS start_date
    FROM generate_series(1,600)
) t
CROSS JOIN LATERAL (SELECT id_penyewa FROM profil_penyewa ORDER BY random() LIMIT 1) p
CROSS JOIN LATERAL (SELECT id_kamar FROM kamar ORDER BY random() LIMIT 1) k;

-- 9) PEMBAYARAN — 1 pembayaran per sewa
INSERT INTO pembayaran (nominal, metode_bayar, id_sewa)
SELECT
    CASE WHEN random() < 0.33 THEN 850000
         WHEN random() < 0.66 THEN 1000000
         ELSE 1500000 END,
    CASE WHEN random() < 0.5 THEN 'Transfer' ELSE 'Tunai' END::metode_pembayaran,
    id_sewa
FROM sewa;

-- 10) SINKRONISASI status kamar berdasarkan sewa yang masih aktif
UPDATE kamar k
SET status = (CASE
    WHEN EXISTS (
        SELECT 1 FROM sewa s
        WHERE s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
    ) THEN 'Sedang disewa'
    ELSE 'Kosong'
END)::status_kamar;

-- 11) PERIODE_PEMBAYARAN — riwayat status bayar per bulan
INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran)
SELECT
    TO_CHAR(CURRENT_DATE - ((random()*365)::int), 'YYYY-MM'),
    CASE WHEN random() < 0.9 THEN 'Berhasil' ELSE 'Gagal' END::status_pembayaran,
    id_pembayaran
FROM pembayaran;

-- 12) REQUEST_MAINTENANCE — ~40% penyewa pernah mengajukan keluhan
INSERT INTO request_maintenance (deskripsi, id_penyewa)
SELECT
    (ARRAY['Lampu kamar mati','AC tidak dingin','Kipas rusak','Kunci pintu rusak',
           'Keran bocor','WC mampet','Stop kontak bermasalah','Jaringan internet lambat'])[floor(random()*8+1)],
    id_penyewa
FROM profil_penyewa
WHERE random() < 0.4;

-- 13) RIWAYAT_MAINTENANCE — 1 riwayat per request
INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance)
SELECT
    CURRENT_DATE - ((random()*90)::int),
    CURRENT_DATE - ((random()*30)::int),
    (ARRAY['Tertunda','Sedang dikerjakan','Selesai'])[floor(random()*3+1)]::status_maintenance,
    id_request_maintenance
FROM request_maintenance;

-- ---------------------------------------------------------------------
-- VERIFIKASI VOLUME DATA (jalankan setelah seeding selesai)
-- ---------------------------------------------------------------------
SELECT 'kos' AS tabel, COUNT(*) FROM kos
UNION ALL SELECT 'tipe_kamar', COUNT(*) FROM tipe_kamar
UNION ALL SELECT 'kamar', COUNT(*) FROM kamar
UNION ALL SELECT 'roles', COUNT(*) FROM roles
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'profil_penyewa', COUNT(*) FROM profil_penyewa
UNION ALL SELECT 'sewa', COUNT(*) FROM sewa
UNION ALL SELECT 'pembayaran', COUNT(*) FROM pembayaran
UNION ALL SELECT 'periode_pembayaran', COUNT(*) FROM periode_pembayaran
UNION ALL SELECT 'request_maintenance', COUNT(*) FROM request_maintenance
UNION ALL SELECT 'riwayat_maintenance', COUNT(*) FROM riwayat_maintenance;

-- Catatan: script perbaikan data (sewa bentrok/duplikat, normalisasi nomor
-- kamar per lantai) dipindahkan ke file terpisah "buat baikin query.sql"
-- karena itu BUKAN seeding awal, melainkan data-fix -- tidak relevan untuk
-- dijalankan ulang di database yang bersih/baru.