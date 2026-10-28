import os
import json
import re
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Auditoría de Asientos y Módulos",
    page_icon="🎟️",
    layout="wide"
)

# Estilos personalizados
st.markdown("""
<style>
    .stApp { background-color: #160a2c; color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: #241147; border: 1px solid #4a2182; border-radius: 10px; padding: 12px; }
    h1, h2, h3 { color: #ffb703; font-weight: 700; }
    .stSelectbox label, .stTextInput label, .stRadio label { color: #ffb703 !important; font-weight: bold; }
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
    "sillas a": 15000, "sillas b fila 1": 24000, "sillas b fila 2": 19000,
    "sillas c fila 1": 19000, "sillas c fila 2": 15000, "sillas d fila 1": 25000,
    "sillas d fila 2": 20000, "sillas vip": 32000, "camarote a": 400000,
    "camarote b": 420000, "camarote c": 420000, "palco vip 1": 450000, "palco vip 2": 450000
}

def normalizar_texto(t):
    if not isinstance(t, str): return ""
    t = t.lower().strip()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    return " ".join(t.split())

def asignar_precio(sector_nombre):
    norm = normalizar_texto(sector_nombre)
    for c, p in PRECIOS_SECTORES.items():
        if c in norm or norm in c: return p
    return 0

def deducir_sector(codigo):
    c = str(codigo).upper()
    if c.startswith("SA-"): return "Sillas A"
    if c.startswith("PV1-"): return "Palco Vip 1"
    if c.startswith("PV2-") or c.startswith("PV-"): return "Palco Vip 2"
    if c.startswith("CA-"): return "Camarote A"
    if c.startswith("CB-"): return "Camarote B"
    if c.startswith("CC-"): return "Camarote C"
    if c.startswith("SV-"): return "Sillas Vip"
    if c.startswith("SBF1-"): return "Sillas B fila 1"
    if c.startswith("SBF2-"): return "Sillas B fila 2"
    if c.startswith("SCF1-"): return "Sillas C fila 1"
    if c.startswith("SCF2-"): return "Sillas C fila 2"
    if c.startswith("SDF1-"): return "Sillas D fila 1"
    if c.startswith("SDF2-"): return "Sillas D fila 2"
    if "TRIBUNA" in c: return "Tribunas"
    return "Otros"

@st.cache_data
def cargar_asientos_totales():
    ruta = "mapa_asientos.json"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        df_base = pd.DataFrame(data)
        # Excluimos las tribunas generales del mapa individual de butacas numeradas
        df_base = df_base[~df_base["codigo"].str.contains("Tribuna", case=False, na=False)].copy()
        df_base["Sector"] = df_base["codigo"].apply(deducir_sector)
        df_base["Precio"] = df_base["Sector"].apply(asignar_precio)
        return df_base
    return pd.DataFrame()

df_universo = cargar_asientos_totales()

st.title("🎟️ Control Individual de Butacas y Módulos")

c1, c2 = st.columns([4, 1])
with c1:
    noche_sel = st.selectbox("Seleccionar Noche a auditar:", list(EVENTOS.keys()))
with c2:
    st.write("")
    st.write("")
    if st.button("🔄 Actualizar"):
        st.rerun()

event_id = EVENTOS[noche_sel]
url = f"https://api.almotick.com/api/v1/events/{event_id}/availability"

if df_universo.empty:
    st.error("⚠️ No se encontró el archivo 'mapa_asientos.json' en el repositorio.")
else:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            seats_api = data.get("seats", [])
            
            # Mapear los orders vendidos devueltos por la API
            ordenes_ocupadas = {}
            for s in seats_api:
                if s.get("status") == "sold":
                    ordenes_ocupadas[s.get("order")] = "VENDIDO"
                elif s.get("status") == "partial":
                    ordenes_ocupadas[s.get("order")] = "PARCIAL"

            # Copiar el mapa de los 1.245 asientos
            df_actual = df_universo.copy()
            df_actual["Estado"] = df_actual["order"].map(lambda o: ordenes_ocupadas.get(o, "LIBRE"))
            
            # Métricas
            totales = len(df_actual)
            vendidos = len(df_actual[df_actual["Estado"] == "VENDIDO"])
            libres = len(df_actual[df_actual["Estado"] == "LIBRE"])
            recaudado = df_actual[df_actual["Estado"] == "VENDIDO"]["Precio"].sum()
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Capacidad Numerada", f"{totales:,}".replace(",", "."))
            col_m2.metric("Butacas/Módulos Libres", f"{libres:,}".replace(",", "."))
            col_m3.metric("Butacas/Módulos Vendidos", f"{vendidos:,}".replace(",", "."))
            col_m4.metric("Recaudación Butacas", f"${recaudado:,.0f}".replace(",", "."))
            
            st.markdown("---")
            
            # Filtros interactivos
            f_sec, f_est, f_bus = st.columns([2, 1, 2])
            with f_sec:
                lista_sectores = ["Todos"] + sorted(list(df_actual["Sector"].unique()))
                sec_elegido = st.selectbox("Filtrar por Sector:", lista_sectores)
            with f_est:
                filtro_estado = st.selectbox("Ver Estado:", ["Todos", "LIBRE", "VENDIDO"])
            with f_bus:
                busqueda = st.text_input("Buscar código puntual (ej: CA-004, PV1-011):", "").strip().upper()
            
            # Aplicar filtros
            df_vista = df_actual.copy()
            if sec_elegido != "Todos":
                df_vista = df_vista[df_vista["Sector"] == sec_elegido]
            if filtro_estado != "Todos":
                df_vista = df_vista[df_vista["Estado"] == filtro_estado]
            if busqueda:
                df_vista = df_vista[df_vista["codigo"].str.contains(busqueda, na=False)]
                
            # Tabla final limpia
            df_vista = df_vista.rename(columns={
                "codigo": "Código Butaca / Módulo",
                "Precio": "Valor Unitario",
                "order": "Order ID"
            })
            
            df_vista["Valor Unitario"] = df_vista["Valor Unitario"].apply(lambda p: f"${p:,.0f}".replace(",", "."))
            
            st.dataframe(
                df_vista[["Código Butaca / Módulo", "Sector", "Estado", "Valor Unitario", "Order ID"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.error(f"Error {r.status_code} al consultar la ticketera.")
    except Exception as e:
        st.error(f"Error: {e}")
