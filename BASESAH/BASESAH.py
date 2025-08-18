import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter

# === Configuración de la app ===
st.set_page_config(layout="wide", page_title="Dashboard Créditos y Captaciones")
st.title("📊 Dashboard Créditos y Captaciones")
st.markdown("---")

# === 1. Función para cargar y preparar datos desde GitHub ===
@st.cache_data
def load_creditos(urls):
    df_list = []
    for url in urls:
        try:
            df = pd.read_excel(url, engine="openpyxl")
            df_list.append(df)
        except Exception as e:
            st.error(f"No se pudo cargar el archivo: {url}\n{e}")
    if not df_list:
        return None
    df_all = pd.concat(df_list, ignore_index=True)
    df_all['TASAINTERES'] = pd.to_numeric(df_all['TASAINTERES'], errors='coerce')
    df_all['DEUDAINICIAL'] = pd.to_numeric(df_all['DEUDAINICIAL'], errors='coerce')
    df_all['DIASATRASO'] = pd.to_numeric(df_all['DIASATRASO'], errors='coerce')
    df_all['FECHAADJUDICACION'] = pd.to_datetime(df_all['FECHAADJUDICACION'], errors='coerce')
    df_all['AÑO'] = df_all['FECHAADJUDICACION'].dt.year
    return df_all

@st.cache_data
def load_captaciones(urls):
    df_list = []
    for url in urls:
        try:
            df = pd.read_excel(url, engine="openpyxl")
            df_list.append(df)
        except Exception as e:
            st.error(f"No se pudo cargar el archivo: {url}\n{e}")
    if not df_list:
        return None
    df_all = pd.concat(df_list, ignore_index=True)
    df_all['TASA'] = pd.to_numeric(df_all['TASA'], errors='coerce')
    df_all['SALDO'] = pd.to_numeric(df_all['SALDO'], errors='coerce')
    df_all['FECHA_APERTURA'] = pd.to_datetime(df_all['FECHA_APERTURA'], errors='coerce')
    df_all['AÑO'] = df_all['FECHA_APERTURA'].dt.year
    return df_all

# URLs crudas de GitHub (coloca aquí tus propios links raw)
creditos_files = [
    "BASESAH/AMBATO_CREDITOS_ACTIVAS.xlsx",
    "BASESAH/HUACHICHICO_CREDITOS_ACTIVAS.xlsx"
]
captaciones_files = [
    "BASESAH/AMBATO.xlsx",
    "BASESAH/HUACHI CHICO.xlsx"
]

df_creditos = load_creditos(creditos_files)
df_captaciones = load_captaciones(captaciones_files)

# === 2. Filtros Sidebar ===
st.sidebar.header("Filtros Créditos")
anio_creditos = st.sidebar.multiselect(
    "Seleccionar Año de Créditos",
    options=sorted(df_creditos['AÑO'].dropna().unique()) if df_creditos is not None else [],
    default=sorted(df_creditos['AÑO'].dropna().unique()) if df_creditos is not None else []
)

st.sidebar.header("Filtros Captaciones")
anio_captaciones = st.sidebar.multiselect(
    "Seleccionar Año de Captaciones",
    options=sorted(df_captaciones['AÑO'].dropna().unique()) if df_captaciones is not None else [],
    default=sorted(df_captaciones['AÑO'].dropna().unique()) if df_captaciones is not None else []
)

# Filtrar según selección
df_creditos_filtered = df_creditos[df_creditos['AÑO'].isin(anio_creditos)] if df_creditos is not None else pd.DataFrame()
df_captaciones_filtered = df_captaciones[df_captaciones['AÑO'].isin(anio_captaciones)] if df_captaciones is not None else pd.DataFrame()

# === 3. Crear pestañas ===
tab_creditos, tab_captaciones = st.tabs(["📈 Créditos", "💰 Captaciones"])
oficinas = ['AMBATO', 'HUACHI CHICO']

# Función para calcular moda (la tasa que más se repite)
def calcular_moda(series):
    series = series.dropna()
    if series.empty:
        return None
    counts = Counter(series)
    return counts.most_common(1)[0][0]

