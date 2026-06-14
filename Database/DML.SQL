INSERT INTO roles (nama_role)
VALUES
('admin'),
('penyewa');

INSERT INTO users(email, password, id_roles) VALUES
('admin1@hiddenkost.com', 'admin123', 1),
('admin2@hiddenkost.com', 'admin123', 1);

INSERT INTO users(email, password, id_roles)
SELECT
    'penyewa' || gs || '@gmail.com',
    'password123',
    2
FROM generate_series(1,998) gs;

INSERT INTO profil_penyewa
(nama_lengkap, pekerjaan, instansi, deskripsi_pekerjaan, status, url_ktp, id_user)
SELECT
    'Penyewa ke-' || gs,

    (
    ARRAY[
    'Mahasiswa',
    'Karyawan Swasta',
    'Pegawai BUMN',
    'Guru',
    'Siswa',
    'Wiraswasta'
    ]
    )[floor(random()*6+1)],

    (
    ARRAY[
    'Institut Teknologi Kalimantan',
    'Universitas Balikpapan',
    'Politeknik Negeri Balikpapan',
    'STT Migas',
    'PT PLN Nusa Daya',
    'PT Pertamina Hulu Mahakam',
    'PT Pamapersada Nusantara',
    'PT Kilang Pertamina Balikpapan'
    ]
    )[floor(random()*8+1)],

    (
    ARRAY[
    'Sistem Informasi',
    'Informatika',
    'Teknik Elektro',
    'Operator',
    'Staff Administrasi',
    'Supervisor',
    'Guru Matematika',
    'Marketing'
    ]
    ) [floor(random()*8+1)],

    CASE
        WHEN random() < 0.8
        THEN 'Aktif'
        ELSE 'Tidak aktif'
    END::status_penyewa,

    'ktp_' || gs || '.jpg',

    gs + 2
FROM generate_series(1,450) gs;

INSERT INTO kos(nama_kos, alamat) VALUES
('Hidden Kost Origin', 'Jl. Giri Rejo II No. 4B, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127'),
('Hidden Kost Lux', 'Jl. Giri Rejo II No. 42 RT.032, Karang Joang, Balikpapan Utara, Balikpapan, Kalimantan Timur 76127');

INSERT INTO tipe_kamar
(kategori, deskripsi_fasilitas, harga_sewa) VALUES
('Tipe A', 'Kasur, dipan, bantal guling, bantal kepala, sprei, AC, lemari, meja, kursi, gantungan baju, kamar mandi dalam', 1200000),
('Tipe B', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja, kursi, gantungan baju, kamar mandi dalam', 1000000),
('Tipe C', 'Kasur, dipan, bantal guling, bantal kepala, sprei, kipas angin, lemari, meja, kursi, gantungan baju',850000);

-- Kamar Hidden Kost Origin
INSERT INTO kamar
(nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'O-' || gs,
    12 + (random()*4)::int,
    CASE
        WHEN gs <= 4 THEN '1'
        ELSE '2'
    END,
    CASE
        WHEN random() < 0.7
        THEN 'Sedang disewa'
        ELSE 'Kosong'
    END::status_kamar,
    3,
    1
FROM generate_series(1,8) gs;

-- Kamar Hidden Kost Lux
INSERT INTO kamar
(nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'LA-' || gs,
    15 + (random()*3)::int,
    ((gs-1)/4 + 1)::text,
    CASE
        WHEN random() < 0.75
        THEN 'Sedang disewa'
        ELSE 'Kosong'
    END::status_kamar,
    1,
    2
FROM generate_series(1,8) gs;

INSERT INTO kamar (nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'LB-' || gs,
    14 + (random()*3)::int,
    ((gs-1)/4 + 1)::text,
    CASE
        WHEN random() < 0.75
        THEN 'Sedang disewa'
        ELSE 'Kosong'
    END::status_kamar,
    2,
    2
FROM generate_series(1,8) gs;

INSERT INTO kamar
(nomor, luas, lantai, status, id_tipe_kamar, id_kos)
SELECT
    'LC-' || gs,
    12 + (random()*2)::int,
    ((gs-1)/4 + 1)::text,
    CASE
        WHEN random() < 0.75
        THEN 'Sedang disewa'
        ELSE 'Kosong'
    END::status_kamar,
    3,
    2
FROM generate_series(1,8) gs;

INSERT INTO sewa (tanggal_mulai, tanggal_akhir, id_penyewa, id_kamar)
SELECT
    start_date,
    start_date +
    (
        ARRAY[
        30,
        90,
        180,
        365,
        730
        ]
        )[floor(random()*5+1)]
        * INTERVAL '1 day',

    (random()*449 + 1)::int,

    (random()*31 + 1)::int

FROM
(
    SELECT
        CURRENT_DATE -
        ((random()*1500)::int * INTERVAL '1 day')
        AS start_date
    FROM generate_series(1,600)
) t;

INSERT INTO pembayaran (nominal, metode_bayar, id_sewa)
SELECT
    CASE
        WHEN random() < 0.33 THEN 850000
        WHEN random() < 0.66 THEN 1000000
        ELSE 1200000
    END,

    CASE
        WHEN random() < 0.5
        THEN 'Transfer'
        ELSE 'Tunai'
    END::metode_pembayaran,

    id_sewa
FROM sewa;

INSERT INTO periode_pembayaran (periode_bayar, status, id_pembayaran)
SELECT
    TO_CHAR(
        CURRENT_DATE -
        ((random()*365)::int),
        'YYYY-MM'
    ),

    CASE
        WHEN random() < 0.9
        THEN 'Berhasil'
        ELSE 'Gagal'
    END::status_pembayaran,

    id_pembayaran
FROM pembayaran;

INSERT INTO request_maintenance (deskripsi, id_penyewa)
SELECT
(
ARRAY[
'Lampu kamar mati',
'AC tidak dingin',
'Kipas rusak',
'Kunci pintu rusak',
'Keran bocor',
'WC mampet',
'Stop kontak bermasalah',
'Jaringan internet lambat'
]
)[floor(random()*8+1)],

id_penyewa

FROM profil_penyewa
WHERE random() < 0.4;

INSERT INTO riwayat_maintenance (tanggal_mulai, tanggal_selesai, status, id_request_maintenance)
SELECT
CURRENT_DATE - ((random()*90)::int),

CURRENT_DATE - ((random()*30)::int),

(
ARRAY[
'Tertunda',
'Sedang dikerjakan',
'Selesai'
]
)[floor(random()*3+1)]::status_maintenance,

id_request_maintenance

FROM request_maintenance;