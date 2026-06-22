
-- ---------------------------------------------------------------------
-- OLAP-1: Total pendapatan per properti kos
-- Dipakai di: Dashboard Admin > Tab Pendapatan
-- ---------------------------------------------------------------------
SELECT
    ko.nama_kos AS "Nama Kos",
    COUNT(DISTINCT s.id_sewa) AS "Jumlah Sewa",
    COALESCE(SUM(pb.nominal), 0) AS "Total Pendapatan"
FROM kos ko
JOIN kamar k       ON k.id_kos = ko.id_kos
JOIN sewa s        ON s.id_kamar = k.id_kamar
JOIN pembayaran pb ON pb.id_sewa = s.id_sewa
GROUP BY ko.nama_kos
ORDER BY "Total Pendapatan" DESC;

-- ---------------------------------------------------------------------
-- OLAP-2: Total pendapatan per tipe kamar
-- Dipakai di: Dashboard Admin > Tab Pendapatan
-- ---------------------------------------------------------------------
SELECT
    tk.kategori AS "Tipe",
    tk.harga_sewa AS "Harga Sewa",
    COUNT(s.id_sewa) AS "Jumlah Sewa",
    COALESCE(SUM(pb.nominal), 0) AS "Total Pendapatan"
FROM tipe_kamar tk
JOIN kamar k       ON k.id_tipe_kamar = tk.id_tipe_kamar
JOIN sewa s        ON s.id_kamar = k.id_kamar
JOIN pembayaran pb ON pb.id_sewa = s.id_sewa
GROUP BY tk.kategori, tk.harga_sewa
ORDER BY "Total Pendapatan" DESC;

-- ---------------------------------------------------------------------
-- OLAP-3: Distribusi metode pembayaran (Tunai vs Transfer)
-- Dipakai di: Dashboard Admin > Tab Pembayaran
-- ---------------------------------------------------------------------
SELECT
    pb.metode_bayar::TEXT AS "Metode",
    COUNT(*) AS "Jumlah Transaksi",
    SUM(pb.nominal) AS "Total"
FROM pembayaran pb
GROUP BY pb.metode_bayar
ORDER BY "Total" DESC;

-- ---------------------------------------------------------------------
-- OLAP-4: KPI ringkasan dashboard admin (kartu statistik di halaman utama)
-- Dipakai di: halaman.py baris ~463-470
-- ---------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM kamar) AS total_kamar,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Kosong') AS kamar_kosong,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Sedang disewa') AS kamar_terisi,
    (SELECT COALESCE(SUM(nominal),0) FROM pembayaran) AS total_pendapatan,
    (SELECT COUNT(*) FROM request_maintenance rm
        LEFT JOIN riwayat_maintenance rwm ON rwm.id_request_maintenance = rm.id_request_maintenance
        WHERE rwm.status IS DISTINCT FROM 'Selesai' OR rwm.status IS NULL) AS maintenance_belum_selesai;

-- ---------------------------------------------------------------------
-- OLAP-5: Okupansi / tingkat hunian (agregasi status kamar & penyewa)
-- ---------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM profil_penyewa WHERE status = 'Aktif') AS penyewa_aktif,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Kosong') AS kamar_kosong,
    (SELECT COUNT(*) FROM kamar) AS total_kamar,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM kamar WHERE status = 'Sedang disewa')
        / (SELECT COUNT(*) FROM kamar), 2
    ) AS persen_okupansi;

-- =====================================================================
-- CATATAN OLAP vs OLTP
-- Query di atas SECARA SADAR tidak diberi index khusus per-kolom seperti
-- file 04, karena sifatnya full-aggregate (memang harus baca banyak baris
-- untuk SUM/COUNT). Optimasi yang relevan untuk OLAP biasanya bukan index
-- tunggal, melainkan:
--   - Materialized View (precompute hasil agregasi, refresh berkala)
--   - Composite index yang MENCAKUP kolom JOIN (membantu, tapi tidak
--     menghindari scan baris yang relevan)
-- Lihat rekomendasi di bagian akhir file 05.
-- =====================================================================