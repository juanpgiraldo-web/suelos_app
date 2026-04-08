import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium

# --- FUNCIÓN TÉCNICA IDW (IGUAL A QGIS) ---
def interpolacion_idw(puntos_lat, puntos_lon, valores, target_lat, target_lon, power=2):
    # Calculamos distancias de los puntos de la finca al píxel actual
    distancias = np.sqrt((puntos_lat - target_lat)**2 + (puntos_lon - target_lon)**2)
    # Evitamos división por cero si el píxel coincide exactamente con un punto
    distancias[distancias == 0] = 0.00001 
    # Fórmula IDW: Peso = 1 / distancia^potencia
    pesos = 1 / (distancias**power)
    return np.sum(pesos * valores) / np.sum(pesos)

# ... (Aquí iría tu parte de conexión a Kobo igual que antes) ...

if 'df_sig' in st.session_state:
    df = st.session_state['df_sig']
    productor_sel = st.selectbox("Seleccionar Unidad Productiva:", df['productor'].unique())
    df_finca = df[df['productor'] == productor_sel].reset_index()

    m = folium.Map(
        location=[df_finca['lat'].mean(), df_finca['lon'].mean()], 
        zoom_start=18, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satélite'
    )

    capa_fusion = folium.FeatureGroup(name="Fusión Diagnóstico IDW (Estilo QGIS)", show=True)

    # Aumentamos la resolución a 25x25 para que sea más suave
    res = 25
    lats = np.linspace(df_finca['lat'].min() - 0.0002, df_finca['lat'].max() + 0.0002, res)
    lons = np.linspace(df_finca['lon'].min() - 0.0002, df_finca['lon'].max() + 0.0002, res)

    for i in range(len(lats)-1):
        for j in range(len(lons)-1):
            # Interpolamos el pH exacto para este píxel usando IDW
            ph_pixel = interpolacion_idw(
                df_finca['lat'], df_finca['lon'], df_finca['ph'], 
                lats[i], lons[j]
            )
            
            # Interpolamos el NDVI (o usamos el valor del vecino para esta demo)
            ndvi_pixel = interpolacion_idw(
                df_finca['lat'], df_finca['lon'], df_finca['ndvi'], 
                lats[i], lons[j]
            )

            # --- LÓGICA DE FUSIÓN DE 4 ESCENARIOS ---
            if ph_pixel < 4.5 and ndvi_pixel < 0.5:
                color = '#FF0000' # CRÍTICO
            elif ph_pixel < 4.5:
                color = '#FFA500' # ALERTA pH
            elif ndvi_pixel < 0.5:
                color = '#800080' # VIGOR BAJO
            else:
                color = '#00FF00' # ÓPTIMO

            folium.Rectangle(
                bounds=[[lats[i], lons[j]], [lats[i+1], lons[j+1]]],
                fill=True, fill_color=color, fill_opacity=0.6,
                color=color, weight=0.5
            ).add_to(capa_fusion)

    capa_fusion.add_to(m)
    st_folium(m, width=1200, height=650)
