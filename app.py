import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from streamlit_folium import st_folium
from scipy.interpolate import griddata # <-- NUEVA LIBRERÍA NECESARIA
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Asómbrate SIG Continuo", layout="wide", page_icon="☕")
st.title("☕ SIG de Suelos: Superficie Continua Real (Metros)")

# --- 2. BARRA LATERAL (RECUPERADA) ---
st.sidebar.image("https://www.asombrate.org/logo.png", width=200)
st.sidebar.header("📡 Sincronización")
token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Generar Superficie Continua"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    with st.spinner("Sincronizando y generando ráster de alta resolución..."):
        try:
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
                                    reporte.append({'lat': float(p[0]), 'lon': float(p[1]), 'ph': float(p[3]), 'productor': prod})
                                except: continue
                st.session_state['df_base'] = pd.DataFrame(reporte)
                st.sidebar.success(f"✅ ¡{len(reporte)} puntos cargados!")
            else: st.sidebar.error("❌ Error de Kobo.")
        except Exception as e: st.sidebar.error(f"⚠️ Error: {e}")

# --- FUNCIÓN DE COLORIZACIÓN (ESTILO SEMÁFORO AJUSTADO) ---
def obtener_color_ph(ph):
    if ph < 4.5: return [255, 0, 0, 160]      # ROJO (Crítico)
    elif ph < 5.0: return [255, 165, 0, 160]    # NARANJA
    elif ph < 5.5: return [255, 255, 0, 160]    # AMARILLO (El 4.9 cae aquí)
    elif ph < 6.0: return [173, 255, 47, 160]   # VERDE LIMA
    else: return [0, 100, 0, 160]              # VERDE OSCURO (Óptimo)

# --- 3. GENERACIÓN DE LA SUPERFICIE CONTINUA ---
if 'df_base' in st.session_state:
    df = st.session_state['df_base']
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Muestras", len(df))
    c2.metric("pH Promedio", round(df['ph'].mean(), 2))
    c3.metric("Fincas", df['productor'].nunique())

    productor_sel = st.selectbox("Seleccionar Finca:", df['productor'].unique())
    df_f = df[df['productor'] == productor_sel].reset_index()

    # Definimos el mapa base satelital
    m = folium.Map(
        location=[df_f['lat'].mean(), df_f['lon'].mean()], 
        zoom_start=18, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satélite'
    )

    # --- MOTOR DE INTERPOLACIÓN RÁSTER (SCIPY) ---
    # 1. Crear una malla de alta resolución (grid) sobre la finca
    grid_res = 100 # Aumenta esto para más suavidad (pero más lento)
    lat_grid = np.linspace(df_f['lat'].min() - 0.0003, df_f['lat'].max() + 0.0003, grid_res)
    lon_grid = np.linspace(df_f['lon'].min() - 0.0003, df_f['lon'].max() + 0.0003, grid_res)
    grid_lon, grid_lat = np.meshgrid(lon_grid, lat_grid)

    # 2. Interpolar los valores de pH sobre la malla usando IDW (Inverse Distance Weighting)
    # Usamos griddata con método 'linear' para suavidad
    puntos_coor = np.vstack((df_f['lon'], df_f['lat'])).T
    grid_ph = griddata(puntos_coor, df_f['ph'], (grid_lon, grid_lat), method='linear')
    
    # Rellenamos los bordes (donde no hay datos) con el valor promedio para que no queden huecos blancos
    ph_promedio = df_f['ph'].mean()
    grid_ph = np.nan_to_num(grid_ph, nan=ph_promedio)

    # 3. Convertir la malla interpolada en una imagen PNG colorizada
    # Creamos una matriz RGBA
    img_rgba = np.zeros((grid_res, grid_res, 4), dtype=np.uint8)
    for i in range(grid_res):
        for j in range(grid_res):
            img_rgba[i, j] = obtener_color_ph(grid_ph[i, j])

    # Invertimos el eje Y para que coincida con las coordenadas geográficas
    img_rgba = np.flipud(img_rgba)

    # --- 4. AGREGAR CAPAS AL MAPA ---
    
    # Capa 1: Superficie Continua (Ráster)
    capa_raster = folium.FeatureGroup(name="Capa 1: Superficie pH Continua (Ráster)", show=True)
    
    # Definimos los límites geográficos exactos de la imagen
    bounds = [[lat_grid.min(), lon_grid.min()], [lat_grid.max(), lon_grid.max()]]
    
    # Superponemos la imagen interpolada sobre el mapa
    folium.raster_layers.ImageOverlay(
        image=img_rgba,
        bounds=bounds,
        opacity=0.7,
        interactive=True,
        cross_origin=False,
        zindex=1
    ).add_to(capa_raster)
    capa_raster.add_to(m)

    # Capa 2: Puntos pH con Etiquetas (RECUPERADO)
    capa_puntos = folium.FeatureGroup(name="Capa 2: Puntos pH con Etiquetas", show=True)
    for _, row in df_f.iterrows():
        # Punto circular
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4, color="white", weight=2, fill=True, fill_color="black", fill_opacity=1
        ).add_to(capa_puntos)
        
        # Etiqueta permanente
        folium.Marker(
            location=[row['lat'], row['lon']],
            icon=folium.DivIcon(
                html=f"""<div style="font-family: sans-serif; color: white; font-weight: bold; 
                background-color: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px;
                font-size: 11px; width: 35px; text-align: center;">{row['ph']}</div>""",
                icon_anchor=(17, 0)
            )
        ).add_to(capa_puntos)
    capa_puntos.add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width=1200, height=650)