# --- Pestaña Créditos ---
with tab_creditos:
    st.header("Comparación Tasa Máxima Créditos vs Captaciones por Oficina y Año")
    # Crear lista para almacenar resultados
    max_tasas_anual = []
    
    for oficina in oficinas:
        for año in sorted(df_creditos_filtered['AÑO'].dropna().unique()):
            # Tasa máxima de créditos por oficina y año
            max_credito = df_creditos_filtered[
                (df_creditos_filtered['OFICINA'] == oficina) & (df_creditos_filtered['AÑO'] == año)
            ]['TASAINTERES'].max() if not df_creditos_filtered.empty else 0
            
            # Tasa máxima de captaciones por oficina y año
            max_captacion = df_captaciones_filtered[
                (df_captaciones_filtered['OFICINA'] == oficina) & (df_captaciones_filtered['AÑO'] == año)
            ]['TASA'].max() if not df_captaciones_filtered.empty else 0
            
            max_tasas_anual.append({
                "OFICINA": oficina,
                "AÑO": año,
                "Créditos": max_credito,
                "Captaciones": max_captacion
            })
    
    # Convertir a DataFrame
    df_max_tasas_anual = pd.DataFrame(max_tasas_anual)
    
    # Graficar con líneas por oficina
    fig_comp_anual = px.line(
        df_max_tasas_anual,
        x='AÑO',
        y='Créditos',
        color='OFICINA',
        markers=True,
        title="Tasa Máxima Créditos por Oficina y Año"
    )
    # Agregar línea de captaciones
    for oficina in oficinas:
        df_ofi = df_max_tasas_anual[df_max_tasas_anual['OFICINA'] == oficina]
        fig_comp_anual.add_scatter(
            x=df_ofi['AÑO'],
            y=df_ofi['Captaciones'],
            mode='lines+markers',
            name=f'Captaciones {oficina}'
        )
    
    st.plotly_chart(fig_comp_anual, use_container_width=True)



    
    st.markdown("---")
    for oficina in oficinas:
        st.subheader(f"Oficina: {oficina}")
        df_ofi = df_creditos_filtered[df_creditos_filtered['OFICINA']==oficina]
        if df_ofi.empty:
            st.info(f"No hay datos de créditos para {oficina}")
            continue

        # Montos colocados por año
        monto_anual = df_ofi.groupby('AÑO')['DEUDAINICIAL'].sum().reset_index()
        fig_monto = px.bar(monto_anual, x='AÑO', y='DEUDAINICIAL', text='DEUDAINICIAL',
                           title=f"Monto Total Colocado por Año - {oficina}")
        st.plotly_chart(fig_monto, use_container_width=True)

        # Tasa moda por año
        tasa_anual = df_ofi.groupby('AÑO')['TASAINTERES'].apply(calcular_moda).reset_index()
        fig_tasa = px.line(tasa_anual, x='AÑO', y='TASAINTERES', markers=True, title=f"Tasa Más Frecuente Créditos - {oficina}")
        st.plotly_chart(fig_tasa, use_container_width=True)

        # Días de mora promedio y máximo
        mora_anual = df_ofi.groupby('AÑO')['DIASATRASO'].agg(['mean','max']).reset_index()
        fig_mora = px.line(mora_anual, x='AÑO', y='mean', markers=True, title=f"Días de Mora Promedio - {oficina}")
        fig_mora.add_scatter(x=mora_anual['AÑO'], y=mora_anual['max'], mode='lines+markers', name='Días Máximos')
        st.plotly_chart(fig_mora, use_container_width=True)

# --- Pestaña Captaciones ---
with tab_captaciones:
    for oficina in oficinas:
        st.subheader(f"Oficina: {oficina}")
        df_ofi = df_captaciones_filtered[df_captaciones_filtered['OFICINA']==oficina]
        if df_ofi.empty:
            st.info(f"No hay datos de captaciones para {oficina}")
            continue

        # Saldos totales por año
        saldo_anual = df_ofi.groupby('AÑO')['SALDO'].sum().reset_index()
        fig_saldo = px.bar(saldo_anual, x='AÑO', y='SALDO', text='SALDO', title=f"Saldos Totales Captaciones por Año - {oficina}")
        st.plotly_chart(fig_saldo, use_container_width=True)

        # Tasa máxima por año para captaciones
        tasa_cap = df_ofi.groupby('AÑO')['TASA'].max().reset_index()
        fig_tasa_cap = px.line(
            tasa_cap, 
            x='AÑO', 
            y='TASA', 
            markers=True, 
            title=f"Tasa Máxima Captaciones - {oficina}"
        )
        st.plotly_chart(fig_tasa_cap, use_container_width=True)








