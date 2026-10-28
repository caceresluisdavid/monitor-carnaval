import os
import json
import requests
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Pegá acá los 4 links o IDs
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

def ejecutar_registro():
    creds_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    if not creds_json:
        return

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Logs_Ventas_Carnaval").sheet1

    ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas_a_insertar = []

    # Recorrer las 4 noches y armar el lote completo
    for noche, event_id in EVENTOS.items():
        if not event_id or "PEGAR" in event_id:
            continue
        
        clean_id = event_id.rstrip("/").split("/")[-1] if "/" in event_id else event_id.strip()
        url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
        
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data.get("lots", []))
                if not df.empty:
                    df["precio_unitario"] = df["nombre"].apply(asignar_precio)
                    df["recaudado"] = df["entradas_vendidas"] * df["precio_unitario"]

                    cupos = int(df["cupos"].sum())
                    vendidas = int(df["entradas_vendidas"].sum())
                    disp = int(df["cupos_disponibles"].sum())
                    rec = float(df["recaudado"].sum())
                    pct = round((vendidas / cupos) * 100, 2) if cupos > 0 else 0

                    filas_a_insertar.append([
                        ahora_str,
                        noche, cupos, vendidas, disp, rec, pct
                    ])
        except Exception as e:
            print(f"Error en {noche}: {e}")

    # Escribe todas las noches juntas en una sola llamada a Google Sheets
    if filas_a_insertar:
        sheet.append_rows(filas_a_insertar)
        print(f"Lote insertado con {len(filas_a_insertar)} filas.")

if __name__ == "__main__":
    ejecutar_registro()
