import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Monitor Ventas - Carnaval Paso de los Libres",
    page_icon="🎭",
    layout="wide"
)

# Estética visual
st.markdown("""
<style>
    .stApp { background-color: #160a2c; color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: #241147; border: 1px solid #4a2182; border-radius: 10px; padding: 12px; }
    h1, h2, h3 { color: #ffb703; font-weight: 700; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #241147; border-radius: 8px 8px 0 0; color: #ced4da; padding: 8px 16px; }
    .stTabs [aria-selected="true"] { background-color: #e63946 !important; color: white !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

EVENTOS = {
    "Noche 1 (16 Ene)": "6ae205cb8562ca9d7bfe35af",
    "Noche 2 (23 Ene)": "6ae20fe68562ca9d7bfe3acf",
    "Noche 3 (30 Ene)": "6ae212cf8562ca9d7bfe3fb9",
    "Noche 4 (06 Feb)": "6ae215cf8562ca9d7bfe44a3"
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
    "camarote b": 420000, "camarote c": 420000, "palco vip 1": 450000, "palco vip 2": 450000,
    "seguro espectador menores": 4000, "estacionamiento": 5000
}

def normalizar_texto(t):
    if not isinstance(t, str): return ""
    t = t.lower().strip()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    return " ".join(t.split())

def asignar_precio(nombre):
    norm = normalizar_texto(nombre)
    for c, p in PRECIOS_SECTORES.items():
        if c in norm or norm in c: return p
    return 0

def obtener_datos(event_input):
    if not event_input:
        return None
    # Extrae el ID si viene una URL completa o con barras finales
    clean_id = event_input.rstrip("/").split("/")[-1] if "/" in event_input else event_input.strip()
    url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            lots = data.get("lots", [])
            if lots:
                df = pd.DataFrame(lots)
                df["precio_unitario"] = df["nombre"].apply(asignar_precio)
                df["recaudado"] = df["entradas_vendidas"] * df["precio_unitario"]
                return df
    except Exception as e:
        st.sidebar.error(f"Error consultando {clean_id}: {e}")
    return None

# Barra lateral
st.sidebar.title("⚙️ CONTROL")
if st.sidebar.button("🔄 ACTUALIZAR AHORA"):
    st.rerun()

st.title("🎭 CARNAVAL PASO DE LOS LIBRES")
st.subheader("Centro de Monitoreo de Ventas y Recaudación")

datos_noches = {}
for nombre, ev_id in EVENTOS.items():
    df_noche = obtener_datos(ev_id)
    if df_noche is not None and not df_noche.empty:
        datos_noches[nombre] = df_noche

pestañas = st.tabs(["🌐 Total Consolidado (4 Noches)"] + list(EVENTOS.keys()))

# Pestaña 1: Consolidado
with pestañas[0]:
    if datos_noches:
        total_cupos = sum(df["cupos"].sum() for df in datos_noches.values())
        total_vendidas = sum(df["entradas_vendidas"].sum() for df in datos_noches.values())
        total_disponibles = sum(df["cupos_disponibles"].sum() for df in datos_noches.values())
        total_recaudado = sum(df["recaudado"].sum() for df in datos_noches.values())
        pct_global = round((total_vendidas / total_cupos) * 100, 2) if total_cupos > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cupos Totales (4 Noches)", f"{total_cupos:,}".replace(",", "."))
        m2.metric("Entradas Vendidas", f"{total_vendidas:,}".replace(",", "."), f"{pct_global}%")
        m3.metric("Entradas Disponibles", f"{total_disponibles:,}".replace(",", "."))
        m4.metric("Recaudación Total Estimada", f"${total_recaudado:,.0f}".replace(",", "."))

        st.markdown("---")
        st.subheader("📊 Resumen General por Noche")
        
        filas_resumen = []
        for n, df in datos_noches.items():
            cup = int(df["cupos"].sum())
            ven = int(df["entradas_vendidas"].sum())
            disp = int(df["cupos_disponibles"].sum())
            rec = float(df["recaudado"].sum())
            p = round((ven / cup) * 100, 2) if cup > 0 else 0
            filas_resumen.append({
                "Noche": n,
                "Cupos": cup,
                "Vendidas": ven,
                "Disponibles": disp,
                "Ocupación": f"{p}%",
                "Recaudación": f"${rec:,.0f}".replace(",", ".")
            })
        st.dataframe(pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True)
    else:
        st.info("No se pudieron obtener datos de la ticketera en este momento. Verificá que los enlaces de los eventos estén activos.")

# Pestañas individuales para cada noche
for i, (nombre, ev_id) in enumerate(EVENTOS.items(), start=1):
    with pestañas[i]:
        if nombre in datos_noches:
            df = datos_noches[nombre]
            c_cupos = int(df["cupos"].sum())
            c_vendidas = int(df["entradas_vendidas"].sum())
            c_disp = int(df["cupos_disponibles"].sum())
            c_rec = float(df["recaudado"].sum())
            c_pct = round((c_vendidas / c_cupos) * 100, 2) if c_cupos > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Capacidad Total", f"{c_cupos:,}".replace(",", "."))
            col1.metric("Entradas Disponibles", f"{c_disp:,}".replace(",", "."))
            col2.metric("Entradas Vendidas", f"{c_vendidas:,}".replace(",", "."), f"{c_pct}%")
            col4.metric("Recaudación Noche", f"${c_rec:,.0f}".replace(",", "."))

            st.markdown("---")
            st.subheader("Desglose por Sector")
            
            df_mostrar = df[["nombre", "cupos", "entradas_vendidas", "cupos_disponibles", "precio_unitario", "recaudado"]].copy()
            df_mostrar.columns = ["Sector", "Capacidad", "Vendidas", "Disponibles", "Precio Unitario", "Recaudado"]
            df_mostrar["Precio Unitario"] = df_mostrar["Precio Unitario"].apply(lambda p: f"${p:,.0f}".replace(",", "."))
            df_mostrar["Recaudado"] = df_mostrar["Recaudado"].apply(lambda r: f"${r:,.0f}".replace(",", "."))
            
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No se recibieron datos para {nombre}.")
