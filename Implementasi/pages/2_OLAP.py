import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from db import run_query

st.set_page_config(page_title="OLAP – Hidden Kost", layout="wide")

st.title("📊 OLAP – Analisis & Laporan")
st.caption("Agregasi data untuk pengambilan keputusan: pendapatan, okupansi, dan tren pembayaran.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Pendapatan per Kos",
    "🏨 Okupansi Kamar",
    "📅 Tren Pembayaran",
    "🔧 Rekap Maintenance",
])


# ── TAB 1: Pendapatan per Kos ─────────────────────────────────────────────────
with tab1:
    st.subheader("Total Pendapatan per Kos")

    sql = """
        SELECT
            ko.nama_kos                       AS nama_kos,
            COUNT(DISTINCT s.id_sewa)         AS jumlah_sewa,
            SUM(pb.nominal)                   AS total_pendapatan,
            AVG(pb.nominal)::INT              AS rata_rata_pembayaran
        FROM kos ko
        JOIN kamar      k  ON ko.id_kos  = k.id_kos
        JOIN sewa       s  ON k.id_kamar = s.id_kamar
        JOIN pembayaran pb ON s.id_sewa  = pb.id_sewa
        GROUP BY ko.nama_kos
        ORDER BY total_pendapatan DESC
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        total = df["total_pendapatan"].sum()
        col1.metric("Total Pendapatan Semua Kos", f"Rp {total:,.0f}")
        col2.metric("Kos Terlaris", df.iloc[0]["nama_kos"])
        col3.metric("Jumlah Sewa Terbanyak", f'{df["jumlah_sewa"].max():,} transaksi')

        st.divider()

        col_chart, col_tabel = st.columns([3, 2])

        with col_chart:
            fig = px.bar(
                df,
                x="nama_kos",
                y="total_pendapatan",
                color="nama_kos",
                text_auto=True,
                title="Total Pendapatan per Kos (Rp)",
                labels={"nama_kos": "Nama Kos", "total_pendapatan": "Total Pendapatan (Rp)"},
                color_discrete_sequence=["#2563eb", "#16a34a"],
            )
            fig.update_traces(texttemplate="Rp %{y:,.0f}", textposition="outside")
            fig.update_layout(showlegend=False, yaxis_tickformat=",")
            st.plotly_chart(fig, use_container_width=True)

        with col_tabel:
            df_tampil = df.copy()
            df_tampil["total_pendapatan"]      = df_tampil["total_pendapatan"].apply(lambda x: f"Rp {x:,}")
            df_tampil["rata_rata_pembayaran"]  = df_tampil["rata_rata_pembayaran"].apply(lambda x: f"Rp {x:,}")
            df_tampil.columns = ["Nama Kos", "Jumlah Sewa", "Total Pendapatan", "Rata-rata Pembayaran"]
            st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Pendapatan per tipe kamar
    st.subheader("Pendapatan per Tipe Kamar")
    sql2 = """
        SELECT
            tk.kategori                   AS tipe,
            COUNT(pb.id_pembayaran)       AS jumlah_transaksi,
            SUM(pb.nominal)               AS total_pendapatan
        FROM tipe_kamar tk
        JOIN kamar      k  ON tk.id_tipe_kamar = k.id_tipe_kamar
        JOIN sewa       s  ON k.id_kamar        = s.id_kamar
        JOIN pembayaran pb ON s.id_sewa          = pb.id_sewa
        GROUP BY tk.kategori
        ORDER BY total_pendapatan DESC
    """
    rows2 = run_query(sql2)
    df2   = pd.DataFrame(rows2)

    if not df2.empty:
        fig2 = px.pie(
            df2,
            names="tipe",
            values="total_pendapatan",
            title="Proporsi Pendapatan per Tipe Kamar",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── TAB 2: Okupansi Kamar ─────────────────────────────────────────────────────
with tab2:
    st.subheader("Tingkat Okupansi Kamar per Kos")

    sql = """
        SELECT
            ko.nama_kos                                          AS nama_kos,
            COUNT(k.id_kamar)                                    AS total_kamar,
            SUM(CASE WHEN k.status = 'Sedang disewa' THEN 1 ELSE 0 END) AS terisi,
            SUM(CASE WHEN k.status = 'Kosong'        THEN 1 ELSE 0 END) AS kosong,
            ROUND(
                SUM(CASE WHEN k.status = 'Sedang disewa' THEN 1 ELSE 0 END)::NUMERIC
                / COUNT(k.id_kamar) * 100, 1
            ) AS persen_terisi
        FROM kos ko
        JOIN kamar k ON ko.id_kos = k.id_kos
        GROUP BY ko.nama_kos
        ORDER BY persen_terisi DESC
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if not df.empty:
        for _, row in df.iterrows():
            st.markdown(f"**{row['nama_kos']}**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Kamar",  row["total_kamar"])
            col2.metric("Terisi",       row["terisi"])
            col3.metric("Kosong",       row["kosong"])
            st.progress(int(row["persen_terisi"]) / 100,
                        text=f"Okupansi: {row['persen_terisi']}%")
            st.divider()

        # Grouped bar
        df_melt = df.melt(
            id_vars="nama_kos",
            value_vars=["terisi", "kosong"],
            var_name="Status",
            value_name="Jumlah",
        )
        df_melt["Status"] = df_melt["Status"].map({"terisi": "Terisi", "kosong": "Kosong"})

        fig = px.bar(
            df_melt,
            x="nama_kos",
            y="Jumlah",
            color="Status",
            barmode="group",
            title="Perbandingan Kamar Terisi vs Kosong",
            color_discrete_map={"Terisi": "#2563eb", "Kosong": "#d1d5db"},
        )
        st.plotly_chart(fig, use_container_width=True)

    # Okupansi per tipe
    st.subheader("Okupansi per Tipe Kamar")
    sql2 = """
        SELECT
            tk.kategori   AS tipe,
            COUNT(*)      AS total,
            SUM(CASE WHEN k.status = 'Sedang disewa' THEN 1 ELSE 0 END) AS terisi,
            ROUND(
                SUM(CASE WHEN k.status = 'Sedang disewa' THEN 1 ELSE 0 END)::NUMERIC
                / COUNT(*) * 100, 1
            ) AS persen
        FROM tipe_kamar tk
        JOIN kamar k ON tk.id_tipe_kamar = k.id_tipe_kamar
        GROUP BY tk.kategori
        ORDER BY persen DESC
    """
    rows2 = run_query(sql2)
    df2   = pd.DataFrame(rows2)
    if not df2.empty:
        df2.columns = ["Tipe", "Total Kamar", "Terisi", "% Okupansi"]
        st.dataframe(df2, use_container_width=True, hide_index=True)


