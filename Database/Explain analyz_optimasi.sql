
DROP INDEX IF EXISTS idx_sewa_id_penyewa;
DROP INDEX IF EXISTS idx_sewa_id_kamar;
DROP INDEX IF EXISTS idx_sewa_tanggal_akhir;
DROP INDEX IF EXISTS idx_sewa_penyewa_tglakhir;
DROP INDEX IF EXISTS idx_sewa_kamar_tglakhir;
DROP INDEX IF EXISTS idx_pembayaran_id_sewa;
DROP INDEX IF EXISTS idx_periode_id_pembayaran;
DROP INDEX IF EXISTS idx_reqmaint_id_penyewa;

SET enable_indexscan = off;
SET enable_bitmapscan = off;
SET enable_indexonlyscan = off;

-- Query 1: dashboard penyewa -> sewa milik 1 penyewa yang masih aktif
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_penyewa = 1 AND tanggal_akhir >= CURRENT_DATE;

-- Query 2: cek status 1 kamar -> sewa aktif untuk kamar tertentu
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_kamar = 1 AND tanggal_akhir >= CURRENT_DATE;

-- Query 3: semua sewa yang masih aktif (dipakai di proses sinkronisasi status kamar)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= CURRENT_DATE;

-- Query 4: riwayat pembayaran 1 sewa
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pembayaran WHERE id_sewa = 1;

-- KEMBALIKAN setting ke index 
SET enable_indexscan = on;
SET enable_bitmapscan = on;
SET enable_indexonlyscan = on;

-- 1a. FK id_penyewa di tabel sewa
--     Query: WHERE id_penyewa = X  (dashboard penyewa, OLTP-2)
CREATE INDEX IF NOT EXISTS idx_sewa_id_penyewa ON sewa(id_penyewa);

-- 1b. FK id_kamar di tabel sewa
--     Query: WHERE id_kamar = X  (cek status kamar, OLTP-3, sinkronisasi)
CREATE INDEX IF NOT EXISTS idx_sewa_id_kamar ON sewa(id_kamar);

-- 1c. tanggal_akhir -- dipakai di HAMPIR SEMUA query ke tabel sewa
CREATE INDEX IF NOT EXISTS idx_sewa_tanggal_akhir ON sewa(tanggal_akhir);

-- 1d. Composite index: pola paling umum "1 penyewa + masih aktif"
CREATE INDEX IF NOT EXISTS idx_sewa_penyewa_tglakhir ON sewa(id_penyewa, tanggal_akhir);

-- 1e. Composite index: pola "1 kamar + masih aktif"
CREATE INDEX IF NOT EXISTS idx_sewa_kamar_tglakhir ON sewa(id_kamar, tanggal_akhir);

-- 2a. FK id_sewa di tabel pembayaran (JOIN ke laporan pendapatan/OLAP)
CREATE INDEX IF NOT EXISTS idx_pembayaran_id_sewa ON pembayaran(id_sewa);

-- 3a. FK id_pembayaran di tabel periode_pembayaran
CREATE INDEX IF NOT EXISTS idx_periode_id_pembayaran ON periode_pembayaran(id_pembayaran);

-- 4a. FK id_penyewa di tabel request_maintenance
CREATE INDEX IF NOT EXISTS idx_reqmaint_id_penyewa ON request_maintenance(id_penyewa);

ANALYZE sewa;
ANALYZE pembayaran;
ANALYZE periode_pembayaran;
ANALYZE request_maintenance;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_penyewa = 1 AND tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_kamar = 1 AND tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pembayaran WHERE id_sewa = 1;


SELECT tablename AS "Tabel", indexname AS "Nama Index", indexdef AS "Definisi"
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'sewa';

