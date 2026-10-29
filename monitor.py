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

def obtener_datos(event_input):
    if not event_input:
        return None
    clean_id = event_input.rstrip("/").split("/")[-1] if "/" in event_input else event_input.strip()
    url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            lots = data.get("lots", [])
            if lots:
                df = pd.DataFrame(lots)
                
                # Comprobar claves que la API no envía cuando el evento está en cero ventas
                if "cupos" not in df.columns:
                    df["cupos"] = 0
                if "entradas_vendidas" not in df.columns:
                    df["entradas_vendidas"] = 0
                if "cupos_disponibles" not in df
