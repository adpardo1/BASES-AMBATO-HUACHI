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
        # El archivo fue subido por el usuario, así que se usa directamente.
        df = pd.read_csv('BASESAH/proyeccion.csv')
    except FileNotFoundError:
        st.error("Error: El archivo 'proyeccion.csv' no se encuentra en el mismo directorio.")
        return None
    
    # Preprocesa los nombres de las columnas y los datos de la columna 'NOMBRE_CTA_CONTABLE'
    df.columns = df.columns.str.strip().str.replace(' ', '_').str.upper()
    df['FECHA_DATOS'] = pd.to_datetime(df['FECHA_DATOS'])
    df['NOMBRE_CTA_CONTABLE'] = df['NOMBRE_CTA_CONTABLE'].str.strip().str.replace(' ', '_').str.upper()
    
    # --- FILTRADO ADICIONAL SOLICITADO ---
    df['CUENTA_CONTABLE'] = df['CUENTA_CONTABLE'].astype(str)
    # Aquí se filtra por las cuentas contables relevantes
    df_filtered_by_account = df[df['CUENTA_CONTABLE'].str.startswith(('4', '5', '14', '21'))].copy()
    df_final = df_filtered_by_account[df_filtered_by_account['NOMBRE_OFICINA'].str.upper() == 'CONSOLIDADO'].copy()
    df_final['SALDO'] = pd.to_numeric(df_final['SALDO'], errors='coerce').fillna(0)
    
    return df_final

# --- Función para generar las gráficas ---
def plot_projections(df_pivot, df_proyeccion, cuenta):
    """Genera y muestra los gráficos de datos históricos y proyecciones."""
    fig = go.Figure()
    
    # Comprobar si los datos históricos existen
    if cuenta in df_pivot.columns:
        fig.add_trace(go.Scatter(x=df_pivot.index, y=df_pivot[cuenta], mode='lines+markers', name='Datos Históricos'))
    else:
        st.warning(f"No se encontraron datos históricos para la cuenta '{cuenta}'.")
        
    # Siempre se mostrará la proyección si existe
    fig.add_trace(go.Scatter(x=df_proyeccion.index, y=df_proyeccion[cuenta], mode='lines', name='Proyección', line=dict(dash='dash')))
    
    fig.update_layout(title=f'Proyección de {cuenta.replace("_", " ")}', xaxis_title='Fecha', yaxis_title='Saldo', template='plotly_white')
    st.plotly_chart(fig, use_container_width=True)

# --- Contenido de la pestaña 2 ---
def show_growth_model(df_filtered):
    """Muestra el modelo de crecimiento y las proyecciones."""
    PROJECTION_PERIOD_MONTHS = 60
    
    # Se ajustan los nombres de las cuentas a proyectar según el archivo CSV
    cuentas_a_proyectar = ['CARTERA_DE_CREDITOS', 'OBLIGACIONES_CON_EL_PUBLICO']
    
    df_pivot = df_filtered[df_filtered['NOMBRE_CTA_CONTABLE'].isin(cuentas_a_proyectar)].groupby(['FECHA_DATOS', 'NOMBRE_CTA_CONTABLE'])['SALDO'].sum().unstack(fill_value=0)

    # --- VERIFICACIÓN DE COLUMNAS ANTES DE CALCULAR ---
    if 'CARTERA_DE_CREDITOS' in df_pivot.columns and 'OBLIGACIONES_CON_EL_PUBLICO' in df_pivot.columns:
        # Se calcula la utilidad con el nombre de la cuenta corregido
        df_pivot['UTILIDADES'] = df_pivot['CARTERA_DE_CREDITOS'] - df_pivot['OBLIGACIONES_CON_EL_PUBLICO']
    else:
        st.error("No se encontraron las cuentas 'CARTERA_DE_CREDITOS' y/o 'OBLIGACIONES_CON_EL_PUBLICO' en los datos filtrados.")
        st.info("Por favor, revisa el archivo 'proyeccion.csv' para asegurar que los nombres de las cuentas coinciden con el código.")
        return
        
    if len(df_pivot) < 12:
        st.error("No hay suficientes datos (se necesitan al menos 12 meses).")
        return

    cartera_proyeccion = []
    obligaciones_proyeccion = []
    
    ultimo_valor_cartera = df_pivot['CARTERA_DE_CREDITOS'].iloc[-1]
    ultimo_valor_obligaciones = df_pivot['OBLIGACIONES_CON_EL_PUBLICO'].iloc[-1]
    
    # --- Bucle para generar las proyecciones de forma incremental con valles sutiles ---
    for i in range(PROJECTION_PERIOD_MONTHS):
        
        # --- Lógica para valles y picos en la cartera ---
        if i < 12:  # Julio 2025 a Junio 2026
            tasa_ajuste_cartera_anual = 0.10
        elif i >= 12 and i < 24:  # Julio 2026 a Junio 2027
            tasa_ajuste_cartera_anual = -0.005
        elif i >= 24 and i < 36: # Julio 2027 a Junio 2028
            tasa_ajuste_cartera_anual = 0.005
        elif i >= 36 and i < 48: # Julio 2028 a Junio 2029
            tasa_ajuste_cartera_anual = -0.01
        else:  # Julio 2029 en adelante
            tasa_ajuste_cartera_anual = -0.03
        
        # Tasa de crecimiento para obligaciones controlada
        tasa_ajuste_obligaciones_anual = 0.07
        
        # Convertir tasas anuales a tasas mensuales
        tasa_mensual_cartera = (1 + tasa_ajuste_cartera_anual)**(1/12) - 1
        tasa_mensual_obligaciones = (1 + tasa_ajuste_obligaciones_anual)**(1/12) - 1

        # Actualizar el valor proyectado, basándose en el valor del mes anterior
        ultimo_valor_cartera = ultimo_valor_cartera * (1 + tasa_mensual_cartera)
        ultimo_valor_obligaciones = ultimo_valor_obligaciones * (1 + tasa_mensual_obligaciones)

        cartera_proyeccion.append(ultimo_valor_cartera)
        obligaciones_proyeccion.append(ultimo_valor_obligaciones)

    utilidades_proyeccion = [c - d for c, d in zip(cartera_proyeccion, obligaciones_proyeccion)]
    
    proyecciones = {
        'CARTERA_DE_CREDITOS': cartera_proyeccion,
        'OBLIGACIONES_CON_EL_PUBLICO': obligaciones_proyeccion,
        'UTILIDADES': utilidades_proyeccion
    }

    df_proyeccion = pd.DataFrame(proyecciones, index=pd.date_range(start=df_pivot.index[-1] + pd.DateOffset(months=1), periods=PROJECTION_PERIOD_MONTHS, freq='M'))
    
    # Se ajusta el título para reflejar el cambio
    st.header("Modelo de Crecimiento (Utilidades: Cartera - Obligaciones)")
    for cuenta in proyecciones.keys():
        plot_projections(df_pivot, df_proyeccion, cuenta)
        
# --- Lógica principal de la aplicación ---
df = load_and_preprocess_data()
if df is not None:
    show_growth_model(df)
