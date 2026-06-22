
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

SELECT
    pb.metode_bayar::TEXT AS "Metode",
    COUNT(*) AS "Jumlah Transaksi",
    SUM(pb.nominal) AS "Total"
FROM pembayaran pb
GROUP BY pb.metode_bayar
ORDER BY "Total" DESC;


SELECT
    (SELECT COUNT(*) FROM kamar) AS total_kamar,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Kosong') AS kamar_kosong,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Sedang disewa') AS kamar_terisi,
    (SELECT COALESCE(SUM(nominal),0) FROM pembayaran) AS total_pendapatan,
    (SELECT COUNT(*) FROM request_maintenance rm
        LEFT JOIN riwayat_maintenance rwm ON rwm.id_request_maintenance = rm.id_request_maintenance
        WHERE rwm.status IS DISTINCT FROM 'Selesai' OR rwm.status IS NULL) AS maintenance_belum_selesai;

SELECT
    (SELECT COUNT(*) FROM profil_penyewa WHERE status = 'Aktif') AS penyewa_aktif,
    (SELECT COUNT(*) FROM kamar WHERE status = 'Kosong') AS kamar_kosong,
    (SELECT COUNT(*) FROM kamar) AS total_kamar,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM kamar WHERE status = 'Sedang disewa')
        / (SELECT COUNT(*) FROM kamar), 2
    ) AS persen_okupansi;
