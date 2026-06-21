
-- ============================================
-- 1. ROLES
-- ============================================
INSERT INTO roles (nama_role) VALUES
('admin'),
('penyewa');

-- ============================================
-- 2. USERS — 2 admin + 998 penyewa
-- ============================================
INSERT INTO users(email, password, id_roles) VALUES
('admin1@hiddenkost.com', 'admin123', 1),
('admin2@hiddenkost.com', 'admin123', 1);

INSERT INTO users(email, password, id_roles)
SELECT
    'penyewa' || gs || '@gmail.com',
    'password123',
    2
FROM generate_series(1,998) gs;

-- ============================================
-- 3. PROFIL_PENYEWA — 450 penyewa
-- ============================================
INSERT INTO profil_penyewa
(nama_lengkap, pekerjaan, instansi, deskripsi_pekerjaan, status, url_ktp, id_user)
SELECT
    'Penyewa ke-' || gs,

    (ARRAY[
        'Mahasiswa','Karyawan Swasta','Pegawai BUMN',
        'Guru','Siswa','Wiraswasta'
    ])[floor(random()*6+1)],

    (ARRAY[
        'Institut Teknologi Kalimantan','Universitas Balikpapan',
        'Politeknik Negeri Balikpapan','STT Migas',
        'PT PLN Nusa Daya','PT Pertamina Hulu Mahakam',
        'PT Pamapersada Nusantara','PT Kilang Pertamina Balikpapan'
    ])[floor(random()*8+1)],

    (ARRAY[
        'Sistem Informasi','Informatika','Teknik Elektro',
        'Operator','Staff Administrasi','Supervisor',
        'Guru Matematika','Marketing'
    ])[floor(random()*8+1)],

    CASE WHEN random() < 0.8 THEN 'Aktif' ELSE 'Tidak aktif' END::status_penyewa,

    'ktp_' || gs || '.jpg',

    gs + 2   -- id_user 3..452 (1=admin1, 2=admin2)
FROM generate_series(1,450) gs;

-- ============================================
-- 4. KOS — 2 kos
-- ============================================
INSERT INTO kos(nama_kos, alamat) VALUES
('Hidden Kost Origin', 'Jl. Giri Rejo II No. 4B, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127'),
('Hidden Kost Lux', 'Jl. Giri Rejo II No. 42 RT.032, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127');

