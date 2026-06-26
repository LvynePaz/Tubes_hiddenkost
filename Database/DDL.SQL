
CREATE TYPE status_penyewa AS ENUM ('Aktif', 'Tidak aktif');
CREATE TYPE status_kamar AS ENUM ('Sedang disewa', 'Kosong');
CREATE TYPE status_maintenance AS ENUM ('Tertunda', 'Sedang dikerjakan', 'Selesai');
CREATE TYPE metode_pembayaran AS ENUM ('Tunai', 'Transfer');
CREATE TYPE status_pembayaran AS ENUM ('Gagal', 'Berhasil');


CREATE TABLE IF NOT EXISTS roles (
    id_roles SERIAL PRIMARY KEY,
    nama_role VARCHAR(25) NOT NULL UNIQUE
);


CREATE TABLE IF NOT EXISTS users (
    id_user SERIAL PRIMARY KEY,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    id_roles INT NOT NULL,

    FOREIGN KEY (id_roles) REFERENCES roles(id_roles)
);


CREATE TABLE IF NOT EXISTS profil_penyewa (
    id_penyewa SERIAL PRIMARY KEY,
    nama_lengkap VARCHAR(100) NOT NULL,
    pekerjaan VARCHAR(50) NOT NULL,
    instansi VARCHAR(50) NOT NULL,
    deskripsi_pekerjaan VARCHAR(100) NOT NULL,
    status status_penyewa NOT NULL DEFAULT 'Tidak aktif',
    url_ktp VARCHAR(255) NOT NULL,
    id_user INT NOT NULL UNIQUE,

    FOREIGN KEY (id_user) REFERENCES users(id_user)
);


CREATE TABLE IF NOT EXISTS kos (
    id_kos SERIAL PRIMARY KEY,
    nama_kos VARCHAR(50) NOT NULL UNIQUE,
    alamat TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tipe_kamar (
    id_tipe_kamar SERIAL PRIMARY KEY,
    kategori VARCHAR(50) NOT NULL UNIQUE,
    deskripsi_fasilitas VARCHAR(255) NOT NULL,
    harga_sewa INT NOT NULL
);

CREATE TABLE IF NOT EXISTS kamar (
    id_kamar SERIAL PRIMARY KEY,
    nomor VARCHAR(8) NOT NULL,
    luas INT NOT NULL,
    lantai VARCHAR(2) NOT NULL,
    status status_kamar NOT NULL DEFAULT 'Kosong',
    id_tipe_kamar INT NOT NULL,
    id_kos INT NOT NULL,

    FOREIGN KEY (id_tipe_kamar) REFERENCES tipe_kamar(id_tipe_kamar),
    FOREIGN KEY (id_kos) REFERENCES kos(id_kos)
);


CREATE TABLE IF NOT EXISTS sewa (
    id_sewa SERIAL PRIMARY KEY,
    tanggal_mulai DATE NOT NULL,
    tanggal_akhir DATE NOT NULL,
    id_penyewa INT NOT NULL,
    id_kamar INT NOT NULL,

    FOREIGN KEY (id_penyewa) REFERENCES profil_penyewa(id_penyewa),
    FOREIGN KEY (id_kamar) REFERENCES kamar (id_kamar)
);


CREATE TABLE IF NOT EXISTS pembayaran (
    id_pembayaran SERIAL PRIMARY KEY,
    nominal INT NOT NULL,
    metode_bayar metode_pembayaran NOT NULL,
    id_sewa INT NOT NULL,

    FOREIGN KEY (id_sewa) REFERENCES sewa(id_sewa)
);

CREATE TABLE IF NOT EXISTS periode_pembayaran (
    id_periode SERIAL PRIMARY KEY,
    periode_bayar VARCHAR(10) NOT NULL,
    status status_pembayaran NOT NULL,
    id_pembayaran INT NOT NULL,

    FOREIGN KEY (id_pembayaran) REFERENCES pembayaran(id_pembayaran)
);

CREATE TABLE IF NOT EXISTS request_maintenance (
    id_request_maintenance SERIAL PRIMARY KEY,
    deskripsi VARCHAR(255) NOT NULL,
    id_penyewa INT NOT NULL,

    FOREIGN KEY (id_penyewa) REFERENCES profil_penyewa(id_penyewa)
);

CREATE TABLE IF NOT EXISTS riwayat_maintenance (
    id_riwayat_maintenance SERIAL PRIMARY KEY,
    tanggal_mulai DATE,
    tanggal_selesai DATE,
    status status_maintenance NOT NULL DEFAULT 'Tertunda',
    id_request_maintenance INT NOT NULL UNIQUE,

    FOREIGN KEY (id_request_maintenance) REFERENCES request_maintenance(id_request_maintenance)
);

CREATE INDEX index_nama_penyewa  ON profil_penyewa (nama_lengkap);
CREATE INDEX index_nomor_kamar   ON kamar (nomor);