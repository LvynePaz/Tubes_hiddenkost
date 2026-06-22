# OLTP — query baca/tulis baris spesifik

OLTP_DATA_KAMAR_PEMILIK = """
    SELECT k.nomor AS "Nomor", ko.nama_kos AS "Kos", k.lantai AS "Lantai",
           k.luas AS "Luas (m²)", tk.kategori AS "Tipe", tk.harga_sewa AS "Harga (Rp)",
           k.status::TEXT AS "Status",
           COALESCE(pp.id_penyewa::TEXT, '-') AS "ID Penyewa",
           COALESCE(pp.nama_lengkap, '-') AS "Penyewa",
           COALESCE(pp.pekerjaan, '-') AS "Pekerjaan",
           COALESCE(TO_CHAR(s_aktif.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Sewa Mulai",
           COALESCE(TO_CHAR(s_aktif.tanggal_akhir, 'DD-MM-YYYY'), '-') AS "Sewa Akhir"
    FROM kamar k
    JOIN kos ko ON k.id_kos = ko.id_kos
    JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
    LEFT JOIN LATERAL (
        SELECT s.id_penyewa, s.tanggal_mulai, s.tanggal_akhir FROM sewa s
        WHERE s.id_kamar = k.id_kamar AND s.tanggal_akhir >= CURRENT_DATE
        ORDER BY s.tanggal_mulai DESC LIMIT 1
    ) s_aktif ON TRUE
    LEFT JOIN profil_penyewa pp ON s_aktif.id_penyewa = pp.id_penyewa
    ORDER BY ko.nama_kos, k.nomor
"""

OLTP_RIWAYAT_PEMBAYARAN_PEMILIK = """
    SELECT pp_penyewa.nama_lengkap AS "Penyewa", k.nomor AS "Kamar",
           ko.nama_kos AS "Kos", pb.nominal AS "Nominal (Rp)",
           pb.metode_bayar::TEXT AS "Metode", per.periode_bayar AS "Periode",
           per.status::TEXT AS "Status Bayar"
    FROM pembayaran pb
    JOIN sewa s ON pb.id_sewa = s.id_sewa
    JOIN profil_penyewa pp_penyewa ON s.id_penyewa = pp_penyewa.id_penyewa
    JOIN kamar k ON s.id_kamar = k.id_kamar
    JOIN kos ko ON k.id_kos = ko.id_kos
    JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
    WHERE s.tanggal_akhir >= CURRENT_DATE
    ORDER BY per.periode_bayar DESC LIMIT 500
"""

OLTP_DATA_PENYEWA_AKTIF = """
    SELECT pp.nama_lengkap AS "Nama", pp.pekerjaan AS "Pekerjaan",
           pp.instansi AS "Instansi", pp.status::TEXT AS "Status",
           COALESCE(k.nomor, '-') AS "Kamar", COALESCE(ko.nama_kos, '-') AS "Kos",
           COALESCE(TO_CHAR(s.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Sewa Mulai",
           COALESCE(TO_CHAR(s.tanggal_akhir, 'DD-MM-YYYY'), '-') AS "Sewa Akhir"
    FROM profil_penyewa pp
    LEFT JOIN LATERAL (
        SELECT s.id_kamar, s.tanggal_mulai, s.tanggal_akhir FROM sewa s
        WHERE s.id_penyewa = pp.id_penyewa AND s.tanggal_akhir >= CURRENT_DATE
        ORDER BY s.tanggal_mulai DESC LIMIT 1
    ) s ON TRUE
    LEFT JOIN kamar k ON s.id_kamar = k.id_kamar
    LEFT JOIN kos ko ON k.id_kos = ko.id_kos
    WHERE pp.status = 'Aktif' ORDER BY pp.nama_lengkap
"""

