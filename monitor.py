import os
import json
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
    .status-badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; }
    .status-free { background-color: #2d6a4f; color: #d8f3dc; }
    .status-partial { background-color: #d97706; color: #fef3c7; }
    .status-sold { background-color: #b91c1c; color: #fee2e2; }
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
    "tribuna 1": 6000, 
    "tribuna 2": 12000, 
    "tribuna 3": 12000, 
    "tribuna 4": 6000,
    "sillas a": 15000, 
    "sillas b fila 1": 24000, 
    "sillas b fila 2": 19000,
    "sillas c fila 1": 19000, 
    "sillas c fila 2": 15000, 
    "sillas d fila 1": 25000, 
    "sillas d fila 2": 20000, 
    "sillas vip": 32000, 
    "camarote a": 400000,
    "camarote b": 420000, 
    "camarote c": 420000, 
    "palco vip 1": 450000, 
    "palco vip 2": 450000,
    "seguro espectador menores": 4000,
    "estacionamiento": 5000
}

TRIBUNAS_INFO = {
    255: {"nombre": "Tribuna 1", "precio": 6000},
    256: {"nombre": "Tribuna 2", "precio": 12000},
    257: {"nombre": "Tribuna 3", "precio": 12000},
    258: {"nombre": "Tribuna 4", "precio": 6000}
}

def normalizar_texto(t):
    if not isinstance(t, str): 
        return ""
    t = t.lower().strip()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    return " ".join(t.split())

def asignar_precio(nombre):
    norm = normalizar_texto(nombre)
    for c, p in PRECIOS_SECTORES.items():
        if c in norm or norm in c: 
            return p
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
    return "Otros"

@st.cache_data
def cargar_universo_base():
    ruta = "mapa_asientos.json"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        # Excluir los 4 registros de tribunas generales para mantener las 1.241 butacas físicas
        df = df[~df["codigo"].str.contains("Tribuna", case=False, na=False)].copy()
        df["sector"] = df["codigo"].apply(deducir_sector)
        return df
    return pd.DataFrame()

df_base_asientos = cargar_universo_base()

def procesar_noche(event_input):
    if not event_input:
        return None, None
    clean_id = event_input.rstrip("/").split("/")[-1] if "/" in event_input else event_input.strip()
    url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            seats = data.get("seats", [])
            
            # 1. Ventas individuales de asientos numerados
            vendidos_set = set()
            tribunas_status = {255: "free", 256: "free", 257: "free", 258: "free"}
            
            for s in seats:
                order_id = s.get("order")
                status = s.get("status")
                if order_id in tribunas_status:
                    tribunas_status[order_id] = status
                elif status == "sold":
                    vendidos_set.add(order_id)
            
            # Tabla de sectores numerados
            filas_sector = []
            if not df_base_asientos.empty:
                for sector_nombre, grp in df_base_asientos.groupby("sector"):
                    cupos = len(grp)
                    orders_sector = set(grp["order"])
                    vendidas = len(orders_sector.intersection(vendidos_set))
                    disponibles = cupos - vendidas
                    precio_unid = asignar_precio(sector_nombre)
                    recaudado = vendidas * precio_unid
                    
                    filas_sector.append({
                        "Sector": sector_nombre,
                        "Capacidad": cupos,
                        "Vendidas": vendidas,
                        "Disponibles": disponibles,
                        "Precio Unitario": precio_unid,
                        "Recaudado": recaudado
                    })
            
            df_sec = pd.DataFrame(filas_sector)
            
            # Tabla de estado de tribunas
            filas_tribunas = []
            for order_id, info in TRIBUNAS_INFO.items():
                st_val = tribunas_status.get(order_id, "free")
                estado_texto = "LIBRE (Sin compras)" if st_val == "free" else ("VENTAS ACTIVAS" if st_val == "partial" else "AGOTADA")
                filas_tribunas.append({
                    "Tribuna": info["nombre"],
                    "Precio": f"${info['precio']:,.0f}".replace(",", "."),
                    "Estado Actual": estado_texto
                })
            df_trib = pd.DataFrame(filas_tribunas)
            
            return df_sec, df_trib
    except Exception as e:
        st.sidebar.error(f"Error consultando {clean_id}: {e}")
    return None, None

# Control lateral
st.sidebar.title("⚙️ CONTROL")
if st.sidebar.button("🔄 ACTUALIZAR AHORA"):
    st.rerun()

st.title("🎭 CARNAVAL PASO DE LOS LIBRES")
st.subheader("Centro de Monitoreo de Ventas y Recaudación")

datos_noches = {}
tribunas_noches = {}

for nombre, ev_id in EVENTOS.items():
    df_sec, df_trib = procesar_noche(ev_id)
    if df_sec is not None and not df_sec.empty:
        datos_noches[nombre] = df_sec
        tribunas_noches[nombre] = df_trib

pestañas = st.tabs(["🌐 Total Consolidado (4 Noches)"] + list(EVENTOS.keys()))

# Pestaña 1: Consolidado Global
with pestañas[0]:
    if datos_noches:
        total_cupos = sum(df["Capacidad"].sum() for df in datos_noches.values())
        total_vendidas = sum(df["Vendidas"].sum() for df in datos_noches.values())
        total_disponibles = sum(df["Disponibles"].sum() for df in datos_noches.values())
        total_recaudado = sum(df["Recaudado"].sum() for df in datos_noches.values())
        pct_global = round((total_vendidas / total_cupos) * 100, 2) if total_cupos > 0 else 0

        c_col1, c_col2, c_col3, c_col4 = st.columns(4)
        c_col1.metric("Capacidad Numerada (4 Noches)", f"{total_cupos:,}".replace(",", "."))
        c_col2.metric("Butacas/Módulos Vendidos", f"{total_vendidas:,}".replace(",", "."), f"{pct_global}%")
        c_col3.metric("Butacas/Módulos Libres", f"{total_disponibles:,}".replace(",", "."))
        c_col4.metric("Recaudación Numerada", f"${total_recaudado:,.0f}".replace(",", "."))

        st.markdown("---")
        st.subheader("📊 Resumen General por Noche (Ubicaciones Numeradas)")
        
        filas_resumen = []
        for n, df in datos_noches.items():
            cup = int(df["Capacidad"].sum())
            ven = int(df["Vendidas"].sum())
            disp = int(df["Disponibles"].sum())
            rec = float(df["Recaudado"].sum())
            p = round((ven / cup) * 100, 2) if cup > 0 else 0
            filas_resumen.append({
                "Noche": n,
                "Capacidad": cup,
                "Vendidas": ven,
                "Disponibles": disp,
                "Ocupación": f"{p}%",
                "Recaudación": f"${rec:,.0f}".replace(",", ".")
            })
        st.dataframe(pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True)
    else:
        st.info("Esperando respuesta de la ticketera.")

# Pestañas individuales para cada noche
for i, (nombre, ev_id) in enumerate(EVENTOS.items(), start=1):
    with pestañas[i]:
        if nombre in datos_noches:
            df = datos_noches[nombre]
            df_tr = tribunas_noches[nombre]
            
            c_cupos = int(df["Capacidad"].sum())
            c_vendidas = int(df["Vendidas"].sum())
            c_disp = int(df["Disponibles"].sum())
            c_rec = float(df["Recaudado"].sum())
            c_pct = round((c_vendidas / c_cupos) * 100, 2) if c_cupos > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Capacidad Numerada", f"{c_cupos:,}".replace(",", "."))
            col1.metric("Butacas/Módulos Libres", f"{c_disp:,}".replace(",", "."))
            col2.metric("Butacas/Módulos Vendidos", f"{c_vendidas:,}".replace(",", "."), f"{c_pct}%")
            col4.metric("Recaudación Numerada", f"${c_rec:,.0f}".replace(",", "."))

            st.markdown("---")
            
            c_izq, c_der = st.columns([3, 2])
            
            with c_izq:
                st.subheader("Desglose por Sector Numerado")
                df_mostrar = df.copy()
                df_mostrar["Precio Unitario"] = df_mostrar["Precio Unitario"].apply(lambda p: f"${p:,.0f}".replace(",", "."))
                df_mostrar["Recaudado"] = df_mostrar["Recaudado"].apply(lambda r: f"${r:,.0f}".replace(",", "."))
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

            with c_der:
                st.subheader("Estado de Tribunas Generales")
                st.dataframe(df_tr, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.subheader("Tarifas de Adicionales")
                st.markdown("""
                * **Seguro Espectador Menores:** $4.000 *(Adicional por checkout)*
                * **Estacionamiento:** $5.000 *(Adicional por checkout)*
                """)
        else:
            st.warning(f"No se recibieron datos para {nombre}.")
