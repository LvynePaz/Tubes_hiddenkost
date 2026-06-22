
-- ---------------------------------------------------------------------
-- OLTP-1: Lihat data kamar saat ini (tampilan tabel kamar admin)
-- ---------------------------------------------------------------------
SELECT
    k.nomor AS "Nomor",
    k.status AS "Status",
    k.luas, k.lantai
FROM kamar k
WHERE k.id_kos = %(id_kos)s
ORDER BY k.nomor;

-- ---------------------------------------------------------------------
-- OLTP-2: Sewa aktif milik 1 penyewa (Dashboard Penyewa "Sewa Saya")
-- Query paling sering dipanggil tiap kali penyewa login/refresh dashboard.
-- ---------------------------------------------------------------------
SELECT s.id_sewa, s.id_kamar, s.tanggal_mulai, s.tanggal_akhir
FROM sewa s
WHERE s.id_penyewa = %(id_penyewa)s
  AND s.tanggal_akhir >= CURRENT_DATE;

-- ---------------------------------------------------------------------
-- OLTP-3: Sewa yang sedang berjalan pada 1 kamar tertentu
-- Dipakai saat admin cek status kamar / proses sinkronisasi
-- ---------------------------------------------------------------------
SELECT s.id_sewa, s.tanggal_mulai, s.tanggal_akhir
FROM sewa s
WHERE s.id_kamar = %(id_kamar)s
  AND s.tanggal_akhir >= CURRENT_DATE;

-- ---------------------------------------------------------------------
-- OLTP-4: Cari profil penyewa by nama (search bar admin)
-- ---------------------------------------------------------------------
SELECT * FROM profil_penyewa WHERE nama_lengkap = %(nama)s;

-- ---------------------------------------------------------------------
-- OLTP-5: Daftar penyewa aktif (admin -> Tab Penyewa)
-- ---------------------------------------------------------------------
SELECT pp.nama_lengkap AS "Nama", pp.pekerjaan, pp.status
FROM profil_penyewa pp
WHERE pp.status = 'Aktif';

-- ---------------------------------------------------------------------
-- OLTP-6: Daftar kamar kosong (admin -> Tab Kamar Kosong)
-- ---------------------------------------------------------------------
SELECT * FROM kamar WHERE status = 'Kosong';

-- ---------------------------------------------------------------------
-- OLTP-7: Riwayat pembayaran untuk 1 sewa
-- ---------------------------------------------------------------------
SELECT * FROM pembayaran WHERE id_sewa = %(id_sewa)s;

-- ---------------------------------------------------------------------
-- OLTP-8: Status periode bayar untuk 1 pembayaran (cek lunas/belum)
-- ---------------------------------------------------------------------
SELECT * FROM periode_pembayaran WHERE id_pembayaran = %(id_pembayaran)s;

-- ---------------------------------------------------------------------
-- OLTP-9: Riwayat keluhan maintenance milik 1 penyewa
-- ---------------------------------------------------------------------
SELECT * FROM request_maintenance WHERE id_penyewa = %(id_penyewa)s;

-- ---------------------------------------------------------------------
-- OLTP-10: INSERT sewa baru (transaksi penyewaan kamar)
-- ---------------------------------------------------------------------
INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
VALUES (%(tanggal_mulai)s, %(tanggal_akhir)s, %(id_penyewa)s, %(id_kamar)s);

-- ---------------------------------------------------------------------
-- OLTP-11: UPDATE status kamar setelah sewa baru / berakhir
-- ---------------------------------------------------------------------
UPDATE kamar
SET status = (CASE
    WHEN EXISTS (
        SELECT 1 FROM sewa s
        WHERE s.id_kamar = kamar.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
    ) THEN 'Sedang disewa' ELSE 'Kosong' END)::status_kamar
WHERE id_kamar = %(id_kamar)s;

-- ---------------------------------------------------------------------
-- OLTP-12: Ajukan request maintenance baru (penyewa)
-- ---------------------------------------------------------------------
INSERT INTO request_maintenance (deskripsi, id_penyewa)
VALUES (%(deskripsi)s, %(id_penyewa)s);

-- ---------------------------------------------------------------------
-- OLTP-13: Admin update progres maintenance
-- ---------------------------------------------------------------------
UPDATE riwayat_maintenance
SET status = %(status)s, tanggal_selesai = %(tanggal_selesai)s
WHERE id_request_maintenance = %(id_request_maintenance)s;