# ── TAB 3: Tren Pembayaran ────────────────────────────────────────────────────
with tab3:
    st.subheader("Tren Pembayaran Bulanan")

    sql = """
        SELECT
            TO_CHAR(pp.periode_bayar::DATE, 'YYYY-MM') AS bulan,
            COUNT(*)                                    AS jumlah_transaksi,
            SUM(pb.nominal)                             AS total_nominal,
            SUM(CASE WHEN pp.status = 'Berhasil' THEN 1 ELSE 0 END) AS berhasil,
            SUM(CASE WHEN pp.status = 'Gagal'    THEN 1 ELSE 0 END) AS gagal
        FROM periode_pembayaran pp
        JOIN pembayaran pb ON pp.id_pembayaran = pb.id_pembayaran
        GROUP BY bulan
        ORDER BY bulan
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Transaksi", f'{df["jumlah_transaksi"].sum():,}')
        col2.metric("Total Berhasil",  f'{df["berhasil"].sum():,}')
        col3.metric("Total Gagal",     f'{df["gagal"].sum():,}')

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["bulan"], y=df["berhasil"],
            name="Berhasil", mode="lines+markers",
            line=dict(color="#16a34a", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=df["bulan"], y=df["gagal"],
            name="Gagal", mode="lines+markers",
            line=dict(color="#dc2626", width=2, dash="dash"),
        ))
        fig.update_layout(
            title="Tren Transaksi Berhasil vs Gagal per Bulan",
            xaxis_title="Bulan",
            yaxis_title="Jumlah Transaksi",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Per metode bayar
    st.subheader("Perbandingan Metode Pembayaran")
    sql2 = """
        SELECT
            metode_bayar              AS metode,
            COUNT(*)                  AS jumlah,
            SUM(nominal)              AS total_nominal
        FROM pembayaran
        GROUP BY metode_bayar
        ORDER BY total_nominal DESC
    """
    rows2 = run_query(sql2)
    df2   = pd.DataFrame(rows2)
    if not df2.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            fig2 = px.pie(
                df2, names="metode", values="jumlah",
                title="Proporsi Jumlah Transaksi",
                color_discrete_sequence=["#2563eb", "#f59e0b"],
            )
            st.plotly_chart(fig2, use_container_width=True)
        with col_b:
            df2["total_nominal"] = df2["total_nominal"].apply(lambda x: f"Rp {x:,}")
            df2.columns = ["Metode", "Jumlah Transaksi", "Total Nominal"]
            st.dataframe(df2, use_container_width=True, hide_index=True)


# ── TAB 4: Rekap Maintenance ──────────────────────────────────────────────────
with tab4:
    st.subheader("Rekap Status Maintenance")

    sql = """
        SELECT
            COALESCE(rv.status, 'Belum ada riwayat') AS status,
            COUNT(*)                                   AS jumlah
        FROM request_maintenance rm
        LEFT JOIN riwayat_maintenance rv
               ON rm.id_request_maintenance = rv.id_request_maintenance
        GROUP BY rv.status
        ORDER BY jumlah DESC
    """
    rows = run_query(sql)
    df   = pd.DataFrame(rows)

    if not df.empty:
        warna = {
            "Selesai":           "#16a34a",
            "Sedang dikerjakan": "#f59e0b",
            "Tertunda":          "#dc2626",
            "Belum ada riwayat": "#6b7280",
        }
        fig = px.bar(
            df,
            x="status",
            y="jumlah",
            color="status",
            title="Jumlah Request Maintenance per Status",
            color_discrete_map=warna,
            labels={"status": "Status", "jumlah": "Jumlah"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        df.columns = ["Status", "Jumlah"]
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Keluhan terbanyak
    st.subheader("Keluhan Terbanyak")
    sql2 = """
        SELECT
            deskripsi      AS keluhan,
            COUNT(*)       AS jumlah
        FROM request_maintenance
        GROUP BY deskripsi
        ORDER BY jumlah DESC
    """
    rows2 = run_query(sql2)
    df2   = pd.DataFrame(rows2)
    if not df2.empty:
        fig2 = px.bar(
            df2,
            x="jumlah",
            y="keluhan",
            orientation="h",
            title="Frekuensi Keluhan Maintenance",
            color="jumlah",
            color_continuous_scale="Blues",
            labels={"keluhan": "Keluhan", "jumlah": "Jumlah"},
        )
        fig2.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2, use_container_width=True)
