import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ======================================================
# 1. KONFIGURASI STREAMLIT & HALAMAN
# ======================================================
st.set_page_config(page_title="Production History Dashboard", layout="wide")
st.title("📊 Production History Dashboard")

file_path = "Data TBNW.xlsx"

# ======================================================
# 2. LOAD SELURUH WORKSHEET (SUMUR) DARI EXCEL
# ======================================================
@st.cache_data(ttl=5)
def load_all_sheets(path):
    excel_file = pd.ExcelFile(path)
    sheet_names = excel_file.sheet_names
    
    all_wells_data = {}
    
    for sheet in sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet)
        if df.empty:
            continue
            
        # Bersihkan spasi di nama kolom
        df.columns = df.columns.astype(str).str.strip()

        # Alias Tanggal (Cari variasi nama kolom tanggal)
        date_candidates = ["Date", "DATE", "date", "Tanggal", "TANGGAL", "Tgl", "tgl"]
        for cand in date_candidates:
            if cand in df.columns:
                df.rename(columns={cand: "Date"}, inplace=True)
                break

        if "Date" not in df.columns:
            continue

        aliases = {
            "Oil Rate": ["Oil Rate", "Oil", "BOPD", "bopd"],
            "Water Rate": ["Water Rate", "Water", "BWPD", "bwpd"],
            "Liq Rate": ["Liq Rate", "BFPD", "bfpd", "Liquid Rate"],
            "BSW": ["BSW", "bsw", "Water Cut", "WC"],
            "Pump Intake Press": ["Pump Intake Press", "PIP", "Pump Intake Pressure", "PIP (psi)", "Press"]
        }

        for target, cands in aliases.items():
            for c in cands:
                if c in df.columns:
                    if c != target:
                        df.rename(columns={c: target}, inplace=True)
                    break

        # Convert Tanggal Ketat
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

        if df.empty:
            continue

        numeric_cols = ["Oil Rate", "Water Rate", "Liq Rate", "BSW", "Pump Intake Press"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0

        if "Event" not in df.columns:
            df["Event"] = ""
        df["Event"] = df["Event"].fillna("").astype(str)

        def make_hover(row):
            event = row["Event"].strip()
            if event == "": event = "-"
            event = event.replace("\r\n", "<br>").replace("\n", "<br>")

            return (
                f"<b>Date :</b> {row['Date']:%d-%b-%Y %H:%M}<br><br>"
                f"<b>Liq Rate :</b> {row['Liq Rate']:.1f} BFPD<br>"
                f"<b>Oil Rate :</b> {row['Oil Rate']:.1f} BOPD<br>"
                f"<b>Water Rate :</b> {row['Water Rate']:.1f} BWPD<br>"
                f"<b>BSW :</b> {row['BSW']:.1f} %<br>"
                f"<b>Pump Intake Press :</b> {row['Pump Intake Press']:.1f} psi<br><br>"
                f"<b>Event :</b><br>{event}"
            )

        df["Hover"] = df.apply(make_hover, axis=1)
        all_wells_data[sheet] = df

    return all_wells_data

try:
    all_wells = load_all_sheets(file_path)
    if not all_wells:
        st.error("Tidak ada worksheet valid yang memiliki kolom 'Date' di file Excel ini.")
        st.stop()
except Exception as e:
    st.error(f"Gagal membaca file Excel: {e}")
    st.stop()

# ======================================================
# 3. SIDEBAR FILTER: NAMA SUMUR & RANGE TANGGAL
# ======================================================
st.sidebar.header("🛢️ Filter Dashboard")

# 1. Dropdown Filter Nama Sumur (Worksheet)
well_list = list(all_wells.keys())
selected_well = st.sidebar.selectbox("Pilih Nama Sumur:", options=well_list)

# Ambil data sumur yang dipilih
df_raw = all_wells[selected_well]

# 2. Filter Range Tanggal Sesuai Sumur yang Dipilih
min_date = df_raw["Date"].min().date()
max_date = df_raw["Date"].max().date()

selected_dates = st.sidebar.date_input(
    "Pilih Rentang Tanggal View:",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

if st.sidebar.button("🔄 Refresh Data Excel"):
    st.cache_data.clear()
    st.rerun()

if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
    start_date, end_date = selected_dates[0], selected_dates[1]
else:
    start_date, end_date = min_date, max_date

t_start = pd.to_datetime(start_date)
t_end = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

df = df_raw[(df_raw["Date"] >= t_start) & (df_raw["Date"] <= t_end)].copy()

if df.empty:
    st.warning(f"⚠️ Tidak ada data untuk sumur **{selected_well}** pada rentang tanggal tersebut. Menampilkan seluruh data sumur ini.")
    df = df_raw.copy()
    start_date, end_date = min_date, max_date

event_df = df[df["Event"].str.strip() != ""].copy()

str_start = start_date.strftime("%d-%b-%Y")
str_end = end_date.strftime("%d-%b-%Y")

# Info Box Status
st.info(f"🛢️ **SUMUR:** `{selected_well}` | 📅 **RANGE TANGGAL:** `{str_start}` s/d `{str_end}` | **Total Data:** {len(df)} baris")

# ======================================================
# 4. PLOTLY TRACES & GRAPH
# ======================================================
COLOR_OIL_RATE = "rgba(0,160,0,0.75)"
COLOR_WATER_RATE = "rgba(30,144,255,0.65)"
COLOR_LIQ_RATE = "rgba(0,82,170,0.80)"

fig = go.Figure()

# Dummy Trace Legend
fig.add_trace(go.Scatter(
    x=[df["Date"].iloc[0]], y=[None],
    mode="markers", name=f"🗓️ View: {str_start} to {str_end}",
    marker=dict(color="rgba(0,0,0,0)"), showlegend=True
))

# Oil Area
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Oil Rate"], mode="lines", name="Oil Rate",
    stackgroup="production", line=dict(color="green", width=1),
    fillcolor=COLOR_OIL_RATE, hoverinfo="skip"
))

