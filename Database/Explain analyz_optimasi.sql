-- =====================================================================
-- 05. OPTIMAL INDEXING + EXPLAIN ANALYZE (Sebelum vs Sesudah)
-- Proyek: Hidden Kost
--
-- CARA PAKAI FILE INI (jalankan berurutan dari atas ke bawah):
--   STEP A -> jalankan blok "SEBELUM INDEX" dulu (drop index tambahan
--             kalau sudah pernah dibuat, lalu EXPLAIN ANALYZE)
--   STEP B -> jalankan blok CREATE INDEX
--   STEP C -> jalankan blok "SESUDAH INDEX" (EXPLAIN ANALYZE lagi,
--             query SAMA persis) lalu bandingkan Execution Time & Scan
--             Method dengan hasil STEP A
-- =====================================================================


-- =====================================================================
-- KENAPA INDEX INI DIPILIH? (analisis pola akses dari file 04_oltp)
-- =====================================================================
-- Tabel "sewa" adalah tabel paling sering di-WHERE/JOIN:
--   - WHERE id_penyewa = X            (OLTP-2: dashboard penyewa)
--   - WHERE id_kamar = X               (OLTP-3: cek status kamar)
--   - WHERE tanggal_akhir >= CURRENT_DATE   (HAMPIR SEMUA query di atas)
-- Tanpa index, PostgreSQL WAJIB Seq Scan = baca SEMUA baris tabel sewa
-- satu per satu untuk menemukan baris yang cocok. Index B-Tree membuat
-- planner bisa lompat langsung ke baris yang relevan (mirip cari kata
-- di kamus pakai daftar abjad, bukan baca dari halaman 1).
--
-- AKIBAT JIKA INDEX INI DIHAPUS / TIDAK DIBUAT:
--   - Dashboard penyewa, sinkronisasi status kamar, dan laporan
--     pembayaran tetap BENAR secara hasil, tapi waktu eksekusi naik
--     linear seiring jumlah baris tabel "sewa" bertambah (saat ini
--     600 baris -> belum terasa; di 100rb+ baris akan sangat lambat).
--   - Planner terpaksa pilih Seq Scan / Hash Join, bukan Index Scan /
--     Nested Loop -> cost query jauh lebih tinggi.
-- =====================================================================


-- ---------------------------------------------------------------------
-- STEP A — BASELINE: EXPLAIN ANALYZE SEBELUM index tambahan dibuat
-- (Pastikan index berikut BELUM ada -- kalau sudah pernah dibuat,
--  drop dulu supaya hasil baseline valid)
-- ---------------------------------------------------------------------
DROP INDEX IF EXISTS idx_sewa_id_penyewa;
DROP INDEX IF EXISTS idx_sewa_id_kamar;
DROP INDEX IF EXISTS idx_sewa_tanggal_akhir;
DROP INDEX IF EXISTS idx_sewa_penyewa_tglakhir;
DROP INDEX IF EXISTS idx_sewa_kamar_tglakhir;
DROP INDEX IF EXISTS idx_pembayaran_id_sewa;
DROP INDEX IF EXISTS idx_periode_id_pembayaran;
DROP INDEX IF EXISTS idx_reqmaint_id_penyewa;

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

-- >> CATAT hasil "Execution Time" dan "Seq Scan" / "Index Scan" dari
--    keempat query di atas sebelum lanjut ke STEP B.


-- ---------------------------------------------------------------------
-- STEP B — PEMBUATAN INDEX OPTIMAL
-- ---------------------------------------------------------------------

-- 1a. FK id_penyewa di tabel sewa
--     Query: WHERE id_penyewa = X  (dashboard penyewa, OLTP-2)
CREATE INDEX IF NOT EXISTS idx_sewa_id_penyewa ON sewa(id_penyewa);

-- 1b. FK id_kamar di tabel sewa
--     Query: WHERE id_kamar = X  (cek status kamar, OLTP-3, sinkronisasi)
CREATE INDEX IF NOT EXISTS idx_sewa_id_kamar ON sewa(id_kamar);

-- 1c. tanggal_akhir -- dipakai di HAMPIR SEMUA query ke tabel sewa
CREATE INDEX IF NOT EXISTS idx_sewa_tanggal_akhir ON sewa(tanggal_akhir);

-- 1d. Composite index: pola paling umum "1 penyewa + masih aktif"
--     Bisa memicu Index Only Scan kalau kolom yg di-SELECT ter-cover.
CREATE INDEX IF NOT EXISTS idx_sewa_penyewa_tglakhir ON sewa(id_penyewa, tanggal_akhir);

-- 1e. Composite index: pola "1 kamar + masih aktif"
CREATE INDEX IF NOT EXISTS idx_sewa_kamar_tglakhir ON sewa(id_kamar, tanggal_akhir);

-- 2a. FK id_sewa di tabel pembayaran (JOIN ke laporan pendapatan/OLAP-1,2)
CREATE INDEX IF NOT EXISTS idx_pembayaran_id_sewa ON pembayaran(id_sewa);

-- 3a. FK id_pembayaran di tabel periode_pembayaran
CREATE INDEX IF NOT EXISTS idx_periode_id_pembayaran ON periode_pembayaran(id_pembayaran);

-- 4a. FK id_penyewa di tabel request_maintenance
CREATE INDEX IF NOT EXISTS idx_reqmaint_id_penyewa ON request_maintenance(id_penyewa);

-- WAJIB: ANALYZE supaya planner PostgreSQL update statistik tabel,
-- kalau tidak, planner bisa saja TETAP pilih Seq Scan walau index ada
-- (karena masih pakai statistik lama / row-count estimate yang salah).
ANALYZE sewa;
ANALYZE pembayaran;
ANALYZE periode_pembayaran;
ANALYZE request_maintenance;


-- ---------------------------------------------------------------------
-- STEP C — EXPLAIN ANALYZE SESUDAH index dibuat (query IDENTIK dgn STEP A)
-- ---------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_penyewa = 1 AND tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE id_kamar = 1 AND tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sewa WHERE tanggal_akhir >= CURRENT_DATE;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pembayaran WHERE id_sewa = 1;

-- >> Bandingkan "Execution Time" STEP A vs STEP C. Yang harus berubah:
--      Seq Scan on sewa            -->  Index Scan using idx_sewa_...
--    Kalau dengan data hanya 600 baris planner TETAP pilih Seq Scan,
--    itu NORMAL -- PostgreSQL kadang menilai Seq Scan lebih murah untuk
--    tabel kecil. Untuk membuktikan index BEKERJA pada data sekecil ini,
--    paksa planner mengabaikan Seq Scan dengan:
--        SET enable_seqscan = off;
--        EXPLAIN ANALYZE SELECT * FROM sewa WHERE id_penyewa = 1;
--        SET enable_seqscan = on;   -- jangan lupa nyalakan lagi


-- ---------------------------------------------------------------------
-- VERIFIKASI: lihat semua index yang sekarang ada di schema public
-- ---------------------------------------------------------------------
SELECT tablename AS "Tabel", indexname AS "Nama Index", indexdef AS "Definisi"
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