-- ============================================
-- 5. TIPE_KAMAR — 3 tipe (INSERT langsung, bukan UPDATE)
-- ============================================
INSERT INTO tipe_kamar (kategori, deskripsi_fasilitas, harga_sewa) VALUES
('Tipe A', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja belajar, kursi, gantungan baju, WC luar', 850000),
('Tipe B', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja belajar, kursi, gantungan baju, WC dalam', 1000000),
('Tipe C', 'Kasur, dipan, bantal guling, bantal kepala, sprei, AC, lemari, meja belajar, kursi, gantungan baju, WC dalam', 1500000);

-- ============================================
-- 6. KAMAR — Hidden Kost Origin (150 kamar, 5 lantai @ 30 kamar)
-- ============================================
INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'O-' || gs,
    12 + (random()*4)::int,
    (((gs - 1) / 30) + 1)::text,
    CASE WHEN random() < 0.6 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
    (SELECT id_tipe_kamar FROM tipe_kamar
     WHERE kategori = (ARRAY['Tipe A','Tipe B','Tipe C'])[((gs - 1) % 3) + 1]),
    (SELECT id_kos FROM kos WHERE nama_kos = 'Hidden Kost Origin')
FROM generate_series(1, 150) gs;

-- ============================================
-- 7. KAMAR — Hidden Kost Lux (150 kamar, 5 lantai @ 30 kamar)
-- ============================================
INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'L-' || gs,
    14 + (random()*4)::int,
    (((gs - 1) / 30) + 1)::text,
    CASE WHEN random() < 0.65 THEN 'Sedang disewa' ELSE 'Kosong' END::status_kamar,
    (SELECT id_tipe_kamar FROM tipe_kamar
     WHERE kategori = (ARRAY['Tipe A','Tipe B','Tipe C'])[((gs - 1) % 3) + 1]),
    (SELECT id_kos FROM kos WHERE nama_kos = 'Hidden Kost Lux')
FROM generate_series(1, 150) gs;

-- ============================================
-- 8. SEWA — 600 transaksi
--    id_penyewa & id_kamar diambil LANGSUNG dari tabel asli (aman dari FK error)
-- ============================================
INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
SELECT
    t.start_date,
    t.start_date +
        (ARRAY[30,90,180,365,730])[floor(random()*5+1)] * INTERVAL '1 day',
    p.id_penyewa,
    k.id_kamar
FROM (
    SELECT CURRENT_DATE - ((random()*1500)::int * INTERVAL '1 day') AS start_date
    FROM generate_series(1,600)
) t
CROSS JOIN LATERAL (
    SELECT id_penyewa FROM profil_penyewa ORDER BY random() LIMIT 1
) p
CROSS JOIN LATERAL (
    SELECT id_kamar FROM kamar ORDER BY random() LIMIT 1
) k;

-- ============================================
-- 9. PEMBAYARAN — 1 pembayaran per sewa
-- ============================================
INSERT INTO pembayaran (nominal, metode_bayar, id_sewa)
SELECT
    CASE
        WHEN random() < 0.33 THEN 850000
        WHEN random() < 0.66 THEN 1000000
        ELSE 1500000
    END,
    CASE WHEN random() < 0.5 THEN 'Transfer' ELSE 'Tunai' END::metode_pembayaran,
    id_sewa
FROM sewa;

-- ============================================
-- 10. SINKRONISASI — status kamar berdasarkan sewa aktif
-- ============================================
UPDATE kamar k
SET status = (CASE
    WHEN EXISTS (
        SELECT 1 FROM sewa s
        WHERE s.id_kamar = k.id_kamar
          AND s.tanggal_akhir >= CURRENT_DATE
    ) THEN 'Sedang disewa'
    ELSE 'Kosong'
END)::status_kamar;
-- ============================================
-- 11. PERIODE_PEMBAYARAN
-- ============================================
INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran)
SELECT
    TO_CHAR(CURRENT_DATE - ((random()*365)::int), 'YYYY-MM'),
    CASE WHEN random() < 0.9 THEN 'Berhasil' ELSE 'Gagal' END::status_pembayaran,
    id_pembayaran
FROM pembayaran;

-- ============================================
-- 12. REQUEST_MAINTENANCE — ~40% dari penyewa mengajukan
-- ============================================
INSERT INTO request_maintenance (deskripsi, id_penyewa)
SELECT
    (ARRAY[
        'Lampu kamar mati','AC tidak dingin','Kipas rusak',
        'Kunci pintu rusak','Keran bocor','WC mampet',
        'Stop kontak bermasalah','Jaringan internet lambat'
    ])[floor(random()*8+1)],
    id_penyewa
FROM profil_penyewa
WHERE random() < 0.4;

-- ============================================
-- 13. RIWAYAT_MAINTENANCE — 1 riwayat per request
-- ============================================
INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance)
SELECT
    CURRENT_DATE - ((random()*90)::int),
    CURRENT_DATE - ((random()*30)::int),
    (ARRAY['Tertunda','Sedang dikerjakan','Selesai'])[floor(random()*3+1)]::status_maintenance,
    id_request_maintenance
FROM request_maintenance;

-- ============================================
-- UPDATE NOMOR KAMAR — format KO1xx/KL1xx berdasarkan lantai (maks 3 lantai)
-- Jalankan setelah kamar sudah ada di database
-- ============================================

-- Origin: set lantai 1-3 secara merata, lalu generate nomor baru
WITH origin_numbered AS (
    SELECT id_kamar,
           ROW_NUMBER() OVER (ORDER BY id_kamar) AS urutan
    FROM kamar k
    JOIN kos ko ON k.id_kos = ko.id_kos
    WHERE ko.nama_kos = 'Hidden Kost Origin'
),
origin_total AS (
    SELECT COUNT(*) AS total FROM origin_numbered
)
UPDATE kamar k
SET
    lantai = CASE
        WHEN o.urutan <= CEIL(t.total / 3.0) THEN '1'
        WHEN o.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
        ELSE '3'
    END,
    nomor = 'KO' ||
        (CASE
            WHEN o.urutan <= CEIL(t.total / 3.0) THEN '1'
            WHEN o.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
            ELSE '3'
        END) ||
        LPAD(
            (
                CASE
                    WHEN o.urutan <= CEIL(t.total / 3.0) THEN o.urutan
                    WHEN o.urutan <= CEIL(t.total / 3.0) * 2 THEN o.urutan - CEIL(t.total / 3.0)::int
                    ELSE o.urutan - (CEIL(t.total / 3.0) * 2)::int
                END
            )::text, 2, '0'
        )
