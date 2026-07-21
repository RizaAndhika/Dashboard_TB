import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ======================================================
# 1. KONFIGURASI STREAMLIT & HALAMAN
# ======================================================
st.set_page_config(page_title="Production History Dashboard", layout="wide")
st.title("📊 Production History Dashboard")

file_path = "Data TB.xlsx"

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

        # Alias Tanggal
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

        # FIX BSW DESIMAL: Jika nilai max BSW <= 1.0 (misal 0.5), kalikan 100 agar jadi persen (50.0%)
        if df["BSW"].max() <= 1.0 and df["BSW"].max() > 0:
            df["BSW"] = df["BSW"] * 100

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
# 3. SIDEBAR FILTER: NAMA SUMUR, TANGGAL & PARAMETER
# ======================================================
st.sidebar.header("🛢️ Filter Dashboard")

# 1. Dropdown Filter Nama Sumur
well_list = list(all_wells.keys())
selected_well = st.sidebar.selectbox("Pilih Nama Sumur:", options=well_list)

# Ambil data sumur yang dipilih
df_raw = all_wells[selected_well]

# 2. Filter Range Tanggal
min_date = df_raw["Date"].min().date()
max_date = df_raw["Date"].max().date()

selected_dates = st.sidebar.date_input(
    "Pilih Rentang Tanggal View:",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

# 3. Filter Parameter Yang Ditampilkan (Multi-Select)
st.sidebar.subheader("📈 Tampilkan Parameter")
available_metrics = ["Oil Rate", "Water Rate", "Liq Rate", "BSW", "Pump Intake Press"]
selected_metrics = st.sidebar.multiselect(
    "Pilih parameter grafik:",
    options=available_metrics,
    default=["Oil Rate", "Water Rate", "Liq Rate", "BSW", "Pump Intake Press"]
)

# 4. SKALA MANUAL SUMBU Y (TINGGI/RENDAH GRAFIK)
st.sidebar.subheader("📐 Skala Sumbu Y")
use_custom_y1 = st.sidebar.checkbox("Set Manual Sumbu Y Kiri (BPD)", value=False)
if use_custom_y1:
    col1, col2 = st.sidebar.columns(2)
    y1_min = col1.number_input("Y1 Min", value=0)
    y1_max = col2.number_input("Y1 Max", value=300, step=50)

use_custom_y2 = st.sidebar.checkbox("Set Manual Sumbu Y Kanan (BSW/PIP)", value=False)
if use_custom_y2:
    col3, col4 = st.sidebar.columns(2)
    y2_min = col3.number_input("Y2 Min", value=0)
    y2_max = col4.number_input("Y2 Max", value=100, step=10)

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
# 4. JUDUL HALAMAN (STREAMLIT MARKDOWN)
# ======================================================
st.markdown(
    f"""
    <div style="text-align: center; margin-top: 10px; margin-bottom: 5px;">
        <h2 style="margin:0; padding:0; font-weight:bold; color:#1E1E1E;">Production History - {selected_well}</h2>
        <p style="margin:5px 0 0 0; font-size:14px; color:#555555;">Range View: <b>{str_start}</b> s/d <b>{str_end}</b></p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ======================================================
# 5. PLOTLY TRACES & GRAPH DINAMIS
# ======================================================
COLOR_OIL_RATE = "rgba(0,160,0,0.75)"
COLOR_WATER_RATE = "rgba(30,144,255,0.65)"
COLOR_LIQ_RATE = "rgba(0,82,170,0.80)"
COLOR_BSW = "rgba(0,122,255,0.9)"
COLOR_PIP = "rgba(220,0,0,0.85)"

fig = go.Figure()

stack_area = ("Oil Rate" in selected_metrics) and ("Water Rate" in selected_metrics)

# 1. Oil Area / Line
if "Oil Rate" in selected_metrics:
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Oil Rate"], mode="lines", name="Oil Rate",
        stackgroup="production" if stack_area else None, 
        line=dict(color="green", width=1.5),
        fillcolor=COLOR_OIL_RATE if stack_area else None, hoverinfo="skip"
    ))

# 2. Water Area / Line
if "Water Rate" in selected_metrics:
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Water Rate"], mode="lines", name="Water Rate",
        stackgroup="production" if stack_area else None, 
        line=dict(color="royalblue", width=1.5),
        fillcolor=COLOR_WATER_RATE if stack_area else None, hoverinfo="skip"
    ))

# 3. Liq Rate Line
if "Liq Rate" in selected_metrics:
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Liq Rate"], mode="lines", name="Liq Rate",
        line=dict(color=COLOR_LIQ_RATE, width=3), hoverinfo="skip"
    ))

# 4. BSW Line (Di Axis Sumbu Y Kanan)
if "BSW" in selected_metrics:
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["BSW"], name="BSW (%)",
        mode="lines", line=dict(color=COLOR_BSW, width=2, dash="dashdot"),
        yaxis="y2", hoverinfo="skip"
    ))

# 5. Pump Intake Press (Di Axis Sumbu Y Kanan)
if "Pump Intake Press" in selected_metrics:
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Pump Intake Press"], name="Pump Intake Press",
        mode="lines", line=dict(color=COLOR_PIP, width=2, dash="dot"),
        yaxis="y2", hoverinfo="skip"
    ))

# 6. Dummy Trace Legend (View)
fig.add_trace(go.Scatter(
    x=[df["Date"].iloc[0]], y=[0],
    mode="markers", name=f"🗓️ View: {str_start} to {str_end}",
    marker=dict(color="rgba(0,0,0,0)", size=0),
    hoverinfo="skip", showlegend=True
))

# Info Hover
hover_y = df["Liq Rate"] if "Liq Rate" in selected_metrics else (
    df["Oil Rate"] if "Oil Rate" in selected_metrics else (
        df["Pump Intake Press"] if "Pump Intake Press" in selected_metrics else df["BSW"]
    )
)
fig.add_trace(go.Scatter(
    x=df["Date"], y=hover_y, mode="markers", name="Info",
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
# 6. PENYESUAIAN SUMBU Y KANAN (RIGHT AXIS TITLE)
# ======================================================
right_axis_title = ""  # Diinisialisasi berupa STRING "" (Menghindari TypeError/ValueError)
right_axis_color = "black"

if "BSW" in selected_metrics and "Pump Intake Press" in selected_metrics:
    right_axis_title = "BSW (%) / PIP (psi)"
    right_axis_color = "darkred"
elif "BSW" in selected_metrics:
    right_axis_title = "BSW (%)"
    right_axis_color = COLOR_BSW
elif "Pump Intake Press" in selected_metrics:
    right_axis_title = "Pump Intake Press (psi)"
    right_axis_color = COLOR_PIP

show_y2 = ("BSW" in selected_metrics) or ("Pump Intake Press" in selected_metrics)

# ======================================================
# 7. LAYOUT CONFIGURATION
# ======================================================
fig.update_layout(
    template="plotly_white",
    height=750,
    hovermode="x",
    hoverlabel=dict(bgcolor="white", font_size=11, font_family="Arial"),
    legend=dict(
        orientation="h",
        x=0,
        y=1.08,
        xanchor="left",
        yanchor="bottom",
        bgcolor="rgba(255,255,255,0.8)"
    ),
    margin=dict(l=80, r=40, t=40, b=80),
    xaxis=dict(
        title="Date", showline=True, linewidth=2, linecolor="black", mirror=True,
        ticks="outside", tickwidth=2, ticklen=6, showgrid=True, gridcolor="rgba(200,200,200,0.3)",
        rangeslider=dict(visible=True, thickness=0.08)
    ),
    yaxis=dict(
        title="Production (BPD)", showline=True, linewidth=2, linecolor="black", mirror=True,
        ticks="outside", tickwidth=2, ticklen=6, showgrid=True, gridcolor="rgba(220,220,220,0.6)", zeroline=False,
        range=[y1_min, y1_max] if use_custom_y1 else None
    ),
    yaxis2=dict(
        title=dict(text=right_axis_title, font=dict(color=right_axis_color)),
        overlaying="y", side="right", showgrid=False, zeroline=False, 
        showline=show_y2, linewidth=2, linecolor=right_axis_color, 
        ticks="outside" if show_y2 else "", tickcolor=right_axis_color, 
        tickfont=dict(color=right_axis_color), showticklabels=show_y2,
        range=[y2_min, y2_max] if (use_custom_y2 and show_y2) else None
    )
)

# Render Chart
st.plotly_chart(fig, use_container_width=True)

# Preview Data Sumur Terpilih
with st.expander(f"🔎 Klik untuk preview data 5 baris pertama sumur {selected_well}"):
    st.dataframe(df_raw.head())
