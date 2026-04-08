import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asómbrate SIG Pro", layout="wide")
st.title("🛰️ SIG Interactivo: Suelo x Satélite")

# --- 1. PROCESAMIENTO DE DATOS ---
token = "01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c"
asset_id = "aRgtiRU7FPKoCEuCTeD7sS"

if st.sidebar.button("🔄 Sincronizar y Generar Capas"):
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
                            # Extraemos datos y asignamos un NDVI simulado (mientras el API 403 se resuelve)
                            reporte.append({
                                'lat': float(p[0]), 'lon': float(p[1]), 
                                'ph': float(p[3]), 'productor': prod,
                                'ndvi': 0.42 if float(p[3]) < 4.0 else 0.65 # Simulación lógica
                            })
                        except: continue
        st.session_state['df_sig'] = pd.DataFrame(reporte)

# --- 2. CONSTRUCCIÓN DEL MAPA MULTICAPA ---
if 'df_sig' in st.session_state:
    df = st.session_state['df_sig']
    productor_sel = st.selectbox("Seleccionar Finca:", df['productor'].unique())
    df_finca = df[df['productor'] == productor_sel]

    # Crear Mapa Base Satelital
    m = folium.Map(
        location=[df_finca['lat'].mean(), df_finca['lon'].mean()], 
        zoom_start=18,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satélite'
    )

    # --- CAPA 1: pH (Mapa de Calor) ---
    capa_ph = folium.FeatureGroup(name="Capa 1: Acidez (pH)", show=False)
    HeatMap([[r['lat'], r['lon'], r['ph']] for _, r in df_finca.iterrows()], radius=20).add_to(capa_ph)
    capa_ph.add_to(m)

    # --- CAPA 2: NDVI (Vigor) ---
    capa_ndvi = folium.FeatureGroup(name="Capa 2: Vigor (NDVI)", show=False)
    for _, row in df_finca.iterrows():
        c_ndvi = 'darkgreen' if row['ndvi'] > 0.5 else 'yellow'
        folium.Circle(location=[row['lat'], row['lon']], radius=15, color=c_ndvi, fill=True, opacity=0.4).add_to(capa_ndvi)
    capa_ndvi.add_to(m)

    # --- CAPA 3: FUSIÓN (Diagnóstico Final) ---
    capa_fusion = folium.FeatureGroup(name="Capa 3: FUSIÓN DIAGNÓSTICO", show=True)
    for _, row in df_finca.iterrows():
        # Lógica de los 4 escenarios
        if row['ph'] < 4.5 and row['ndvi'] < 0.45:
            color, diag = 'red', "CRÍTICO (pH Bajo + Vigor Bajo)"
        elif row['ph'] < 4.5:
            color, diag = 'orange', "ALERTA pH (Suelo Ácido)"
        elif row['ndvi'] < 0.45:
            color, diag = 'purple', "VIGOR BAJO (Otras causas)"
        else:
            color, diag = 'green', "ÓPTIMO"
            
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=8, color='white', weight=2, fill=True, fill_color=color, fill_opacity=0.9,
            popup=diag
        ).add_to(capa_fusion)
    capa_fusion.add_to(m)

    # AGREGAR CONTROL DE CAPAS
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
    
    st.info("💡 **Instrucciones:** En la esquina superior derecha del mapa, puedes prender y apagar las capas de pH, NDVI y Fusión.")
