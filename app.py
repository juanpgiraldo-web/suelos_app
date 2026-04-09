import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Asómbrate SIG Oficial", layout="wide", page_icon="🌱")

st.title("🌱 Plataforma de Diagnóstico Oficial - Asómbrate")
st.markdown("Visualización de pH mediante Mapas de Calor Orgánicos y Puntos de Control.")

# --- 2. BARRA LATERAL (CONEXIÓN KOBO) ---
st.sidebar.image("https://www.asombrate.org/logo.png", width=200)
st.sidebar.header("📡 Sincronización en Tiempo Real")

token = st.sidebar.text_input("Token Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Sincronizar con Kobo"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Extrayendo datos reales (Filtrando vacíos)..."):
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                datos_raw = res.json()['results']
                reporte_lista = []
                
                for encuesta in datos_raw:
                    productor = encuesta.get('Nombre_y_apellidos_del_productor', 'Desconocido')
                    # Entramos al grupo de suelos detectado
                    grupo = encuesta.get('group_ub1zk22', [])
                    data_sitios = grupo[0] if isinstance(grupo, list) and len(grupo) > 0 else grupo
                    
                    if isinstance(data_sitios, dict):
                        for k, v in data_sitios.items():
                            if 'Sitio' in k and 'muestra' in k:
                                try:
                                    partes = v.split()
                                    # EXTRACCIÓN BLINDADA: Solo si existen los 4 datos (Lat, Lon, Alt, pH)
                                    if len(partes) >= 4:
                                        val_ph = float(partes[3])
                                        
                                        # Filtro de seguridad: pH debe ser un número real entre 2 y 9
                                        if 2.0 <= val_ph <= 9.0:
                                            reporte_lista.append({
                                                'Lat': float(partes[0]),
                                                'Lon': float(p[1]) if 'p' in locals() else float(partes[1]),
                                                'pH': val_ph,
                                                'Productor': productor
                                            })
                                except (ValueError, IndexError):
                                    # Si el dato está mal formado o vacío, se ignora por completo
                                    continue
                
                df_final = pd.DataFrame(reporte_lista)
                if not df_final.empty:
                    st.session_state['df_oficial'] = df_final
                    st.sidebar.success(f"✅ ¡{len(df_final)} puntos reales cargados!")
                else:
                    st.sidebar.warning("⚠️ No se encontraron puntos con datos de pH válidos.")
            else:
                st.sidebar.error(f"❌ Error de conexión: {res.status_code}")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error técnico: {e}")

# --- 3. CUERPO PRINCIPAL Y MAPA ---
if 'df_oficial' in st.session_state:
    df = st.session_state['df_oficial']
    
    # Métricas de control
    c1, c2, c3 = st.columns(3)
    c1.metric("Puntos con pH", len(df))
    c2.metric("pH Promedio", round(df['pH'].mean(), 2))
    c3.metric("Fincas Validadas", df['Productor'].nunique())

    # Selector de Productor
    productor_sel = st.selectbox("Seleccione la Finca para análisis:", sorted(df['Productor'].unique()))
    df_f = df[df['Productor'] == productor_sel].reset_index(drop=True)

    # Crear Mapa
    m = folium.Map(
        location=[df_f['Lat'].mean(), df_f['Lon'].mean()],
        zoom_start=18,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satélite'
    )

    # --- CAPA 1: MAPA DE CALOR (SEMÁFORO ORGÁNICO) ---
    capa_calor = folium.FeatureGroup(name="Capa 1: Mapa de Calor (pH)")
    
    heat_data = []
    for _, row in df_f.iterrows():
        # Lógica de intensidad para el gradiente (Semáforo)
        v = row['pH']
        if v < 4.5: intens = 1.0     # Rojo
        elif v < 5.0: intens = 0.7   # Naranja
        elif v < 5.5: intens = 0.5   # Amarillo
        elif v < 6.0: intens = 0.3   # Verde Lima
        else: intens = 0.1           # Verde Oscuro
        heat_data.append([row['Lat'], row['Lon'], intens])

    HeatMap(
        heat_data,
        radius=40,
        blur=25,
        min_opacity=0.3,
        gradient={0.2: '#006400', 0.4: '#ADFF2F', 0.5: '#FFFF00', 0.7: '#FFA500', 1.0: '#FF0000'}
    ).add_to(capa_calor)

    # --- CAPA 2: PUNTOS REALES CON ETIQUETAS ---
    capa_puntos = folium.FeatureGroup(name="Capa 2: Puntos pH (Etiquetados)")
    for _, row in df_f.iterrows():
        # Círculo de ubicación
        folium.CircleMarker(
            location=[row['Lat'], row['Lon']],
            radius=4, color="white", weight=2, fill=True, fill_color="black", fill_opacity=1
        ).add_to(capa_puntos)
        
        # Etiqueta de valor
        folium.Marker(
            location=[row['Lat'], row['Lon']],
            icon=folium.DivIcon(
                html=f"""<div style="font-family: sans-serif; color: white; font-weight: bold; 
                background-color: rgba(0,0,0,0.6); padding: 2px 5px; border-radius: 3px;
                font-size: 11px; width: 35px; text-align: center;">{row['pH']}</div>""",
                icon_anchor=(17, 0)
            )
        ).add_to(capa_puntos)

    # Control y Renderizado
    capa_calor.add_to(m)
    capa_puntos.add_to(m)
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=650)
    
    # Tabla de datos para auditoría manual
    with st.expander("Ver tabla de datos original de esta finca"):
        st.dataframe(df_f[['Lat', 'Lon', 'pH']], use_container_width=True)

else:
    st.info("👈 Por favor, haz clic en el botón de sincronización en la barra lateral.")