FROM origin_numbered o, origin_total t
WHERE k.id_kamar = o.id_kamar;

-- Lux: sama persis, ganti kode jadi KL
WITH lux_numbered AS (
    SELECT id_kamar,
           ROW_NUMBER() OVER (ORDER BY id_kamar) AS urutan
    FROM kamar k
    JOIN kos ko ON k.id_kos = ko.id_kos
    WHERE ko.nama_kos = 'Hidden Kost Lux'
),
lux_total AS (
    SELECT COUNT(*) AS total FROM lux_numbered
)
UPDATE kamar k
SET
    lantai = CASE
        WHEN l.urutan <= CEIL(t.total / 3.0) THEN '1'
        WHEN l.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
        ELSE '3'
    END,
    nomor = 'KL' ||
        (CASE
            WHEN l.urutan <= CEIL(t.total / 3.0) THEN '1'
            WHEN l.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
            ELSE '3'
        END) ||
        LPAD(
            (
                CASE
                    WHEN l.urutan <= CEIL(t.total / 3.0) THEN l.urutan
                    WHEN l.urutan <= CEIL(t.total / 3.0) * 2 THEN l.urutan - CEIL(t.total / 3.0)::int
                    ELSE l.urutan - (CEIL(t.total / 3.0) * 2)::int
                END
            )::text, 2, '0'
        )
FROM lux_numbered l, lux_total t
WHERE k.id_kamar = l.id_kamar;

-- ============================================
-- VERIFIKASI APAKAH DATANYA BENAR 
-- ============================================

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

-- Cek kamar yang statusnya 'Sedang disewa' TAPI tidak punya sewa aktif sama sekali
SELECT k.id_kamar, k.nomor, k.status,
       COUNT(s.id_sewa) AS jumlah_sewa_aktif
FROM kamar k
LEFT JOIN sewa s ON s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
WHERE k.status = 'Sedang disewa'
GROUP BY k.id_kamar, k.nomor, k.status
HAVING COUNT(s.id_sewa) = 0
ORDER BY k.nomor;

SELECT nomor, lantai, ko.nama_kos
FROM kamar k
JOIN kos ko ON k.id_kos = ko.id_kos
ORDER BY ko.nama_kos, lantai, nomor;

-- --- Hidden Kost Origin ---
WITH origin_numbered AS (
    SELECT k.id_kamar,
           ROW_NUMBER() OVER (ORDER BY k.id_kamar) AS urutan
    FROM kamar k
    JOIN kos ko ON k.id_kos = ko.id_kos
    WHERE ko.nama_kos = 'Hidden Kost Origin'
),
origin_total AS (
    SELECT COUNT(*) AS total FROM origin_numbered
)
UPDATE kamar k
SET
    lantai = sub.lantai_baru,
    nomor  = 'KO' || sub.lantai_baru || LPAD(sub.urutan_lantai::text, 2, '0')
FROM (
    SELECT
        o.id_kamar,
        o.urutan,
        CASE
            WHEN o.urutan <= CEIL(t.total / 3.0) THEN '1'
            WHEN o.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
            ELSE '3'
        END AS lantai_baru,
        CASE
            WHEN o.urutan <= CEIL(t.total / 3.0) THEN o.urutan
            WHEN o.urutan <= CEIL(t.total / 3.0) * 2 THEN o.urutan - CEIL(t.total / 3.0)::int
            ELSE o.urutan - (CEIL(t.total / 3.0) * 2)::int
        END AS urutan_lantai
    FROM origin_numbered o, origin_total t
) sub
WHERE k.id_kamar = sub.id_kamar;


-- --- Hidden Kost Lux ---
WITH lux_numbered AS (
    SELECT k.id_kamar,
           ROW_NUMBER() OVER (ORDER BY k.id_kamar) AS urutan
    FROM kamar k
    JOIN kos ko ON k.id_kos = ko.id_kos
    WHERE ko.nama_kos = 'Hidden Kost Lux'
),
lux_total AS (
    SELECT COUNT(*) AS total FROM lux_numbered
)
UPDATE kamar k
SET
    lantai = sub.lantai_baru,
    nomor  = 'KL' || sub.lantai_baru || LPAD(sub.urutan_lantai::text, 2, '0')
