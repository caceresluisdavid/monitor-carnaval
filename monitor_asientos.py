import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Control Individual de Butacas y Módulos",
    page_icon="🎟️",
    layout="wide"
)

# Estética visual
st.markdown("""
<style>
    .stApp { background-color: #160a2c; color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: #241147; border: 1px solid #4a2182; border-radius: 10px; padding: 12px; }
    h1, h2, h3 { color: #ffb703; font-weight: 700; }
    .stSelectbox label, .stTextInput label { color: #ffb703 !important; font-weight: bold; }
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
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    return " ".join(t.split())

def asignar_precio(sector_nombre):
    norm = normalizar_texto(sector_nombre)
    for c, p in PRECIOS_SECTORES.items():
        if c in norm or norm in c: return p
    return 0

@st.cache_data(ttl=300)
def cargar_mapa_oficial(event_id):
    url = f"https://api.almotick.com/api/v1/events/{event_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            seats = r.json().get("evento", {}).get("seatmap", {}).get("seats", [])
            filas = []
            for s in seats:
                if "tribuna" in s.get("tier_name", "").lower():
                    continue
                filas.append({
                    "order": s.get("order"),
                    "codigo": s.get("label"),
                    "Sector": s.get("tier_name"),
                    "Precio": asignar_precio(s.get("tier_name")),
                    "enabled": s.get("enabled", True)
                })
            return pd.DataFrame(filas)
    except Exception as e:
        st.error(f"Error cargando el mapa de Almotick: {e}")
    return pd.DataFrame()

st.title("🎟️ Control Individual de Butacas y Módulos")

c1, c2 = st.columns([4, 1])
with c1:
    noche_sel = st.selectbox("Seleccionar Noche a auditar:", list(EVENTOS.keys()))
with c2:
    st.write("")
    st.write("")
    if st.button("🔄 Actualizar"):
        st.cache_data.clear()
        st.rerun()

event_id = EVENTOS[noche_sel]
df_base = cargar_mapa_oficial(event_id)

if df_base.empty:
    st.error("No se pudo conectar con la API de Almotick para descargar el mapa.")
else:
    url_avail = f"https://api.almotick.com/api/v1/events/{event_id}/availability"
    try:
        r = requests.get(url_avail, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            seats_api = data.get("seats", [])
            
            vendidos_api = set()
            for s in seats_api:
                if s.get("status") in ["sold", "partial"]:
                    vendidos_api.add(s.get("order"))

            df_actual = df_base.copy()
            
            def calcular_estado(fila):
                if fila["order"] in vendidos_api:
                    return "VENDIDO"
                if not fila["enabled"]:
                    return "RESERVADO / BLOQUEADO"
                return "LIBRE"

            df_actual["Estado"] = df_actual.apply(calcular_estado, axis=1)
            
            # Métricas: el dinero computa EXCLUSIVAMENTE sobre 'VENDIDO'
            totales = len(df_actual)
            vendidos = len(df_actual[df_actual["Estado"] == "VENDIDO"])
            bloqueados = len(df_actual[df_actual["Estado"] == "RESERVADO / BLOQUEADO"])
            libres = len(df_actual[df_actual["Estado"] == "LIBRE"])
            recaudado_efectivo = df_actual[df_actual["Estado"] == "VENDIDO"]["Precio"].sum()
            
            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
            col_m1.metric("Capacidad Numerada", f"{totales:,}".replace(",", "."))
            col_m2.metric("Butacas/Módulos Libres", f"{libres:,}".replace(",", "."))
            col_m3.metric("Butacas Vendidas", f"{vendidos:,}".replace(",", "."))
            col_m4.metric("Reservas / Bloqueos", f"{bloqueados:,}".replace(",", "."))
            col_m5.metric("Recaudación Efectiva", f"${recaudado_efectivo:,.0f}".replace(",", "."))
            
            st.markdown("---")
            
            # Filtros interactivos
            f_sec, f_est, f_bus = st.columns([2, 1, 2])
            with f_sec:
                lista_sectores = ["Todos"] + sorted(list(df_actual["Sector"].dropna().unique()))
                sec_elegido = st.selectbox("Filtrar por Sector:", lista_sectores)
            with f_est:
                filtro_estado = st.selectbox("Ver Estado:", ["Todos", "LIBRE", "VENDIDO", "RESERVADO / BLOQUEADO", "NO DISPONIBLES (Vendidos + Reservas)"])
            with f_bus:
                busqueda = st.text_input("Buscar código puntual (ej: PV2-001, SDF1-055):", "").strip().upper()
            
            # Aplicar filtros
            df_vista = df_actual.copy()
            if sec_elegido != "Todos":
                df_vista = df_vista[df_vista["Sector"] == sec_elegido]
            if filtro_estado == "LIBRE":
                df_vista = df_vista[df_vista["Estado"] == "LIBRE"]
            elif filtro_estado == "VENDIDO":
                df_vista = df_vista[df_vista["Estado"] == "VENDIDO"]
            elif filtro_estado == "RESERVADO / BLOQUEADO":
                df_vista = df_vista[df_vista["Estado"] == "RESERVADO / BLOQUEADO"]
            elif filtro_estado == "NO DISPONIBLES (Vendidos + Reservas)":
                df_vista = df_vista[df_vista["Estado"].isin(["VENDIDO", "RESERVADO / BLOQUEADO"])]

            if busqueda:
                df_vista = df_vista[df_vista["codigo"].str.contains(busqueda, na=False)]
                
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
