import requests
import pandas as pd
import streamlit as st
import time
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(
    page_title="Carnaval Paso de los Libres - Monitor Multi-Noche",
    page_icon="🎭",
    layout="wide"
)

# Estilos visuales
st.markdown("""
<style>
    .stApp { background-color: #160a2c; color: #f8f9fa; }
    section[data-testid="stSidebar"] { background-color: #110724 !important; border-right: 1px solid #3d1c6d; }
    div[data-testid="stMetric"] { background-color: #241147; border: 1px solid #4a2182; border-radius: 12px; padding: 16px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4); }
    div[data-testid="stMetric"] label { color: #ffb703 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.82rem; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.7rem !important; font-weight: 800; }
    h1 { color: #ffb703; font-family: 'Arial Black', sans-serif; text-transform: uppercase; letter-spacing: 1px; }
    h2, h3 { color: #ffa200; font-weight: 700; }
    .stButton > button { background: linear-gradient(90deg, #fb8500 0%, #ffb703 100%); color: #110724 !important; font-weight: 800; border: none; border-radius: 8px; width: 100%; padding: 0.6rem 1rem; text-transform: uppercase; }
    button[data-baseweb="tab"] { color: #adb5bd !important; font-weight: 700 !important; font-size: 1.05rem !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #ffb703 !important; border-bottom-color: #ffb703 !important; }
</style>
""", unsafe_allow_html=True)

EVENTOS = {
    "Noche 1 (16 Ene)": "6ac83585c0d0aed59622065f",
    "Noche 2": "",
    "Noche 3": "",
    "Noche 4": ""
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://almotick.com",
    "Referer": "https://almotick.com/"
}

PRECIOS_SECTORES = {
    "tribuna 1": 6000, "tribuna 2": 12000, "tribuna 3": 12000, "tribuna 4": 6000,
    "sillas a": 15000, "sillas b fila 1": 24000, "sillas b fila 2": 19000,
    "sillas c fila 1": 19000, "sillas c fila 2": 15000, "sillas d fila 1": 25000,
    "sillas d fila 2": 20000, "sillas vip": 32000, "camarote a": 400000,
    "camarote b": 420000, "camarote c": 420000, "palco vip 1": 450000, "palco vip 2": 450000
}

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Lee credenciales desde Streamlit Secrets
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Logs_Ventas_Carnaval").sheet1
        return sheet
    except Exception:
        return None

def registrar_log_horario(resultados):
    """Guarda un registro si pasó más de 1 hora desde el último log."""
    sheet = conectar_sheets()
    if not sheet:
        return

    try:
        registros = sheet.get_all_values()
        ahora = datetime.now()
        debe_guardar = False

        if len(registros) <= 1:
            debe_guardar = True
        else:
            ultima_fecha_str = registros[-1][0]
            try:
                ultima_fecha = datetime.strptime(ultima_fecha_str, "%Y-%m-%d %H:%M:%S")
                if (ahora - ultima_fecha).total_seconds() >= 3600:
                    debe_guardar = True
            except Exception:
                debe_guardar = True

        if debe_guardar:
            filas_nuevas = []
            for noche, info in resultados.items():
                df_n = info["df"]
                if df_n is not None:
                    cupos = int(df_n["cupos"].sum())
                    vendidas = int(df_n["entradas_vendidas"].sum())
                    disp = int(df_n["cupos_disponibles"].sum())
                    rec = float(df_n["recaudado"].sum())
                    pct = round((vendidas / cupos) * 100, 2) if cupos > 0 else 0
                    filas_nuevas.append([
                        ahora.strftime("%Y-%m-%d %H:%M:%S"),
                        noche, cupos, vendidas, disp, rec, pct
                    ])
            if filas_nuevas:
                sheet.append_rows(filas_nuevas)
    except Exception:
        pass

def normalizar_texto(t):
    if not isinstance(t, str): return ""
    t = t.lower().strip()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("(", ""), (")", "")):
        t = t.replace(a, b)
    return " ".join(t.split())

def asignar_precio(nombre):
    norm = normalizar_texto(nombre)
    for c, p in PRECIOS_SECTORES.items():
        if c in norm or norm in c: return p
    return 0

def consultar_evento(event_id):
    if not event_id: return None, None
    clean_id = event_id.rstrip("/").split("/")[-1] if "/" in event_id else event_id.strip()
    url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data.get("lots", []))
            if not df.empty:
                df["precio_unitario"] = df["nombre"].apply(asignar_precio)
                df["recaudado"] = df["entradas_vendidas"] * df["precio_unitario"]
                df["porcentaje_ocupado"] = ((df["entradas_vendidas"] / df["cupos"]) * 100).round(1)
                return df, data.get("generated_at")
    except Exception:
        pass
    return None, None

# --- Panel Lateral ---
st.sidebar.title("⚙️ Control")
auto_refresh = st.sidebar.checkbox("Actualizar automáticamente", value=False)
if auto_refresh:
    intervalo = st.sidebar.slider("Intervalo (segundos)", min_value=5, max_value=60, value=15)
else:
    if st.sidebar.button("🔄 Actualizar Ahora"):
        st.rerun()

