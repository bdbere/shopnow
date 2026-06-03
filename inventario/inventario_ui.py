import streamlit as st
import requests
import os

# ==========================================
# CONFIGURACIÓN DE URLS
# ==========================================
# El Orquestador (8002) da los tokens, Inventario (8003) da los datos
TOKEN_URL = "http://localhost:8002/token"
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://shopnow-inventario.onrender.com/inventario")

# Configuración básica de la página
st.set_page_config(page_title="ShopNow - Inventario", page_icon="📋", layout="centered")

# ==========================================
# FUNCIÓN DE LOGIN
# ==========================================
def mostrar_login():
    st.title("📋 Login Inventario", text_alignment= "center")
    st.write("Por favor, inicia sesión para acceder al control de existencias.")
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión")
        
        if submit:
            credenciales = {"username": usuario, "password": password}
            
            try:
                respuesta = requests.post(TOKEN_URL, data=credenciales)
                
                if respuesta.status_code == 200:
                    st.session_state["token"] = respuesta.json()["access_token"]
                    st.success("¡Acceso concedido! Redirigiendo...")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar con el Orquestador (Puerto 8002). ¿Está encendido?")

# ==========================================
# FUNCIÓN PRINCIPAL (CONTROL DE INVENTARIO)
# ==========================================
def mostrar_panel_inventario():
    st.title("📋 Inventario")
    if st.button("🔄 Actualizar Tabla"):
           st.rerun()
    
    # Botón de cerrar sesión en la barra lateral
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["token"]
        st.rerun()
        
    st.sidebar.info("Sesión iniciada como: Administrador")
    
    # 1. Preparar el Token en los Headers de la petición
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    # 2. Consumir la API de Inventario
    try:
        respuesta = requests.get(INVENTARIO_URL, headers=headers)
        
        if respuesta.status_code == 200:
            inventario = respuesta.json()
            if inventario:
                st.dataframe(inventario, use_container_width=True)
            else:
                st.info("No hay registros de stock en la base de datos.")
                
        elif respuesta.status_code == 401:
            st.error("Tu sesión ha expirado o es inválida.")
            del st.session_state["token"]
            st.rerun()
        else:
            st.error(f"Error al consultar la API: Código {respuesta.status_code}")
            
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con el microservicio de Inventario (Puerto 8003). ¿Está encendido?")

# ==========================================
# LÓGICA DE NAVEGACIÓN
# ==========================================
if "token" not in st.session_state:
    mostrar_login()
else:
    mostrar_panel_inventario()