OLTP_REKAP_MAINTENANCE = """
    SELECT rm.id_request_maintenance AS "ID", pp.nama_lengkap AS "Penyewa",
           rm.deskripsi AS "Keluhan",
           COALESCE(rv.status::TEXT, 'Belum ditangani') AS "Status",
           COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
           COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
    FROM request_maintenance rm
    JOIN profil_penyewa pp ON rm.id_penyewa = pp.id_penyewa
    LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
    ORDER BY CASE WHEN rv.status IS NULL THEN 0 WHEN rv.status='Tertunda' THEN 1
                  WHEN rv.status='Sedang dikerjakan' THEN 2 ELSE 3 END,
             rm.id_request_maintenance DESC
"""

OLTP_MAINTENANCE_PENDING = """
    SELECT rm.id_request_maintenance, rm.deskripsi, pp.nama_lengkap,
           COALESCE(rv.status::TEXT, 'Belum ditangani') AS status
    FROM request_maintenance rm
    JOIN profil_penyewa pp ON rm.id_penyewa = pp.id_penyewa
    LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
    WHERE rv.status IS NULL OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
    ORDER BY rm.id_request_maintenance DESC
"""

OLTP_CEK_RIWAYAT_MAINTENANCE_EXIST = (
    "SELECT id_riwayat_maintenance FROM riwayat_maintenance WHERE id_request_maintenance = %s"
)

OLTP_KAMAR_KOSONG_PENYEWA = """
    SELECT k.nomor AS "Nomor", ko.nama_kos AS "Kos", k.lantai AS "Lantai",
           tk.kategori AS "Tipe", tk.harga_sewa AS "Harga (Rp)",
           tk.deskripsi_fasilitas AS "Fasilitas"
    FROM kamar k JOIN kos ko ON k.id_kos = ko.id_kos
    JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
    WHERE k.status = 'Kosong' ORDER BY ko.nama_kos, k.nomor
"""

OLTP_SEWA_AKTIF_PENYEWA = """
    SELECT s.id_sewa, k.nomor AS "Kamar", ko.nama_kos AS "Kos",
           tk.kategori AS "Tipe", tk.harga_sewa AS harga,
           s.tanggal_mulai AS "Mulai", s.tanggal_akhir AS "Akhir",
           (s.tanggal_akhir - CURRENT_DATE) AS "Sisa Hari",
           COALESCE(bayar.jumlah_bulan_bayar, 0) AS jumlah_bulan_bayar,
           (s.tanggal_mulai + (COALESCE(bayar.jumlah_bulan_bayar, 0) * INTERVAL '1 month'))::date AS jatuh_tempo
    FROM sewa s
    JOIN kamar k ON s.id_kamar = k.id_kamar
    JOIN kos ko ON k.id_kos = ko.id_kos
    JOIN tipe_kamar tk ON k.id_tipe_kamar = tk.id_tipe_kamar
    LEFT JOIN LATERAL (
        SELECT COUNT(*) AS jumlah_bulan_bayar FROM pembayaran pb
        JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
        WHERE pb.id_sewa = s.id_sewa AND per.status = 'Berhasil'
    ) bayar ON TRUE
    WHERE s.id_penyewa = %s AND s.tanggal_akhir >= CURRENT_DATE
    ORDER BY s.tanggal_mulai DESC
"""

OLTP_RIWAYAT_BAYAR_PENYEWA = """
    SELECT k.nomor AS "Kamar", pb.nominal AS "Nominal (Rp)",
           pb.metode_bayar::TEXT AS "Metode", per.periode_bayar AS "Periode",
           per.status::TEXT AS "Status"
    FROM sewa s JOIN kamar k ON s.id_kamar = k.id_kamar
    JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
    JOIN periode_pembayaran per ON pb.id_pembayaran = per.id_pembayaran
    WHERE s.id_penyewa = %s AND s.tanggal_akhir >= CURRENT_DATE
    ORDER BY per.periode_bayar DESC
"""