st.title("🎭 CARNAVAL PASO DE LOS LIBRES")
st.markdown("### Centro de Monitoreo de Ventas y Recaudación")

resultados = {}
for nombre, ev_id in EVENTOS.items():
    df_noche, timestamp = consultar_evento(ev_id)
    resultados[nombre] = {"df": df_noche, "timestamp": timestamp}

# Intenta guardar el log horario silenciosamente
registrar_log_horario(resultados)

# Visualización por Tabs
tab_nombres = ["🌐 Total Consolidado (4 Noches)"] + list(EVENTOS.keys())
tabs = st.tabs(tab_nombres)

with tabs[0]:
    dfs_activos = [info["df"] for info in resultados.values() if info["df"] is not None]
    if dfs_activos:
        df_total = pd.concat(dfs_activos, ignore_index=True)
        df_cons = df_total.groupby("nombre", as_index=False).agg({
            "precio_unitario": "first", "cupos": "sum",
            "entradas_vendidas": "sum", "cupos_disponibles": "sum", "recaudado": "sum"
        })
        df_cons["porcentaje_ocupado"] = ((df_cons["entradas_vendidas"] / df_cons["cupos"]) * 100).round(1)

        cap_gral = df_cons["cupos"].sum()
        vend_gral = df_cons["entradas_vendidas"].sum()
        disp_gral = df_cons["cupos_disponibles"].sum()
        rec_gral = df_cons["recaudado"].sum()
        pct_gral = round((vend_gral / cap_gral) * 100, 2) if cap_gral > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Capacidad Total", f"{cap_gral:,.0f}")
        c2.metric("Total Vendidas", f"{vend_gral:,.0f}")
        c3.metric("Disponibles", f"{disp_gral:,.0f}")
        c4.metric("% Ocupación Gral.", f"{pct_gral}%")
        c5.metric("Recaudación Acumulada", f"${rec_gral:,.0f}".replace(",", "."))

        st.markdown("---")
        st.subheader("📋 Consolidado por Sector (Suma de Todas las Noches)")
        df_tabla_cons = pd.DataFrame({
            "Sector": df_cons["nombre"],
            "Precio Unit.": df_cons["precio_unitario"].apply(lambda x: f"${x:,.0f}".replace(",", ".")),
            "Capacidad Total": df_cons["cupos"],
            "Total Vendidas": df_cons["entradas_vendidas"],
            "Total Libres": df_cons["cupos_disponibles"],
            "% Ocupado": df_cons["porcentaje_ocupado"].apply(lambda x: f"{x:.1f}%"),
            "Recaudación Total": df_cons["recaudado"].apply(lambda x: f"${x:,.0f}".replace(",", "."))
        })
        st.dataframe(df_tabla_cons, use_container_width=True, hide_index=True)

        st.subheader("📊 Recaudación Acumulada por Sector (ARS)")
        df_graf = df_cons[df_cons["recaudado"] > 0]
        if not df_graf.empty:
            st.bar_chart(df_graf.set_index("nombre")["recaudado"], color="#fb8500")
    else:
        st.info("No hay datos disponibles para consolidar.")

for i, (nombre_evento, datos) in enumerate(resultados.items(), start=1):
    with tabs[i]:
        df_e = datos["df"]
        ts_e = datos["timestamp"]
        if df_e is not None:
            t_cupos = df_e["cupos"].sum()
            t_vend = df_e["entradas_vendidas"].sum()
            t_disp = df_e["cupos_disponibles"].sum()
            t_rec = df_e["recaudado"].sum()
            t_pct = round((t_vend / t_cupos) * 100, 2) if t_cupos > 0 else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Capacidad Noche", f"{t_cupos:,.0f}")
            col2.metric("Vendidas", f"{t_vend:,.0f}")
            col3.metric("Disponibles", f"{t_disp:,.0f}")
            col4.metric("% Ocupación", f"{t_pct}%")
            col5.metric("Recaudado Noche", f"${t_rec:,.0f}".replace(",", "."))

            if ts_e:
                st.caption(f"🕒 Servidor sincronizado: {ts_e}")

            st.markdown("---")
            df_v = pd.DataFrame({
                "Sector": df_e["nombre"],
                "Precio Unit.": df_e["precio_unitario"].apply(lambda x: f"${x:,.0f}".replace(",", ".")),
                "Cupos": df_e["cupos"],
                "Vendidas": df_e["entradas_vendidas"],
                "Disponibles": df_e["cupos_disponibles"],
                "% Ocupado": df_e["porcentaje_ocupado"].apply(lambda x: f"{x:.1f}%"),
                "Subtotal": df_e["recaudado"].apply(lambda x: f"${x:,.0f}".replace(",", "."))
            })
            st.dataframe(df_v, use_container_width=True, hide_index=True)

            df_gn = df_e[df_e["recaudado"] > 0]
            if not df_gn.empty:
                st.bar_chart(df_gn.set_index("nombre")["recaudado"], color="#fb8500")
        else:
            st.warning(f"No hay enlace configurado para **{nombre_evento}**.")

if auto_refresh:
    time.sleep(intervalo)
    st.rerun()