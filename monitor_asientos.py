import os
import json
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Detalle Individual de Asientos - Carnaval",
    page_icon="🎟️",
    layout="wide"
)

# Estilos acordes al monitor de ventas
st.markdown("""
<style>
    .stApp { background-color: #160a2c; color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: #241147; border: 1px solid #4a2182; border-radius: 10px; padding: 12px; }
    h1, h2, h3 { color: #ffb703; font-weight: 700; }
    .stSelectbox label, .stTextInput label { color: #ffb703 !important; font-weight: bold; }
    .status-sold { color: #ff4d4d; font-weight: bold; }
    .status-partial { color: #ffb703; font-weight: bold; }
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
    "camarote b": 420000, "camarote c": 420000, "palco vip 1": 450000, "palco vip 2": 450000
}

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

@st.cache_data
def cargar_mapa():
    ruta = "mapa_asientos.json"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Diccionario indexado por order numérico
        return {item["order"]: item["codigo"] for item in data}
    return {}

dicc_mapa = cargar_mapa()

st.title("🎟️ Auditoría Individual de Asientos y Módulos")

c_noche, c_btn = st.columns([4, 1])
with c_noche:
    noche_sel = st.selectbox("Seleccionar Noche a auditar:", list(EVENTOS.keys()))
with c_btn:
    st.write("")
    st.write("")
    if st.button("🔄 Actualizar Datos"):
        st.rerun()

event_id = EVENTOS[noche_sel]
url = f"https://api.almotick.com/api/v1/events/{event_id}/availability"

try:
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 200:
        data = r.json()
        seats_api = data.get("seats", [])
        
        if not dicc_mapa:
            st.warning("⚠️ No se encontró el archivo 'mapa_asientos.json' en la carpeta. Se mostrarán solo los números de orden.")

        if seats_api:
            # Procesar registros individuales
            registros = []
            for s in seats_api:
                orden = s.get("order")
                cod_asiento = dicc_mapa.get(orden, f"ID-{orden}")
                sector = s.get("tier_name", "Sin Sector")
                estado = s.get("status", "unknown").upper()
                precio = asignar_precio(sector)
                
                registros.append({
                    "Código Asiento / Módulo": cod_asiento,
                    "Sector": sector,
                    "Estado": estado,
                    "Valor Estimado": precio,
                    "Order API": orden
                })
            
            df = pd.DataFrame(registros)
            
            # Métricas superiores
            total_vendidos = len(df[df["Estado"] == "SOLD"])
            recaudado = df[df["Estado"] == "SOLD"]["Valor Estimado"].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Asientos/Módulos Vendidos", total_vendidos)
            m2.metric("Otras Reservas / Bloqueos", len(df) - total_vendidos)
            m3.metric("Monto Registrado en Asientos", f"${recaudado:,.0f}".replace(",", "."))
            
            st.markdown("---")
            
            # Filtros interactivos
            f1, f2 = st.columns(2)
            with f1:
                sectores = ["Todos"] + sorted(list(df["Sector"].dropna().unique()))
                filtro_sec = st.selectbox("Filtrar por sector:", sectores)
            with f2:
                busqueda = st.text_input("Buscar por código específico (ej: CA-004, PV1):", "").strip().upper()
            
            df_filtrado = df.copy()
            if filtro_sec != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Sector"] == filtro_sec]
            if busqueda:
                df_filtrado = df_filtrado[df_filtrado["Código Asiento / Módulo"].str.contains(busqueda, na=False)]
                
            # Formato de visualización
            df_mostrar = df_filtrado[["Código Asiento / Módulo", "Sector", "Estado", "Valor Estimado", "Order API"]].sort_values(by="Código Asiento / Módulo")
            df_mostrar["Valor Estimado"] = df_mostrar["Valor Estimado"].apply(lambda v: f"${v:,.0f}".replace(",", "."))
            
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
        else:
            st.info("No se registran butacas ocupadas en esta noche.")
    else:
        st.error(f"Error {r.status_code} al conectar con la ticketera Almotick.")
except Exception as e:
    st.error(f"Error en la consulta: {e}")
