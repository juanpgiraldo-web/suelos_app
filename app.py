import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Asómbrate - Mapa de Calor Real", layout="wide")
st.title("☕ Visualizador de Suelos: Mapa de Calor y Puntos pH")

# --- 2. BARRA LATERAL (CONEXIÓN KOBO) ---
st.sidebar.header("📡 Sincronización")
token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Cargar Datos de Finca"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Obteniendo datos de Kobo..."):
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
                                    'ph': float(p[3]), 'productor': prod
                                })
                            except: continue
            st.session_state['df_base'] = pd.DataFrame(reporte)
            st.sidebar.success("✅ Datos sincronizados")

# --- 3. GENERACIÓN DEL MAPA ---
if 'df_base' in st.session_state:
    df = st.session_state['df_base']
    
    # Métricas superiores
    c1, c2, c3 = st.columns(3)
    c1.metric("Muestras", len(df))
    c2.metric("pH Promedio", round(df['ph'].mean(), 2))
    c3.metric("Fincas", df['productor'].nunique())

    productor_sel = st.selectbox("Seleccionar Finca para visualizar:", df['productor'].unique())
    df_f = df[df['productor'] == productor_sel].reset_index()

    # Mapa base satelital de Google
    m = folium.Map(
        location=[df_f['lat'].mean(), df_f['lon'].mean()], 
        zoom_start=18, 
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
        attr='Google Satélite'
    )

    # --- CAPA 1: MAPA DE CALOR (ESTILO COLAB) ---
    # Esta es la "mancha" orgánica que querías.
    capa_calor = folium.FeatureGroup(name="Capa 1: Mapa de Calor (pH)")
    # Creamos la lista de intensidad [lat, lon, intensidad]
    # Usamos (7 - ph) para que los pH más bajos (ácidos) brillen más en rojo
    heat_data = [[row['lat'], row['lon'], (7 - row['ph'])] for _, row in df_f.iterrows()]
    
    HeatMap(
        heat_data, 
        radius=35, # Ajusta esto para que la mancha sea más o menos grande
        blur=20, 
        min_opacity=0.3,
        gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'} # Colores según acidez
    ).add_to(capa_calor)

    # --- CAPA 2: PUNTOS CON ETIQUETAS ---
    capa_puntos = folium.FeatureGroup(name="Capa 2: Puntos pH con Etiquetas")
    for _, row in df_f.iterrows():
        # Punto circular
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4,
            color="white",
            weight=2,
            fill=True,
            fill_color="black",
            fill_opacity=1
        ).add_to(capa_puntos)
        
        # Etiqueta permanente con el valor del pH
        folium.Marker(
            location=[row['lat'], row['lon']],
            icon=folium.DivIcon(
                html=f"""<div style="font-family: sans-serif; color: white; font-weight: bold; 
                background-color: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px;
                font-size: 12px; width: 40px; text-align: center;">{row['ph']}</div>""",
                icon_anchor=(20, 0) # Posiciona la etiqueta respecto al punto
            )
        ).add_to(capa_puntos)

    # Añadir capas y control
    capa_calor.add_to(m)
    capa_puntos.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
    
    st.info("💡 En esta versión hemos vuelto a la mancha orgánica (HeatMap) y añadido etiquetas numéricas fijas sobre cada punto.")
