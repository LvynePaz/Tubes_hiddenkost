
ANALYZE sewa;
ANALYZE pembayaran;
ANALYZE kamar;
ANALYZE profil_penyewa;
ANALYZE request_maintenance;



-- 1. Sewa aktif milik 1 penyewa (dashboard penyewa)
-- Index: idx_sewa_penyewa_tglakhir(id_penyewa, tanggal_akhir)
-- Dari 600 baris, cuma 1-2 yg cocok → Index Scan jauh lebih cepat.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa
WHERE id_penyewa = 1 AND tanggal_akhir >= CURRENT_DATE;

-- 2. Sewa aktif di 1 kamar (cek status kamar)
-- Index: idx_sewa_kamar_tglakhir(id_kamar, tanggal_akhir)
-- 1 kamar dari 300, cuma 1-3 baris cocok → Index Scan menang.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa
WHERE id_kamar = 1 AND tanggal_akhir >= CURRENT_DATE;

-- 3. Pembayaran untuk 1 sewa (riwayat bayar)
-- Index: idx_pembayaran_id_sewa(id_sewa)
-- Relasi 1:1, pasti 1 baris → index langsung tunjuk baris yang tepat.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pembayaran WHERE id_sewa = 1;

-- 4. Periode pembayaran untuk 1 transaksi
-- Index: idx_periode_id_pembayaran(id_pembayaran)
-- Relasi 1:1, 1 baris per query.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM periode_pembayaran WHERE id_pembayaran = 1;

-- 5. Cari penyewa by nama (dashboard pemilik)
-- Index: index_nama_penyewa(nama_lengkap)
-- 450 nama unik, exact-match → index langsung temukan.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM profil_penyewa WHERE nama_lengkap = 'Penyewa ke-1';

-- 6. Cari kamar by nomor
-- Index: index_nomor_kamar(nomor)
-- Nomor unik per kos, 1 baris per query.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM kamar WHERE nomor = 'O-1';

-- 7. Maintenance milik 1 penyewa
-- Index: idx_reqmaint_id_penyewa(id_penyewa)
-- ~1 request per penyewa → selektivitas tinggi.
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM request_maintenance WHERE id_penyewa = 1;


-- ========================================
-- TITIK BERALIH — di % berapa planner pindah dari Index ke Seq Scan
-- ========================================
-- Kolom: sewa.tanggal_akhir
-- Query sama, tapi cutoff berubah → % data yg cocok berubah.
-- Cari titik di mana planner ganti dari Index Scan ke Seq Scan.

SELECT MIN(tanggal_akhir) AS tgl_awal, MAX(tanggal_akhir) AS tgl_akhir,
       COUNT(*) AS total FROM sewa;

-- ~1% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.99) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~5% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.95) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~10% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.90) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~20% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.80) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~30% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.70) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~50% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.50) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~80% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.20) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- ~100% data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= (
    SELECT percentile_disc(0.01) WITHIN GROUP (ORDER BY tanggal_akhir) FROM sewa);

-- Cara baca: cari baris pertama yg node berubah dari Index Scan ke Seq Scan.
-- Itu titik beralih. Di bawah titik itu index berguna, di atas titik itu Seq Scan lebih cepat.

-- 1. Cek jumlah baris sekarang
SELECT COUNT(*) AS total_sewa FROM sewa;

-- 2. Baseline: plan SEKARANG sebelum ditambah data
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_penyewa = 1;



-- Bisection Experiment: N = 2000
-- Semua operasi dalam BEGIN...ROLLBACK — data asli AMAN

BEGIN;

-- 1. Simpan 2000 baris sewa random
CREATE TEMP TABLE keep_ids AS
SELECT id_sewa FROM sewa ORDER BY random() LIMIT 2000;

-- 2. Hapus child: periode_pembayaran → pembayaran → sewa
DELETE FROM periode_pembayaran
WHERE id_pembayaran IN (
    SELECT id_pembayaran FROM pembayaran
    WHERE id_sewa NOT IN (SELECT id_sewa FROM keep_ids)
);

DELETE FROM pembayaran
WHERE id_sewa NOT IN (SELECT id_sewa FROM keep_ids);

-- 3. Hapus sewa yang tidak masuk sampel
DELETE FROM sewa
WHERE id_sewa NOT IN (SELECT id_sewa FROM keep_ids);

-- 4. Refresh statistik
ANALYZE sewa;

-- 5. Cari id_penyewa representatif
SELECT id_penyewa, COUNT(*) AS jumlah_baris
FROM sewa
GROUP BY id_penyewa
ORDER BY jumlah_baris DESC
LIMIT 10;

ROLLBACK;

-- 8. Verifikasi rollback — harus 50768
SELECT COUNT(*) FROM sewa;
