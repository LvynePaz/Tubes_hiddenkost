SELECT (
        SELECT COUNT(*)
        FROM profil_penyewa
        WHERE
            status = 'Aktif'
    ) AS penyewa_aktif,
    (
        SELECT COUNT(*)
        FROM kamar
        WHERE
            status = 'Kosong'
    ) AS kamar_kosong,
    (
        SELECT COUNT(*)
        FROM kamar
    ) AS total_kamar;

-- ---------------------------------------------------------------------
-- B. Naikkan rasio kamar terisi
-- Pendekatan paling aman: TIDAK mengubah jumlah baris profil_penyewa
-- atau kamar (struktur data tetap), tapi mengurangi kamar yang
-- KOSONG dengan cara membuatkan SEWA BARU untuk kamar kosong,
-- menggunakan penyewa AKTIF yang BELUM punya sewa aktif saat ini.
--
-- Target: hanya sisakan sedikit kamar kosong (mis. ±10% dari total),
-- sisanya terisi -> otomatis status_kamar berubah 'Sedang disewa'.
-- ---------------------------------------------------------------------

-- B1. Buat sewa baru untuk kamar yang kosong, dipasangkan dengan
--     penyewa aktif yang BELUM memiliki sewa aktif sekarang,
--     SISAKAN sekitar 10% kamar tetap kosong secara acak.
WITH
    kamar_kosong_terpilih AS (
        SELECT id_kamar
        FROM kamar
        WHERE
            status = 'Kosong'
        ORDER BY random()
            -- sisakan ~10% kamar kosong, isi sisanya (90%)
        OFFSET (
                SELECT CEIL(COUNT(*) * 0.10)
                FROM kamar
                WHERE
                    status = 'Kosong'
            )::int
    ),
    penyewa_tersedia AS (
        SELECT pp.id_penyewa
        FROM profil_penyewa pp
        WHERE
            pp.status = 'Aktif'
            AND NOT EXISTS (
                SELECT 1
                FROM sewa s
                WHERE
                    s.id_penyewa = pp.id_penyewa
                    AND s.tanggal_akhir >= CURRENT_DATE
            )
        ORDER BY random()
    ),
    pasangan AS (
        SELECT k.id_kamar, p.id_penyewa, ROW_NUMBER() OVER (
                ORDER BY random()
            ) AS rn
        FROM kamar_kosong_terpilih k
            CROSS JOIN LATERAL (
                SELECT id_penyewa
                FROM penyewa_tersedia
                OFFSET (
                        (
                            SELECT COUNT(*)
                            FROM kamar_kosong_terpilih kk
                            WHERE
                                kk.id_kamar < k.id_kamar
                        )
                    )
                LIMIT 1
            ) p
    )
INSERT INTO
    sewa (
        tanggal_mulai,
        tanggal_akhir,
        id_penyewa,
        id_kamar
    )
SELECT CURRENT_DATE - ((random() * 60)::int), CURRENT_DATE + (ARRAY[180, 365, 730]) [floor(random() * 3 + 1)] * INTERVAL '1 day', pas.id_penyewa, pas.id_kamar
FROM (
        -- pasangkan kamar kosong dengan penyewa tersedia 1-ke-1 tanpa duplikat
        SELECT kk.id_kamar, pt.id_penyewa
        FROM (
                SELECT id_kamar, ROW_NUMBER() OVER (
                        ORDER BY random()
                    ) AS rn
                FROM kamar_kosong_terpilih
            ) kk
            JOIN (
                SELECT id_penyewa, ROW_NUMBER() OVER (
                        ORDER BY random()
                    ) AS rn
                FROM penyewa_tersedia
            ) pt ON pt.rn = kk.rn
    ) pas;

-- B2. Tambahkan pembayaran untuk sewa baru tersebut (1 pembayaran/sewa)
INSERT INTO
    pembayaran (
        nominal,
        metode_bayar,
        id_sewa
    )
SELECT
    tk.harga_sewa, -- nominal MENGIKUTI harga sewa kamar (konsisten!)
    CASE
        WHEN random() < 0.5 THEN 'Transfer'
        ELSE 'Tunai'
    END::metode_pembayaran,
    s.id_sewa
