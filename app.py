import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Asómbrate SIG Estable", layout="wide")
st.title("☕ Visualizador de Suelos: Mapa de Calor Orgánico")

# --- 2. BARRA LATERAL (TODO RECUPERADO) ---
st.sidebar.image("https://www.asombrate.org/logo.png", width=200)
st.sidebar.header("📡 Sincronización")
token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Sincronizar Finca"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Sincronizando con Kobo..."):
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
            st.session_state['df_estable'] = pd.DataFrame(reporte)
            st.sidebar.success("✅ Datos sincronizados")

# --- 3. VISUALIZACIÓN ---
if 'df_estable' in st.session_state:
    df = st.session_state['df_estable']
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Muestras", len(df))
    c2.metric("pH Promedio", round(df['ph'].mean(), 2))
    c3.metric("Fincas", df['productor'].nunique())

    productor_sel = st.selectbox("Seleccionar Finca:", df['productor'].unique())
    df_f = df[df['productor'] == productor_sel].reset_index()

    # Mapa base satelital
    m = folium.Map(
        location=[df_f['lat'].mean(), df_f['lon'].mean()], 
        zoom_start=18, 
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
        attr='Google Satélite'
    )

    # --- CAPA 1: MAPA DE CALOR (MÁXIMA CONTINUIDAD) ---
    capa_calor = folium.FeatureGroup(name="Capa 1: Mapa de Calor (Suelo)", show=True)
    
    # Preparamos los datos [lat, lon, intensidad]
    # Usamos una lógica de intensidad para el semáforo
    heat_data = []
    for _, row in df_f.iterrows():
        # A menor pH, mayor intensidad para que se vea rojo
        # Escala: pH 4.0 -> Intensidad 1.0 | pH 6.0 -> Intensidad 0.1
        intensidad = max(0.1, (7 - row['ph']) / 3) 
        heat_data.append([row['lat'], row['lon'], intensidad])

    HeatMap(
        heat_data,
        radius=45,        # Radio grande para que los puntos se fundan incluso con zoom
        blur=30,          # Desenfoque alto para evitar el efecto "bola"
        min_opacity=0.3,
        gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 0.8: 'orange', 1: 'red'}
    ).add_to(capa_calor)

    # --- CAPA 2: PUNTOS CON ETIQUETAS ---
    capa_puntos = folium.FeatureGroup(name="Capa 2: Puntos pH con Etiquetas", show=True)
    for _, row in df_f.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4, color="white", weight=2, fill=True, fill_color="black", fill_opacity=1
        ).add_to(capa_puntos)
        
        folium.Marker(
            location=[row['lat'], row['lon']],
            icon=folium.DivIcon(
                html=f"""<div style="font-family: sans-serif; color: white; font-weight: bold; 
                background-color: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px;
                font-size: 11px; width: 35px; text-align: center;">{row['ph']}</div>""",
                icon_anchor=(17, 0)
            )
        ).add_to(capa_puntos)

    # Control de Capas
    capa_calor.add_to(m)
    capa_puntos.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
