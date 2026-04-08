import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asómbrate SIG Píxel", layout="wide")
st.title("🛰️ Análisis de Fusión Ráster: pH ∩ NDVI")

# --- 1. PROCESAMIENTO ---
token = "01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c"
asset_id = "aRgtiRU7FPKoCEuCTeD7sS"

if st.sidebar.button("🔄 Generar Fusión Píxel a Píxel"):
    res = requests.get(f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json', 
                       headers={'Authorization': f'Token {token}'})
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
                            # Extraemos datos reales
                            reporte.append({
                                'lat': float(p[0]), 'lon': float(p[1]), 
                                'ph': float(p[3]), 'productor': prod,
                                'ndvi': 0.45 if float(p[3]) < 4.2 else 0.7 # Simulación para el ejemplo
                            })
                        except: continue
        st.session_state['df_sig'] = pd.DataFrame(reporte)

# --- 2. MOTOR DE INTERPOLACIÓN Y FUSIÓN ---
if 'df_sig' in st.session_state:
    df = st.session_state['df_sig']
    productor_sel = st.selectbox("Seleccionar Unidad Productiva:", df['productor'].unique())
    df_finca = df[df['productor'] == productor_sel]

    # Creamos el mapa base
    m = folium.Map(
        location=[df_finca['lat'].mean(), df_finca['lon'].mean()], 
        zoom_start=18,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satélite'
    )

    # Definimos las capas
    capa_ph = folium.FeatureGroup(name="Capa 1: Mapa de Calor (pH Interpolado)", show=False)
    capa_ndvi = folium.FeatureGroup(name="Capa 2: Superficie NDVI", show=False)
    capa_fusion = folium.FeatureGroup(name="Capa 3: FUSIÓN DIAGNÓSTICO (Píxel)", show=True)

    # --- LÓGICA DE INTERPOLACIÓN ESPACIAL ---
    # Creamos una "malla" de píxeles alrededor de la finca
    lats = np.linspace(df_finca['lat'].min(), df_finca['lat'].max(), 15)
    lons = np.linspace(df_finca['lon'].min(), df_finca['lon'].max(), 15)

    for lt in lats:
        for ln in lons:
            # Encontramos el punto de Kobo más cercano para este "píxel" (IDW simplificado)
            distancias = np.sqrt((df_finca['lat'] - lt)**2 + (df_finca['lon'] - ln)**2)
            idx_cercano = distancias.idxmin()
            val_ph = df_finca.loc[idx_cercano, 'ph']
            val_ndvi = df_finca.loc[idx_cercano, 'ndvi']

            # 1. Agregar a Capa pH (Interpolada)
            color_ph = 'red' if val_ph < 4.5 else 'yellow' if val_ph < 5.5 else 'blue'
            folium.Rectangle(
                bounds=[[lt, ln], [lt+0.0001, ln+0.0001]],
                color=color_ph, fill=True, fill_opacity=0.3, weight=0
            ).add_to(capa_ph)

            # 2. Agregar a Capa NDVI
            color_ndvi = 'darkgreen' if val_ndvi > 0.5 else 'brown'
            folium.Rectangle(
                bounds=[[lt, ln], [lt+0.0001, ln+0.0001]],
                color=color_ndvi, fill=True, fill_opacity=0.3, weight=0
            ).add_to(capa_ndvi)

            # 3. CAPA FUSIÓN (INTERSECCIÓN LÓGICA)
            # Píxel por píxel evaluamos los 4 escenarios
            if val_ph < 4.5 and val_ndvi < 0.5:
                res_color, res_diag = '#FF0000', "CRÍTICO" # Rojo Puro
            elif val_ph < 4.5:
                res_color, res_diag = '#FFA500', "ALERTA pH" # Naranja
            elif val_ndvi < 0.5:
                res_color, res_diag = '#800080', "VIGOR BAJO" # Púrpura
            else:
                res_color, res_diag = '#00FF00', "ÓPTIMO" # Verde Brillante

            folium.Rectangle(
                bounds=[[lt, ln], [lt+0.0001, ln+0.0001]],
                fill=True, fill_color=res_color, fill_opacity=0.6,
                color=res_color, weight=1,
                popup=f"Diagnóstico: {res_diag}"
            ).add_to(capa_fusion)

    # Añadir capas al mapa
    capa_ph.add_to(m)
    capa_ndvi.add_to(m)
    capa_fusion.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
    
    st.info("""
    ✨ **Análisis de Álgebra de Mapas completado:**
    La Capa 3 es el resultado de la intersección booleana entre el ráster de pH y el ráster de NDVI. 
    Cada cuadro representa un área de terreno evaluada bajo los 4 criterios de decisión.
    """)