FROM
    sewa s
    JOIN kamar k ON s.id_kamar = k.id_kamar
    JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
WHERE
    s.id_sewa NOT IN (
        SELECT id_sewa
        FROM pembayaran
    )
    AND s.tanggal_akhir >= CURRENT_DATE;

-- B3. Tambahkan periode pembayaran (status Berhasil) untuk pembayaran baru
INSERT INTO
    periode_pembayaran (
        periode_bayar,
        status,
        id_pembayaran
    )
SELECT TO_CHAR(CURRENT_DATE, 'YYYY-MM'), 'Berhasil'::status_pembayaran, pb.id_pembayaran
FROM pembayaran pb
WHERE
    pb.id_pembayaran NOT IN (
        SELECT id_pembayaran
        FROM periode_pembayaran
    );

-- ---------------------------------------------------------------------
-- C. Sinkronkan ulang status kamar (WAJIB dijalankan setelah B)
-- ---------------------------------------------------------------------
UPDATE kamar k
SET
    status = (
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM sewa s
                WHERE
                    s.id_kamar = k.id_kamar
                    AND s.tanggal_akhir >= CURRENT_DATE
            ) THEN 'Sedang disewa'
            ELSE 'Kosong'
        END
    )::status_kamar;

-- ---------------------------------------------------------------------
-- D. Verifikasi hasil akhir — penyewa aktif harus JAUH lebih banyak
--    dari kamar kosong.
-- ---------------------------------------------------------------------
SELECT (
        SELECT COUNT(*)
        FROM profil_penyewa
        WHERE
            status = 'Aktif'
    ) AS penyewa_aktif,
    (
        SELECT COUNT(*)
        FROM kamar
        WHERE
            status = 'Kosong'
    ) AS kamar_kosong,
    (
        SELECT COUNT(*)
        FROM kamar
        WHERE
            status = 'Sedang disewa'
    ) AS kamar_terisi,
    (
        SELECT COUNT(*)
        FROM kamar
    ) AS total_kamar;

--------------------------------------------------------------------------- batas

-- =====================================================================
-- CEK_SELISIH_PENYEWA_KAMAR.SQL
-- Mencari akar penyebab kenapa "penyewa sedang sewa" (356) bisa lebih
-- besar dari "kamar terisi" (270).
--
-- Kemungkinan #1 (paling mungkin): satu kamar punya LEBIH DARI SATU
-- sewa aktif bersamaan (tanggal_akhir >= CURRENT_DATE untuk lebih
-- dari satu baris sewa dengan id_kamar yang sama). Dashboard hanya
-- menghitung 1 baris per kamar (kamar.status), tapi COUNT(DISTINCT
-- id_penyewa) di tabel sewa menghitung SEMUA penyewa yang "nempel"
-- di kamar manapun -> bisa lebih banyak dari jumlah kamar.
-- =====================================================================

-- ---------------------------------------------------------------------
-- A. Cari kamar dengan lebih dari 1 sewa aktif bersamaan
--    Kalau hasil SUM(kelebihan) mendekati (356 - 270 = 86), ini
--    konfirmasi penyebabnya.
-- ---------------------------------------------------------------------
SELECT
    k.id_kamar,
    k.nomor,
    COUNT(*) AS jumlah_sewa_aktif_bersamaan,
    COUNT(*) - 1 AS kelebihan
FROM kamar k
    JOIN sewa s ON s.id_kamar = k.id_kamar
    AND s.tanggal_akhir >= CURRENT_DATE
GROUP BY
    k.id_kamar,
    k.nomor
HAVING
    COUNT(*) > 1
ORDER BY jumlah_sewa_aktif_bersamaan DESC;

-- Total kelebihan penyewa akibat kamar bentrok (harusnya ≈ 86 jika
-- ini adalah satu-satunya penyebab selisih 356 vs 270):
SELECT COALESCE(SUM(kelebihan), 0) AS total_kelebihan_penyewa
FROM (
        SELECT COUNT(*) - 1 AS kelebihan
        FROM kamar k
            JOIN sewa s ON s.id_kamar = k.id_kamar
            AND s.tanggal_akhir >= CURRENT_DATE
        GROUP BY
            k.id_kamar
        HAVING
            COUNT(*) > 1
    ) x;