OLTP_INSERT_PEMBAYARAN = "INSERT INTO pembayaran (nominal, metode_bayar, id_sewa) VALUES (%s, %s, %s)"
OLTP_GET_LAST_ID_PEMBAYARAN = "SELECT MAX(id_pembayaran) AS id FROM pembayaran"
OLTP_INSERT_PERIODE_PEMBAYARAN = "INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran) VALUES (%s, %s, %s)"

OLTP_MAINT_PENYEWA = """
    SELECT rm.deskripsi AS "Keluhan", COALESCE(rv.status::TEXT, 'Menunggu') AS "Status",
           COALESCE(TO_CHAR(rv.tanggal_mulai, 'DD-MM-YYYY'), '-') AS "Mulai Dikerjakan",
           COALESCE(TO_CHAR(rv.tanggal_selesai, 'DD-MM-YYYY'), '-') AS "Selesai"
    FROM request_maintenance rm
    LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
    WHERE rm.id_penyewa = %s ORDER BY rv.status NULLS FIRST
"""

OLTP_INSERT_MAINTENANCE = "INSERT INTO request_maintenance (deskripsi, id_penyewa) VALUES (%s, %s)"

OLTP_DAFTAR_PENYEWA_AKTIF_LOGIN = """
    SELECT id_penyewa, nama_lengkap FROM profil_penyewa
    WHERE status = 'Aktif' ORDER BY id_penyewa LIMIT 20
"""

# OLAP — agregasi untuk laporan & KPI

OLAP_KPI_TOTAL_KAMAR = "SELECT COUNT(*) AS n FROM kamar"
OLAP_KPI_KAMAR_KOSONG = "SELECT COUNT(*) AS n FROM kamar WHERE status = 'Kosong'"
OLAP_KPI_KAMAR_TERISI = "SELECT COUNT(*) AS n FROM kamar WHERE status = 'Sedang disewa'"
OLAP_KPI_TOTAL_PENDAPATAN = "SELECT COALESCE(SUM(nominal),0) AS n FROM pembayaran"
OLAP_KPI_MAINTENANCE_PENDING = """
    SELECT COUNT(*) AS n FROM request_maintenance rm
    LEFT JOIN riwayat_maintenance rv ON rm.id_request_maintenance = rv.id_request_maintenance
    WHERE rv.status IS NULL OR rv.status IN ('Tertunda', 'Sedang dikerjakan')
"""

OLAP_PENDAPATAN_PER_KOS = """
    SELECT ko.nama_kos AS "Nama Kos", COUNT(DISTINCT s.id_sewa) AS "Jumlah Sewa",
           SUM(pb.nominal) AS "Total Pendapatan", AVG(pb.nominal)::INT AS "Rata-rata"
    FROM kos ko JOIN kamar k ON ko.id_kos = k.id_kos
    JOIN sewa s ON k.id_kamar = s.id_kamar
    JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
    GROUP BY ko.nama_kos ORDER BY "Total Pendapatan" DESC
"""

OLAP_PENDAPATAN_PER_TIPE_KAMAR = """
    SELECT tk.kategori AS "Tipe", tk.harga_sewa AS "Harga Sewa",
           COUNT(DISTINCT s.id_sewa) AS "Jumlah Sewa", SUM(pb.nominal) AS "Total Pendapatan"
    FROM tipe_kamar tk JOIN kamar k ON tk.id_tipe_kamar = k.id_tipe_kamar
    JOIN sewa s ON k.id_kamar = s.id_kamar
    JOIN pembayaran pb ON s.id_sewa = pb.id_sewa
    GROUP BY tk.kategori, tk.harga_sewa ORDER BY "Total Pendapatan" DESC
"""

OLAP_RINGKASAN_METODE_BAYAR = """
    SELECT pb.metode_bayar::TEXT AS "Metode", COUNT(*) AS "Jumlah", SUM(pb.nominal) AS "Total"
    FROM pembayaran pb JOIN sewa s ON pb.id_sewa = s.id_sewa
    WHERE s.tanggal_akhir >= CURRENT_DATE
    GROUP BY pb.metode_bayar ORDER BY "Total" DESC
"""