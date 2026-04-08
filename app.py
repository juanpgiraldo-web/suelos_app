import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Asómbrate - Diagnóstico Pro", layout="wide")

st.title("🌱 Plataforma de Diagnóstico de Suelos - Asómbrate")
st.markdown("Extracción automática de KoboToolbox y análisis de pH.")

# --- BARRA LATERAL (CONEXIÓN) ---
st.sidebar.header("Configuración de Datos")
token = st.sidebar.text_input("Token de Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Sincronizar con Kobo"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Descargando datos..."):
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            datos = res.json()['results']
            
            # --- PROCESAMIENTO DE LOS 548 PUNTOS ---
            reporte = []
            for enc in datos:
                prod = enc.get('Nombre_y_apellidos_del_productor', 'Desconocido')
                grupo = enc.get('group_ub1zk22', [])
                data_sitios = grupo[0] if isinstance(grupo, list) and len(grupo)>0 else {}
                
                for k, v in data_sitios.items():
                    if 'Sitio' in k and 'muestra' in k:
                        try:
                            partes = v.split()
                            reporte.append({
                                'Productor': prod,
                                'Lat': float(partes[0]), 'Lon': float(partes[1]),
                                'pH': float(partes[3])
                            })
                        except: continue
            
            st.session_state['df'] = pd.DataFrame(reporte)
            st.success(f"¡Sincronizado! {len(reporte)} puntos cargados.")
        else:
            st.error("Error al conectar con Kobo. Revisa el Token.")

# --- CUERPO PRINCIPAL ---
if 'df' in st.session_state:
    df = st.session_state['df']
    
    # Métricas rápidas
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Muestras", len(df))
    c2.metric("Promedio pH", round(df['pH'].mean(), 2))
    c3.metric("Fincas Analizadas", df['Productor'].nunique())

    # Mapa Interactivo
    st.subheader("📍 Mapa de Distribución de Acidez")
    m = folium.Map(location=[df['Lat'].mean(), df['Lon'].mean()], zoom_start=14)
    
    for _, row in df.iterrows():
        color = 'red' if row['pH'] < 4.5 else 'orange' if row['pH'] < 5.5 else 'green'
        folium.CircleMarker(
            location=[row['Lat'], row['Lon']],
            radius=5,
            color=color,
            fill=True,
            popup=f"Productor: {row['Productor']}<br>pH: {row['pH']}"
        ).add_to(m)
    
    st_folium(m, width=1200, height=500)

    # Tabla y Descarga
    st.subheader("📋 Datos Detallados")
    filtro_prod = st.multiselect("Filtrar por Productor", options=df['Productor'].unique())
    
    df_filtrado = df[df['Productor'].isin(filtro_prod)] if filtro_prod else df
    st.dataframe(df_filtrado, use_container_width=True)

    # Botón de descarga Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_filtrado.to_excel(writer, index=False, sheet_name='Diagnóstico')
    st.download_button(
        label="📥 Descargar Reporte en Excel",
        data=output.getvalue(),
        file_name="diagnostico_asombrate.xlsx",
        mime="application/vnd.ms-excel"
    )