# Water Area
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Water Rate"], mode="lines", name="Water Rate",
    stackgroup="production", line=dict(color="royalblue", width=1),
    fillcolor=COLOR_WATER_RATE, hoverinfo="skip"
))

# Liq Rate Line
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Liq Rate"], mode="lines", name="Liq Rate",
    line=dict(color=COLOR_LIQ_RATE, width=3), hoverinfo="skip"
))

# Pump Intake Press
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Pump Intake Press"], name="Pump Intake Press",
    mode="lines", line=dict(color="red", width=2, dash="dot"),
    yaxis="y2", hoverinfo="skip"
))

# Info Hover
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Liq Rate"], mode="markers", name="Info",
    marker=dict(size=12, color="rgba(0,0,0,0)"), customdata=df["Hover"],
    hovertemplate="%{customdata}<extra></extra>", showlegend=False
))

# Event Markers
if not event_df.empty:
    fig.add_trace(go.Scatter(
        x=event_df["Date"], y=event_df["Liq Rate"], mode="markers", name="Event",
        marker=dict(symbol="diamond", size=8, color="black", line=dict(color="white", width=1)),
        hoverinfo="skip"
    ))

    for _, row in event_df.iterrows():
        fig.add_vline(x=row["Date"], line_dash="dash", line_color="gray", line_width=1)

    offset_list = [-90, -140, -190, -240, -110, -160, -210, -260]
    for i, (_, row) in enumerate(event_df.iterrows()):
        event_text = row["Event"].replace("\n", "<br>")
        ay = offset_list[i % len(offset_list)]

        fig.add_annotation(
            x=row["Date"], y=row["Liq Rate"], xref="x", yref="y",
            text=f"<b>{event_text}</b>", showarrow=True, arrowhead=0, arrowsize=1, arrowwidth=1.2,
            arrowcolor="gray", ax=0, ay=ay, bgcolor="white", bordercolor="gray", borderwidth=1,
            borderpad=5, align="left", font=dict(size=9, color="black")
        )

# ======================================================
# 5. LAYOUT CONFIGURATION (DENGAN TINGGI KOTAK 700PX)
# ======================================================
fig.update_layout(
    template="plotly_white",
    height=800,  # <-- UKURAN KOTAK DIPERBESAR TINGGINYA
    title=dict(
        text=f"<b>Production History - {selected_well}</b><br><span style='font-size:15px; color:#555555;'>Range View: <b>{str_start}</b> s/d <b>{str_end}</b></span>",
        x=0.5, font=dict(size=24)
    ),
    hovermode="x",
    hoverlabel=dict(bgcolor="white", font_size=11, font_family="Arial"),
    legend=dict(orientation="h", x=0, y=1.12, bgcolor="rgba(255,255,255,0.8)"),
    margin=dict(l=80, r=40, t=130, b=80),
    xaxis=dict(
        title="Date", showline=True, linewidth=2, linecolor="black", mirror=True,
        ticks="outside", tickwidth=2, ticklen=6, showgrid=True, gridcolor="rgba(200,200,200,0.3)",
        rangeslider=dict(visible=True, thickness=0.08)
    ),
    yaxis=dict(
        title="Production (BPD)", showline=True, linewidth=2, linecolor="black", mirror=True,
        ticks="outside", tickwidth=2, ticklen=6, showgrid=True, gridcolor="rgba(220,220,220,0.6)", zeroline=False
    ),
    yaxis2=dict(
        title=dict(text="Pump Intake Press (psi)", font=dict(color="red")),
        overlaying="y", side="right", showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor="red",
        ticks="outside", tickcolor="red", tickfont=dict(color="red")
    )
)

# Render Chart dengan lebar penuh
st.plotly_chart(fig, use_container_width=True)

# Preview Data Sumur Terpilih
with st.expander(f"🔎 Klik untuk preview data 5 baris pertama sumur {selected_well}"):
    st.dataframe(df_raw.head())
