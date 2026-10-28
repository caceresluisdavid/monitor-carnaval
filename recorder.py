import os
import json
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Zona horaria GMT-3 (Argentina)
TZ_ARG = timezone(timedelta(hours=-3))

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

def cargar_diccionario_asientos():
    if os.path.exists("mapa_asientos.json"):
        with open("mapa_asientos.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {item["order"]: item["codigo"] for item in data}
    return {}

def ejecutar_registro():
    creds_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    if not creds_json:
        print("Falta la variable GCP_SERVICE_ACCOUNT")
        return

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    libro = client.open("Logs_Ventas_Carnaval")
    sheet_totales = libro.sheet1
    
    # Obtener o crear pestaña Log_Butacas
    try:
        sheet_butacas = libro.worksheet("Log_Butacas")
    except:
        sheet_butacas = libro.add_worksheet(title="Log_Butacas", rows=1000, cols=10)
        sheet_butacas.append_row(["fecha_hora_gmt3", "noche", "codigo_butaca", "sector", "precio", "order_id"])

    # Leer ventas ya registradas para no duplicar
    registros_previos = sheet_butacas.get_all_values()
    claves_ya_registradas = set()
    if len(registros_previos) > 1:
        for fila in registros_previos[1:]:
            if len(fila) >= 6:
                # Clave única: (noche, order_id)
                claves_ya_registradas.add((fila[1], str(fila[5])))

    dicc_mapa = cargar_diccionario_asientos()
    ahora_gmt3 = datetime.now(TZ_ARG).strftime("%Y-%m-%d %H:%M:%S")

    filas_totales = []
    filas_nuevas_butacas = []

    for noche, event_id in EVENTOS.items():
        if not event_id:
            continue
        clean_id = event_id.rstrip("/").split("/")[-1] if "/" in event_id else event_id.strip()
        url = f"https://api.almotick.com/api/v1/events/{clean_id}/availability"
        
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                data = r.json()
                
                # 1. Procesar totales generales por sector
                df_lots = pd.DataFrame(data.get("lots", []))
                if not df_lots.empty:
                    df_lots["precio_unitario"] = df_lots["nombre"].apply(asignar_precio)
                    df_lots["recaudado"] = df_lots["entradas_vendidas"] * df_lots["precio_unitario"]

                    cupos = int(df_lots["cupos"].sum())
                    vendidas = int(df_lots["entradas_vendidas"].sum())
                    disp = int(df_lots["cupos_disponibles"].sum())
                    rec = float(df_lots["recaudado"].sum())
                    pct = round((vendidas / cupos) * 100, 2) if cupos > 0 else 0

                    filas_totales.append([
                        ahora_gmt3, noche, cupos, vendidas, disp, rec, pct
                    ])

                # 2. Procesar detalle de butacas vendidas
                seats_api = data.get("seats", [])
                for s in seats_api:
                    if s.get("status") == "sold":
                        order_id = str(s.get("order"))
                        if (noche, order_id) not in claves_ya_registradas:
                            cod = dicc_mapa.get(s.get("order"), f"ID-{order_id}")
                            sec = deducir_sector(cod)
                            precio = asignar_precio(sec)
                            
                            filas_nuevas_butacas.append([
                                ahora_gmt3, noche, cod, sec, precio, order_id
                            ])
                            claves_ya_registradas.add((noche, order_id))
        except Exception as e:
            print(f"Error procesando {noche}: {e}")

    # Guardar en Google Sheets
    if filas_totales:
        sheet_totales.append_rows(filas_totales)
        print(f"Totales guardados: {len(filas_totales)} filas.")

    if filas_nuevas_butacas:
        sheet_butacas.append_rows(filas_nuevas_butacas)
        print(f"Nuevas butacas registradas: {len(filas_nuevas_butacas)} filas.")
    else:
        print("No hubo butacas nuevas vendidas en esta hora.")

if __name__ == "__main__":
    ejecutar_registro()
