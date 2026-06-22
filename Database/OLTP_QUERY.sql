

SELECT
    k.nomor AS "Nomor",
    k.status AS "Status",
    k.luas, k.lantai
FROM kamar k
WHERE k.id_kos = %(id_kos)s
ORDER BY k.nomor;

SELECT s.id_sewa, s.id_kamar, s.tanggal_mulai, s.tanggal_akhir
FROM sewa s
WHERE s.id_penyewa = %(id_penyewa)s
  AND s.tanggal_akhir >= CURRENT_DATE;


SELECT s.id_sewa, s.tanggal_mulai, s.tanggal_akhir
FROM sewa s
WHERE s.id_kamar = %(id_kamar)s
  AND s.tanggal_akhir >= CURRENT_DATE;


SELECT * FROM profil_penyewa WHERE nama_lengkap = %(nama)s;


SELECT pp.nama_lengkap AS "Nama", pp.pekerjaan, pp.status
FROM profil_penyewa pp
WHERE pp.status = 'Aktif';

SELECT * FROM kamar WHERE status = 'Kosong';

SELECT * FROM pembayaran WHERE id_sewa = %(id_sewa)s;

SELECT * FROM periode_pembayaran WHERE id_pembayaran = %(id_pembayaran)s;

SELECT * FROM request_maintenance WHERE id_penyewa = %(id_penyewa)s;

INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
VALUES (%(tanggal_mulai)s, %(tanggal_akhir)s, %(id_penyewa)s, %(id_kamar)s);

UPDATE kamar
SET status = (CASE
    WHEN EXISTS (
        SELECT 1 FROM sewa s
        WHERE s.id_kamar = kamar.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
    ) THEN 'Sedang disewa' ELSE 'Kosong' END)::status_kamar
WHERE id_kamar = %(id_kamar)s;

INSERT INTO request_maintenance (deskripsi, id_penyewa)
VALUES (%(deskripsi)s, %(id_penyewa)s);

UPDATE riwayat_maintenance
SET status = %(status)s, tanggal_selesai = %(tanggal_selesai)s
WHERE id_request_maintenance = %(id_request_maintenance)s;