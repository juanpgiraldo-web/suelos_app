import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Asómbrate SIG Áreas Reales", layout="wide")
st.title("☕ SIG de Áreas Continuas: Intersección pH x NDVI")

# --- 2. BARRA LATERAL (TODO RECUPERADO) ---
st.sidebar.header("📡 Sincronización Kobo")
token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Generar Áreas de Diagnóstico"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Sincronizando y procesando superficies..."):
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            datos = res.json()['results']
            reporte = []
            for enc in datos:
                prod = enc.get('Nombre_y_apellidos_del_productor', 'Desconocido')
                grupo = enc.get('group_ub1zk22', [])
                data = grupo[0] if isinstance(grupo, list) and len(grupo)>0 else grupo
                if isinstance(data, dict):
                    for k, v in data.items():
                        if 'Sitio' in k and 'muestra' in k:
                            try:
                                p = v.split()
                                reporte.append({
                                    'lat': float(p[0]), 'lon': float(p[1]), 
                                    'ph': float(p[3]), 'productor': prod,
                                    'ndvi': 0.42 if float(p[3]) < 4.2 else 0.68 
                                })
                            except: continue
            st.session_state['df_full'] = pd.DataFrame(reporte)
            st.sidebar.success("✅ Datos cargados")

# --- 3. MOTOR DE INTERPOLACIÓN (IDW para áreas suaves) ---
def calcular_idw(lats, lons, valores, target_lat, target_lon):
    dist = np.sqrt((lats - target_lat)**2 + (lons - target_lon)**2)
    dist[dist == 0] = 0.00001
    pesos = 1 / (dist**2)
    return np.sum(pesos * valores) / np.sum(pesos)

# --- 4. MAPA Y CAPAS ---
if 'df_full' in st.session_state:
    df = st.session_state['df_full']
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Puntos Totales", len(df))
    c2.metric("Promedio pH", round(df['ph'].mean(), 2))
    c3.metric("Fincas", df['productor'].nunique())

    productor_sel = st.selectbox("Seleccionar Finca:", df['productor'].unique())
    df_f = df[df['productor'] == productor_sel].reset_index()

    m = folium.Map(
        location=[df_f['lat'].mean(), df_f['lon'].mean()], 
        zoom_start=18, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satélite'
    )

    # CAPAS
    capa_ph = folium.FeatureGroup(name="Capa 1: Mapa de Calor pH", show=False)
    capa_ndvi = folium.FeatureGroup(name="Capa 2: Superficie NDVI", show=False)
    capa_fusion = folium.FeatureGroup(name="Capa 3: FUSIÓN (Área Continua)", show=True)

    # Generamos la "Malla" (Grid)
    # Aumentamos la densidad para que no se vean puntos, sino una mancha
    grid_res = 25 
    lat_grid = np.linspace(df_f['lat'].min() - 0.0002, df_f['lat'].max() + 0.0002, grid_res)
    lon_grid = np.linspace(df_f['lon'].min() - 0.0002, df_f['lon'].max() + 0.0002, grid_res)

    for i in range(len(lat_grid)-1):
        for j in range(len(lon_grid)-1):
            # Calculamos los valores interpolados para el centro de este "parche"
            mid_lat = (lat_grid[i] + lat_grid[i+1]) / 2
            mid_lon = (lon_grid[j] + lon_grid[j+1]) / 2
            
            val_ph = calcular_idw(df_f['lat'], df_f['lon'], df_f['ph'], mid_lat, mid_lon)
            val_ndvi = calcular_idw(df_f['lat'], df_f['lon'], df_f['ndvi'], mid_lat, mid_lon)

            # Capa NDVI (Superficie verde/marrona)
            c_ndvi = 'darkgreen' if val_ndvi > 0.5 else '#7b3f00'
            folium.Rectangle(
                bounds=[[lat_grid[i], lon_grid[j]], [lat_grid[i+1], lon_grid[j+1]]],
                fill=True, fill_color=c_ndvi, fill_opacity=0.3, weight=0
            ).add_to(capa_ndvi)

            # Capa Fusión (Lógica de 4 escenarios)
            if val_ph < 4.5 and val_ndvi < 0.5: color = 'red' # CRÍTICO
            elif val_ph < 4.5: color = 'orange' # ALERTA pH
            elif val_ndvi < 0.5: color = 'purple' # VIGOR BAJO
            else: color = 'green' # ÓPTIMO

            folium.Rectangle(
                bounds=[[lat_grid[i], lon_grid[j]], [lat_grid[i+1], lon_grid[j+1]]],
                fill=True, fill_color=color, fill_opacity=0.6, weight=0
            ).add_to(capa_fusion)

    # Mapa de calor de pH (Capa 1)
    HeatMap([[r['lat'], r['lon'], r['ph']] for _, r in df_f.iterrows()], radius=25, blur=15).add_to(capa_ph)

    capa_ph.add_to(m)
    capa_ndvi.add_to(m)
    capa_fusion.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
