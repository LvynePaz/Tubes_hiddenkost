-- =====================================================================
-- OPTIMAL INDEX SCAN — Rekomendasi Index Berdasarkan Query Pattern
-- ABD Kelompok 2 — Hidden Kost
-- =====================================================================
--
-- INDEX YANG SUDAH ADA (dari DDL):
--   index_nama_penyewa    → profil_penyewa(nama_lengkap)
--   index_nomor_kamar     → kamar(nomor)
--   index_status_penyewa  → profil_penyewa(status)      ← low selectivity
--   index_status_kamar    → kamar(status)                ← low selectivity
--
-- INDEX BARU YANG DIREKOMENDASIKAN:
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- PRIORITAS 1: TABEL SEWA (tabel paling sering di-JOIN & di-filter)
-- ─────────────────────────────────────────────────────────────────────

-- 1a. Index pada FK id_penyewa
--     Dipakai di: Dashboard Penyewa (sewa aktif saya), LATERAL subquery
--     data kamar, riwayat pembayaran per penyewa
--     Query: WHERE s.id_penyewa = %s AND s.tanggal_akhir >= CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_sewa_id_penyewa ON sewa(id_penyewa);

-- 1b. Index pada FK id_kamar
--     Dipakai di: LATERAL subquery data kamar, sinkronisasi status kamar,
--     EXISTS subquery di UPDATE kamar
--     Query: WHERE s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_sewa_id_kamar ON sewa(id_kamar);

-- 1c. Index pada tanggal_akhir
--     Hampir SEMUA query ke tabel sewa filter: s.tanggal_akhir >= CURRENT_DATE
--     Tanpa index ini, PostgreSQL harus Seq Scan seluruh tabel sewa
--     untuk menemukan sewa yang masih aktif.
CREATE INDEX IF NOT EXISTS idx_sewa_tanggal_akhir ON sewa(tanggal_akhir);

-- 1d. BONUS: Composite index untuk query pattern paling umum
--     Covers: WHERE s.id_penyewa = X AND s.tanggal_akhir >= CURRENT_DATE
--     PostgreSQL bisa pakai Index Only Scan jika kolom yang di-SELECT
--     sudah ter-cover di index.
CREATE INDEX IF NOT EXISTS idx_sewa_penyewa_tglakhir ON sewa(id_penyewa, tanggal_akhir);

-- 1e. Composite index untuk kamar + tanggal
--     Covers: WHERE s.id_kamar = X AND s.tanggal_akhir >= CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_sewa_kamar_tglakhir ON sewa(id_kamar, tanggal_akhir);


-- ─────────────────────────────────────────────────────────────────────
-- PRIORITAS 2: TABEL PEMBAYARAN (JOIN ke sewa di hampir semua laporan)
-- ─────────────────────────────────────────────────────────────────────

-- 2a. Index pada FK id_sewa
--     Dipakai di: Tab Pendapatan, Tab Pembayaran, Riwayat Pembayaran Penyewa
--     Query: JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
CREATE INDEX IF NOT EXISTS idx_pembayaran_id_sewa ON pembayaran(id_sewa);


-- ─────────────────────────────────────────────────────────────────────
-- PRIORITAS 3: TABEL PERIODE_PEMBAYARAN (JOIN ke pembayaran)
-- ─────────────────────────────────────────────────────────────────────

-- 3a. Index pada FK id_pembayaran
--     Dipakai di: Tab Pembayaran, Riwayat Pembayaran, hitung jumlah_bulan_bayar
--     Query: JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
CREATE INDEX IF NOT EXISTS idx_periode_id_pembayaran ON periode_pembayaran(id_pembayaran);


-- ─────────────────────────────────────────────────────────────────────
-- PRIORITAS 4: TABEL REQUEST_MAINTENANCE
-- ─────────────────────────────────────────────────────────────────────

-- 4a. Index pada FK id_penyewa
--     Dipakai di: Maintenance per penyewa (penyewa view)
--     Query: WHERE rm.id_penyewa = %s
CREATE INDEX IF NOT EXISTS idx_reqmaint_id_penyewa ON request_maintenance(id_penyewa);


-- =====================================================================
-- JALANKAN ANALYZE SETELAH MEMBUAT INDEX
-- (supaya PostgreSQL planner tahu statistik terbaru)
-- =====================================================================
ANALYZE sewa;
ANALYZE pembayaran;
ANALYZE periode_pembayaran;
ANALYZE request_maintenance;


-- =====================================================================
-- VERIFIKASI: CEK SEMUA INDEX YANG ADA
-- =====================================================================
SELECT
    tablename  AS "Tabel",
    indexname  AS "Nama Index",
    indexdef   AS "Definisi"
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;


-- =====================================================================
-- TEST: EXPLAIN ANALYZE — Buktikan index dipakai
-- =====================================================================

-- Test 1: Cari sewa per penyewa (harus Index Scan pada idx_sewa_id_penyewa)
EXPLAIN ANALYZE
SELECT * FROM sewa WHERE id_penyewa = 1;

-- Test 2: Cari sewa per kamar (harus Index Scan pada idx_sewa_id_kamar)
EXPLAIN ANALYZE
SELECT * FROM sewa WHERE id_kamar = 1;

-- Test 3: Cari sewa aktif (harus Index Scan pada idx_sewa_tanggal_akhir)
EXPLAIN ANALYZE
SELECT * FROM sewa WHERE tanggal_akhir >= CURRENT_DATE;

-- Test 4: Cari pembayaran per sewa (harus Index Scan pada idx_pembayaran_id_sewa)
EXPLAIN ANALYZE
SELECT * FROM pembayaran WHERE id_sewa = 1;

-- Test 5: Cari periode per pembayaran (harus Index Scan pada idx_periode_id_pembayaran)
EXPLAIN ANALYZE
SELECT * FROM periode_pembayaran WHERE id_pembayaran = 1;

-- Test 6: Cari maintenance per penyewa (harus Index Scan pada idx_reqmaint_id_penyewa)
EXPLAIN ANALYZE
SELECT * FROM request_maintenance WHERE id_penyewa = 1;

-- Test 7: Composite index — sewa per penyewa yang masih aktif
EXPLAIN ANALYZE
SELECT * FROM sewa WHERE id_penyewa = 1 AND tanggal_akhir >= CURRENT_DATE;