-- ---------------------------------------------------------------------
-- B. PERBAIKAN: hapus sewa bentrok, sisakan HANYA 1 sewa aktif
--    (yang paling baru / tanggal_mulai terbesar) per kamar.
--    Urutan hapus WAJIB: periode_pembayaran -> pembayaran -> sewa
--    (mengikuti foreign key).
--
--    Setelah ini, COUNT(DISTINCT id_penyewa) dari sewa aktif akan
--    PERSIS SAMA dengan jumlah kamar berstatus 'Sedang disewa'.
-- ---------------------------------------------------------------------

WITH
    sewa_aktif_ranked AS (
        SELECT s.id_sewa, s.id_kamar, ROW_NUMBER() OVER (
                PARTITION BY
                    s.id_kamar
                ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
            ) AS rn
        FROM sewa s
        WHERE
            s.tanggal_akhir >= CURRENT_DATE
    ),
    sewa_duplikat AS (
        SELECT id_sewa
        FROM sewa_aktif_ranked
        WHERE
            rn > 1
    )
DELETE FROM periode_pembayaran per USING pembayaran pb
WHERE
    per.id_pembayaran = pb.id_pembayaran
    AND pb.id_sewa IN (
        SELECT id_sewa
        FROM sewa_duplikat
    );

WITH
    sewa_aktif_ranked AS (
        SELECT s.id_sewa, s.id_kamar, ROW_NUMBER() OVER (
                PARTITION BY
                    s.id_kamar
                ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
            ) AS rn
        FROM sewa s
        WHERE
            s.tanggal_akhir >= CURRENT_DATE
    ),
    sewa_duplikat AS (
        SELECT id_sewa
        FROM sewa_aktif_ranked
        WHERE
            rn > 1
    )
DELETE FROM pembayaran pb
WHERE
    pb.id_sewa IN (
        SELECT id_sewa
        FROM sewa_duplikat
    );

WITH
    sewa_aktif_ranked AS (
        SELECT s.id_sewa, s.id_kamar, ROW_NUMBER() OVER (
                PARTITION BY
                    s.id_kamar
                ORDER BY s.tanggal_mulai DESC, s.id_sewa DESC
            ) AS rn
        FROM sewa s
        WHERE
            s.tanggal_akhir >= CURRENT_DATE
    ),
    sewa_duplikat AS (
        SELECT id_sewa
        FROM sewa_aktif_ranked
        WHERE
            rn > 1
    )
DELETE FROM sewa
WHERE
    id_sewa IN (
        SELECT id_sewa
        FROM sewa_duplikat
    );

-- ---------------------------------------------------------------------
-- C. Sinkronkan ulang status kamar (jaga-jaga)
-- ---------------------------------------------------------------------
UPDATE kamar k
SET
    status = (
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM sewa s
                WHERE
                    s.id_kamar = k.id_kamar
                    AND s.tanggal_akhir >= CURRENT_DATE
            ) THEN 'Sedang disewa'
            ELSE 'Kosong'
        END
    )::status_kamar;

-- ---------------------------------------------------------------------
-- D. Verifikasi akhir — kedua angka ini HARUS SAMA sekarang
-- ---------------------------------------------------------------------
SELECT (
        SELECT COUNT(*)
        FROM kamar
        WHERE
            status = 'Sedang disewa'
    ) AS kamar_terisi,
    (
        SELECT COUNT(DISTINCT s.id_penyewa)
        FROM sewa s
        WHERE
            s.tanggal_akhir >= CURRENT_DATE
    ) AS penyewa_sedang_sewa;

-- Pastikan 0 baris (tidak ada lagi kamar dengan sewa bentrok)
SELECT
    k.id_kamar,
    k.nomor,
    COUNT(*) AS jumlah_sewa_aktif_bersamaan
FROM kamar k
    JOIN sewa s ON s.id_kamar = k.id_kamar
    AND s.tanggal_akhir >= CURRENT_DATE
GROUP BY
    k.id_kamar,
    k.nomor
HAVING
    COUNT(*) > 1;