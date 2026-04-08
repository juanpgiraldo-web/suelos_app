import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Asómbrate - Diagnóstico Pro", layout="wide", page_icon="🌱")

# Estilo personalizado para el título
st.title("🌱 Plataforma de Diagnóstico Asómbrate")
st.markdown("""
Esta aplicación extrae datos en tiempo real de **KoboToolbox**, procesa los grupos anidados de suelos 
y genera un análisis visual de acidez (pH).
""")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
st.sidebar.image("https://www.asombrate.org/logo.png", width=200) # Opcional: Logo de Asómbrate
st.sidebar.header("🛠️ Conexión con Kobo")

token = st.sidebar.text_input("Token de API Kobo", value="01dbd69d8e9ae587eaeddc25f8cf9f35377cb08c", type="password")
asset_id = st.sidebar.text_input("Asset UID (Formulario)", value="aRgtiRU7FPKoCEuCTeD7sS")

if st.sidebar.button("🔄 Sincronizar Datos Ahora"):
    headers = {'Authorization': f'Token {token}'}
    url = f'https://kf.kobotoolbox.org/api/v2/assets/{asset_id}/data.json'
    
    with st.spinner("Conectando con el servidor de Kobo..."):
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                datos_raw = res.json()['results']
                
                # --- MOTOR DE EXTRACCIÓN (CIRUGÍA DE DATOS) ---
                reporte_lista = []
                for encuesta in datos_raw:
                    productor = encuesta.get('Nombre_y_apellidos_del_productor', 'Desconocido')
                    fecha = encuesta.get('start', 'N/A')
                    
                    # Entramos al grupo específico que detectamos
                    grupo_sitios = encuesta.get('group_ub1zk22', [])
                    # Kobo a veces manda el grupo como lista o como dict
                    data_sitios = grupo_sitios[0] if isinstance(grupo_sitios, list) and len(grupo_sitios) > 0 else grupo_sitios
                    
                    if isinstance(data_sitios, dict):
                        for k, v in data_sitios.items():
                            if 'Sitio' in k and 'muestra' in k:
                                try:
                                    # Formato: 'Latitud Longitud Altitud pH'
                                    partes = v.split()
                                    reporte_lista.append({
                                        'Productor': productor,
                                        'Fecha': fecha,
                                        'Latitud': float(partes[0]),
                                        'Longitud': float(partes[1]),
                                        'Altitud': float(partes[2]),
                                        'pH': float(partes[3])
                                    })
                                except: continue
                
                # Guardamos en el estado de la sesión para no perder datos al filtrar
                st.session_state['data_final'] = pd.DataFrame(reporte_lista)
                st.success(f"✅ ¡Éxito! Se cargaron {len(reporte_lista)} puntos de muestreo.")
            else:
                st.error(f"❌ Error de Kobo: {res.status_code}. Verifica el Token.")
        except Exception as e:
            st.error(f"⚠️ Error de conexión: {e}")

# --- CUERPO PRINCIPAL (VISUALIZACIÓN) ---
if 'data_final' in st.session_state:
    df = st.session_state['data_final']

    # 1. Métricas de resumen
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Muestras Totales", len(df))
    col2.metric("pH Promedio", round(df['pH'].mean(), 2))
    col3.metric("Fincas", df['Productor'].nunique())
    col4.metric("pH Mínimo", df['pH'].min())

    # 2. Mapa Interactivo
    st.subheader("📍 Mapa de Acidez en Campo")
    
    # Crear el mapa base centrado en el promedio
    m = folium.Map(location=[df['Latitud'].mean(), df['Longitud'].mean()], zoom_start=15, control_scale=True)
    
    # Agregar puntos al mapa con colores por pH
    for _, row in df.iterrows():
        # Lógica de colores: Rojo (Muy Ácido), Naranja (Ácido), Verde (Óptimo)
        color_punto = 'red' if row['pH'] < 4.5 else 'orange' if row['pH'] < 5.5 else 'green'
        
        folium.CircleMarker(
            location=[row['Latitud'], row['Longitud']],
            radius=6,
            color=color_punto,
            fill=True,
            fill_opacity=0.7,
            popup=f"<b>Productor:</b> {row['Productor']}<br><b>pH:</b> {row['pH']}<br><b>Altitud:</b> {row['Altitud']} m"
        ).add_to(m)
    
    # Renderizar mapa en la App
    st_folium(m, width=1400, height=600)

    # 3. Filtros y Tabla
    st.divider()
    st.subheader("📋 Tabla de Datos y Descarga")
    
    filtro_nombre = st.multiselect("Filtrar por nombre del Productor:", options=df['Productor'].unique())
    
    df_mostrar = df[df['Productor'].isin(filtro_nombre)] if filtro_nombre else df
    st.dataframe(df_mostrar, use_container_width=True)

    # Botón para descargar a Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_mostrar.to_excel(writer, index=False, sheet_name='Diagnostico_Asombrate')
    
    st.download_button(
        label="📥 Descargar Diagnóstico en Excel",
        data=output.getvalue(),
        file_name="diagnostico_asombrate_kobo.xlsx",
        mime="application/vnd.ms-excel"
    )

else:
    st.info("👈 Haz clic en el botón 'Sincronizar Datos Ahora' de la izquierda para comenzar.")