FROM (
    SELECT
        l.id_kamar,
        l.urutan,
        CASE
            WHEN l.urutan <= CEIL(t.total / 3.0) THEN '1'
            WHEN l.urutan <= CEIL(t.total / 3.0) * 2 THEN '2'
            ELSE '3'
        END AS lantai_baru,
        CASE
            WHEN l.urutan <= CEIL(t.total / 3.0) THEN l.urutan
            WHEN l.urutan <= CEIL(t.total / 3.0) * 2 THEN l.urutan - CEIL(t.total / 3.0)::int
            ELSE l.urutan - (CEIL(t.total / 3.0) * 2)::int
        END AS urutan_lantai
    FROM lux_numbered l, lux_total t
) sub
WHERE k.id_kamar = sub.id_kamar;


UPDATE kamar k
SET status = (
    CASE
        WHEN EXISTS (
            SELECT 1 FROM sewa s
            WHERE s.id_kamar = k.id_kamar
              AND s.tanggal_akhir >= CURRENT_DATE
        ) THEN 'Sedang disewa'
        ELSE 'Kosong'
    END
)::status_kamar;



WITH sewa_aktif_ranked AS (
    SELECT
        s.id_sewa,
        s.id_kamar,
        ROW_NUMBER() OVER (
            PARTITION BY s.id_kamar
            ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
        ) AS rn
    FROM sewa s
    WHERE s.tanggal_akhir >= CURRENT_DATE
),
sewa_duplikat AS (
    SELECT id_sewa FROM sewa_aktif_ranked WHERE rn > 1
)
DELETE FROM periode_pembayaran per
USING pembayaran pb
WHERE per.id_pembayaran = pb.id_pembayaran
  AND pb.id_sewa IN (SELECT id_sewa FROM sewa_duplikat);

WITH sewa_aktif_ranked AS (
    SELECT
        s.id_sewa,
        s.id_kamar,
        ROW_NUMBER() OVER (
            PARTITION BY s.id_kamar
            ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
        ) AS rn
    FROM sewa s
    WHERE s.tanggal_akhir >= CURRENT_DATE
),
sewa_duplikat AS (
    SELECT id_sewa FROM sewa_aktif_ranked WHERE rn > 1
)
DELETE FROM pembayaran pb
WHERE pb.id_sewa IN (SELECT id_sewa FROM sewa_duplikat);

WITH sewa_aktif_ranked AS (
    SELECT
        s.id_sewa,
        s.id_kamar,
        ROW_NUMBER() OVER (
            PARTITION BY s.id_kamar
            ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
        ) AS rn
    FROM sewa s
    WHERE s.tanggal_akhir >= CURRENT_DATE
),
sewa_duplikat AS (
    SELECT id_sewa FROM sewa_aktif_ranked WHERE rn > 1
)
DELETE FROM sewa
WHERE id_sewa IN (SELECT id_sewa FROM sewa_duplikat);

-- Setelah menghapus sewa duplikat di atas, status kamar bisa berubah
-- (kamar yang tadinya dianggap 'Sedang disewa' karena sewa duplikat
-- tetap 'Sedang disewa' selama masih ada 1 sewa aktif tersisa, jadi
-- BAGIAN 2 di atas tidak perlu diulang lagi -- statusnya tetap valid).


-- =====================================================================
-- BAGIAN 4: VERIFIKASI HASIL PERBAIKAN
-- =====================================================================

-- Lantai sudah merata 1, 2, 3?
SELECT ko.nama_kos, k.lantai, COUNT(*) AS jumlah_kamar
FROM kamar k
JOIN kos ko ON k.id_kos = ko.id_kos
GROUP BY ko.nama_kos, k.lantai
ORDER BY ko.nama_kos, k.lantai;

-- Harus 0 baris (tidak ada lagi kamar 'Sedang disewa' tanpa sewa aktif)
SELECT k.id_kamar, k.nomor, k.status, COUNT(s.id_sewa) AS jumlah_sewa_aktif
FROM kamar k
LEFT JOIN sewa s ON s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
WHERE k.status = 'Sedang disewa'
GROUP BY k.id_kamar, k.nomor, k.status
HAVING COUNT(s.id_sewa) = 0;

-- Harus 0 baris juga (tidak ada lagi kamar dengan >1 sewa aktif bersamaan)
SELECT k.id_kamar, k.nomor, COUNT(*) AS sewa_aktif_bersamaan
FROM kamar k
JOIN sewa s ON s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
GROUP BY k.id_kamar, k.nomor
HAVING COUNT(*) > 1;

-- Cek contoh nomor kamar baru
SELECT nomor, lantai, ko.nama_kos
FROM kamar k
JOIN kos ko ON k.id_kos = ko.id_kos
ORDER BY ko.nama_kos, lantai, nomor;