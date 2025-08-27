import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import statsmodels.api as sm

# --- Funciones de Caching y Preprocesamiento ---
@st.cache_data
def load_and_preprocess_data():
    """Carga y preprocesa el archivo de datos."""
    try:
        df = pd.read_csv('BASESAH/proyeccion.csv')
    except FileNotFoundError:
        st.error("Error: El archivo 'proyeccion.csv' no se encuentra en el mismo directorio.")
        return None
    
    df.columns = df.columns.str.strip().str.replace(' ', '_').str.upper()
    df['FECHA_DATOS'] = pd.to_datetime(df['FECHA_DATOS'])
    df['NOMBRE_CTA_CONTABLE'] = df['NOMBRE_CTA_CONTABLE'].str.strip().str.replace(' ', '_').str.upper()
    
    # --- FILTRADO ADICIONAL SOLICITADO ---
    df['CUENTA_CONTABLE'] = df['CUENTA_CONTABLE'].astype(str)
    df_filtered_by_account = df[df['CUENTA_CONTABLE'].str.startswith(('4', '5', '14', '2103'))].copy()
    df_final = df_filtered_by_account[df_filtered_by_account['NOMBRE_OFICINA'].str.upper() == 'CONSOLIDADO'].copy()
    df_final['SALDO'] = pd.to_numeric(df_final['SALDO'], errors='coerce').fillna(0)
    
    return df_final

# --- Función para generar las gráficas ---
def plot_projections(df_pivot, df_proyeccion, cuenta):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_pivot.index, y=df_pivot[cuenta], mode='lines+markers', name='Datos Históricos'))
    fig.add_trace(go.Scatter(x=df_proyeccion.index, y=df_proyeccion[cuenta], mode='lines', name='Proyección', line=dict(dash='dash')))
    fig.update_layout(title=f'Proyección de {cuenta.replace("_", " ")}', xaxis_title='Fecha', yaxis_title='Saldo', template='plotly_white')
    st.plotly_chart(fig, use_container_width=True)

# --- Contenido de la pestaña 2 ---
def show_growth_model(df_filtered):
    PROJECTION_PERIOD_MONTHS = 60
    
    # Normaliza nombres de cuentas que queremos proyectar
    cuentas_a_proyectar = ['CARTERA_DE_CREDITOS', 'DEPOSITOS_A_PLAZO']
    
    # Depuración: muestra los nombres reales que hay en los datos
    st.write("Nombres únicos de NOMBRE_CTA_CONTABLE en el CSV:", df_filtered['NOMBRE_CTA_CONTABLE'].unique())
    
    df_pivot = df_filtered[df_filtered['NOMBRE_CTA_CONTABLE'].isin(cuentas_a_proyectar)] \
        .groupby(['FECHA_DATOS', 'NOMBRE_CTA_CONTABLE'])['SALDO'].sum() \
        .unstack(fill_value=0)

    # Validación: asegúrate que las columnas existan
    for col in cuentas_a_proyectar:
        if col not in df_pivot.columns:
            st.error(f"No se encontró la cuenta '{col}' en los datos. Revisa el CSV y la normalización de nombres.")
            return
    
    df_pivot['UTILIDADES'] = df_pivot['CARTERA_DE_CREDITOS'] - df_pivot['DEPOSITOS_A_PLAZO']
    
    if len(df_pivot) < 12:
        st.error("No hay suficientes datos (se necesitan al menos 12 meses).")
        return

    cartera_proyeccion = []
    depositos_proyeccion = []
    
    ultimo_valor_cartera = df_pivot['CARTERA_DE_CREDITOS'].iloc[-1]
    ultimo_valor_depositos = df_pivot['DEPOSITOS_A_PLAZO'].iloc[-1]
    
    # --- Bucle para generar las proyecciones de forma incremental con valles sutiles ---
    for i in range(PROJECTION_PERIOD_MONTHS):
        
        # Lógica de valles y picos
        if i < 12:
            tasa_ajuste_cartera_anual = 0.10
        elif i < 24:
            tasa_ajuste_cartera_anual = -0.005
        elif i < 36:
            tasa_ajuste_cartera_anual = 0.005
        elif i < 48:
            tasa_ajuste_cartera_anual = -0.01
        else:
            tasa_ajuste_cartera_anual = -0.03
        
        tasa_ajuste_depositos_anual = 0.07
        
        tasa_mensual_cartera = (1 + tasa_ajuste_cartera_anual)**(1/12) - 1
        tasa_mensual_depositos = (1 + tasa_ajuste_depositos_anual)**(1/12) - 1

        ultimo_valor_cartera *= (1 + tasa_mensual_cartera)
        ultimo_valor_depositos *= (1 + tasa_mensual_depositos)

        cartera_proyeccion.append(ultimo_valor_cartera)
        depositos_proyeccion.append(ultimo_valor_depositos)

    utilidades_proyeccion = [c - d for c, d in zip(cartera_proyeccion, depositos_proyeccion)]
    
    proyecciones = {
        'CARTERA_DE_CREDITOS': cartera_proyeccion,
        'DEPOSITOS_A_PLAZO': depositos_proyeccion,
        'UTILIDADES': utilidades_proyeccion
    }

    df_proyeccion = pd.DataFrame(
        proyecciones,
        index=pd.date_range(
            start=df_pivot.index[-1] + pd.DateOffset(months=1),
            periods=PROJECTION_PERIOD_MONTHS,
            freq='M'
        )
    )
    
    st.header("Modelo de Crecimiento (Utilidades: Cartera - Obligaciones)")
    for cuenta in proyecciones.keys():
        plot_projections(df_pivot, df_proyeccion, cuenta)

# --- Lógica principal de la aplicación ---
df = load_and_preprocess_data()
if df is not None:
    show_growth_model(df)
