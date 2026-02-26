import streamlit as st
import simpy
import random
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
import plotly.express as px
import plotly.graph_objects as go

# ======================================================
# KONFIGURASI SIMULASI
# ======================================================
@dataclass
class Config:
    NUM_MAHASISWA: int = 500
    NUM_KELOMPOK: int = 2
    NUM_STAFF_PER_KELOMPOK: int = 2

    MIN_SERVICE_TIME: float = 1.0
    MAX_SERVICE_TIME: float = 3.0

    START_HOUR: int = 8
    START_MINUTE: int = 0

    RANDOM_SEED: int = 42


# ======================================================
# MODEL DISCRETE EVENT SYSTEM
# ======================================================
class KantinDES:
    def __init__(self, config: Config):
        self.config = config
        self.env = simpy.Environment()

        random.seed(config.RANDOM_SEED)
        np.random.seed(config.RANDOM_SEED)

        self.start_time = datetime(2024, 1, 1, config.START_HOUR, config.START_MINUTE)

        self.staff = [
            simpy.Resource(self.env, capacity=config.NUM_STAFF_PER_KELOMPOK)
            for _ in range(config.NUM_KELOMPOK)
        ]

        self.data = []

    def sim_time_to_clock(self, t):
        return self.start_time + timedelta(minutes=t)

    def service_time(self):
        return random.uniform(
            self.config.MIN_SERVICE_TIME,
            self.config.MAX_SERVICE_TIME
        )

    def interarrival_time(self):
        mean = 120 / self.config.NUM_MAHASISWA
        return random.expovariate(1 / mean)

    def mahasiswa(self, i):
        datang = self.env.now

        kelompok = min(
            range(self.config.NUM_KELOMPOK),
            key=lambda k: self.staff[k].count + len(self.staff[k].queue)
        )

        with self.staff[kelompok].request() as req:
            yield req

            mulai = self.env.now
            tunggu = mulai - datang

            layanan = self.service_time()
            yield self.env.timeout(layanan)

            selesai = self.env.now

            self.data.append({
                "id": i,
                "kelompok": kelompok + 1,
                "waktu_datang": datang,
                "waktu_mulai": mulai,
                "waktu_selesai": selesai,
                "waktu_tunggu": tunggu,
                "waktu_layanan": layanan,
                "jam_datang": self.sim_time_to_clock(datang),
                "jam_selesai": self.sim_time_to_clock(selesai)
            })

    def kedatangan(self):
        for i in range(self.config.NUM_MAHASISWA):
            self.env.process(self.mahasiswa(i))
            yield self.env.timeout(self.interarrival_time())

    def run(self):
        self.env.process(self.kedatangan())
        self.env.run()
        return pd.DataFrame(self.data)


# ======================================================
# VISUALISASI
# ======================================================
def plot_waiting_time(df):
    fig = px.histogram(
        df,
        x="waktu_tunggu",
        nbins=30,
        title="Distribusi Waktu Tunggu Mahasiswa",
        labels={"waktu_tunggu": "Menit"}
    )
    fig.add_vline(
        x=df["waktu_tunggu"].mean(),
        line_dash="dash",
        line_color="red",
        annotation_text="Rata-rata"
    )
    return fig


def plot_timeline(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["waktu_datang"],
        y=df["id"],
        mode="markers",
        name="Datang",
        marker=dict(size=5)
    ))

    fig.add_trace(go.Scatter(
        x=df["waktu_selesai"],
        y=df["id"],
        mode="markers",
        name="Selesai",
        marker=dict(size=5)
    ))

    fig.update_layout(
        title="Timeline Kedatangan & Penyelesaian",
        xaxis_title="Menit",
        yaxis_title="ID Mahasiswa"
    )
    return fig


def plot_utilization(df, config):
    total_time = df["waktu_selesai"].max()
    util = []

    for k in range(1, config.NUM_KELOMPOK + 1):
        service = df[df["kelompok"] == k]["waktu_layanan"].sum()
        u = service / (total_time * config.NUM_STAFF_PER_KELOMPOK) * 100
        util.append(u)

    return px.bar(
        x=[f"Kelompok {i}" for i in range(1, config.NUM_KELOMPOK + 1)],
        y=util,
        labels={"x": "Kelompok", "y": "Utilisasi (%)"},
        title="Utilisasi Staff per Kelompok"
    )


# ======================================================
# APLIKASI STREAMLIT
# ======================================================
def main():
    st.set_page_config("Simulasi Kantin DES", "🍽️", layout="wide")

    st.sidebar.header("Parameter Simulasi")

    num_mhs = st.sidebar.number_input("Jumlah Mahasiswa", 100, 2000, 500, 50)
    kelompok = st.sidebar.number_input("Jumlah Kelompok", 1, 5, 2)
    staff = st.sidebar.number_input("Staff per Kelompok", 1, 5, 2)

    min_s = st.sidebar.slider("Waktu Layanan Min (menit)", 0.5, 5.0, 1.0)
    max_s = st.sidebar.slider("Waktu Layanan Max (menit)", 1.0, 10.0, 3.0)

    start_h = st.sidebar.slider("Jam Mulai", 0, 23, 8)
    start_m = st.sidebar.slider("Menit Mulai", 0, 59, 0)

    run = st.sidebar.button("🚀 Jalankan Simulasi", type="primary")

    st.title("🍽️ Simulasi Kantin Prasmanan (DES)")

    if run:
        config = Config(
            NUM_MAHASISWA=num_mhs,
            NUM_KELOMPOK=kelompok,
            NUM_STAFF_PER_KELOMPOK=staff,
            MIN_SERVICE_TIME=min_s,
            MAX_SERVICE_TIME=max_s,
            START_HOUR=start_h,
            START_MINUTE=start_m
        )

        with st.spinner("Menjalankan simulasi..."):
            model = KantinDES(config)
            df = model.run()

        st.success("Simulasi selesai!")

        col1, col2, col3 = st.columns(3)
        col1.metric("Rata-rata Waktu Tunggu", f"{df.waktu_tunggu.mean():.2f} menit")
        col2.metric("Total Mahasiswa", len(df))
        col3.metric("Total Staff", kelompok * staff)

        st.plotly_chart(plot_waiting_time(df), use_container_width=True)
        st.plotly_chart(plot_timeline(df), use_container_width=True)
        st.plotly_chart(plot_utilization(df, config), use_container_width=True)

        with st.expander("Data Simulasi"):
            st.dataframe(df, use_container_width=True)

    else:
        st.info("Atur parameter lalu klik **Jalankan Simulasi**")


if __name__ == "__main__":
    main()
