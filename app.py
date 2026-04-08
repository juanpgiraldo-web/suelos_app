import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import io

# --- 1. CONFIGURACIÓN DE PÁGINA (Layout Wide) ---
st.set_page_config(page_title="Asómbrate SIG Áreas", layout="wide", page_icon="☕")

# Título y Descripción con Estilo
st.title("☕ Plataforma de Diagnóstico SIG Áreas - Asómbrate")
st.markdown("Intersección Geoespacial de Superficies de Suelo (pH) y Satélite (NDVI).")

# --- 2. BARRA LATERAL (RECUPERADA: Conexión Kobo) ---
st.sidebar.image("https://www.asombrate.org/logo.png", width=200) # Opcional: Logo de Asómbrate
st.sidebar.header("📡 Sincronización de Datos")
token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Sincronizar y Generar Superficies"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Generando superficies continuas de diagnóstico..."):
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                datos_raw = res.json()['results']
                reporte = []
                for enc in datos_raw:
                    prod = enc.get('Nombre_y_apellidos_del_productor', 'Desconocido')
                    grupo = enc.get('group_ub1zk22', [])
                    data_sitios = grupo[0] if isinstance(grupo, list) and len(grupo)>0 else grupo
                    if isinstance(data_sitios, dict):
                        for k, v in data_sitios.items():
                            if 'Sitio' in k and 'muestra' in k:
                                try:
                                    p = v.split()
                                    reporte.append({
                                        'Lat': float(p[0]), 'Lon': float(p[1]), 
                                        'pH': float(p[3]), 'Productor': prod,
                                        # Simulación de NDVI (mientras el API 403 se resuelve)
                                        'NDVI': 0.42 if float(p[3]) < 4.2 else 0.68 
                                    })
                                except: continue
                
                df = pd.DataFrame(reporte)
                st.session_state['df_areas'] = df
                st.sidebar.success(f"✅ ¡{len(df)} puntos cargados!")
            else:
                st.sidebar.error("❌ Error al conectar con Kobo.")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error: {e}")

# --- 3. MOTOR DE INTERPOLACIÓN (CREADOR DE SUPERFICIES) ---
def interpolacion_idw(puntos_lat, puntos_lon, valores, target_lat, target_lon, power=2):
    distancias = np.sqrt((puntos_lat - target_lat)**2 + (puntos_lon - target_lon)**2)
    distancias[distancias == 0] = 0.00001 # Evitar división por cero
    pesos = 1 / (distancias**power)
    return np.sum(pesos * valores) / np.sum(pesos)

# --- 4. VISUALIZACIÓN MULTICAPA (ÁREAS) ---
if 'df_areas' in st.session_state:
    df = st.session_state['df_areas']
    
    # Métricas Recuperadas
    col1, col2, col3 = st.columns(3)
    col1.metric("Puntos", len(df))
    col2.metric("pH Promedio", round(df['pH'].mean(), 2))
    col3.metric("Fincas", df['Productor'].nunique())

    productor_sel = st.selectbox("Seleccionar Unidad Productiva:", df['Productor'].unique())
    df_finca = df[df['Productor'] == productor_sel].reset_index()

    # Mapa base satelital
    m = folium.Map(
        location=[df_finca['Lat'].mean(), df_finca['Lon'].mean()], 
        zoom_start=18, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satélite'
    )

    # --- DEFINICIÓN DE CAPAS (RECUPERADO CONTROL DE CAPAS) ---
    capa_ph = folium.FeatureGroup(name="Capa 1: Superficie pH", show=False)
    capa_ndvi = folium.FeatureGroup(name="Capa 2: Superficie NDVI", show=False)
    capa_fusion = folium.FeatureGroup(name="Capa 3: FUSIÓN DIAGNÓSTICO", show=True)

    # Lógica de Generación de Superficies Píxel a Píxel
    res = 20 # Resolución de la malla
    lats = np.linspace(df_finca['Lat'].min() - 0.0001, df_finca['Lat'].max() + 0.0001, res)
    lons = np.linspace(df_finca['Lon'].min() - 0.0001, df_finca['Lon'].max() + 0.0001, res)

    for i in range(len(lats)-1):
        for j in range(len(lons)-1):
            # Interpolamos pH y NDVI para generar la superficie continua
            ph_p = interpolacion_idw(df_finca['Lat'], df_finca['Lon'], df_finca['pH'], lats[i], lons[j])
            ndvi_p = interpolacion_idw(df_finca['Lat'], df_finca['Lon'], df_finca['NDVI'], lats[i], lons[j])

            # 1. Agregar a Capa pH (Interpolación Heatmap)
            # Usamos el HeatMap plugin para la Capa 1 (Estilo Colab)
            # (Se hace fuera del bucle para eficiencia, ver abajo)

            # 2. Agregar a Capa NDVI (Superficie)
            c_ndvi = 'darkgreen' if ndvi_p > 0.5 else '#A52A2A' # Marrón para vigor bajo
            folium.Rectangle(
                bounds=[[lats[i], lons[j]], [lats[i+1], lons[j+1]]],
                color=c_ndvi, fill=True, fill_opacity=0.3, weight=0
            ).add_to(capa_ndvi)

            # 3. CAPA FUSIÓN (Diagnóstico) Píxel por Píxel
            if ph_p < 4.5 and ndvi_p < 0.5: color = '#FF0000' # CRÍTICO
            elif ph_p < 4.5: color = '#FFA500' # ALERTA pH
            elif ndvi_p < 0.5: color = '#800080' # VIGOR BAJO
            else: color = '#00FF00' # ÓPTIMO

            folium.Rectangle(
                bounds=[[lats[i], lons[j]], [lats[i+1], lons[j+1]]],
                fill=True, fill_color=color, fill_opacity=0.6,
                color=color, weight=0.5, # Borde suave
                popup=f"Diag: {color}"
            ).add_to(capa_fusion)

    # Capa 1: pH (Mapa de Calor Estilo Colab)
    HeatMap([[r['Lat'], r['Lon'], r['pH']] for _, r in df_finca.iterrows()], radius=18, min_opacity=0.5).add_to(capa_ph)

    # Añadir capas al mapa y control
    capa_ph.add_to(m)
    capa_ndvi.add_to(m)
    capa_fusion.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
    st.write("💡 **Instrucciones:** Abre el control de capas (arriba a la derecha) para prender y apagar pH, NDVI o Fusión.")
