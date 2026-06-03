import streamlit as st
import requests
from datetime import datetime
import os

# CONFIGURACIÓN DE URLS
TOKEN_URL = "http://localhost:8002/token"
CLIENTES_URL = os.getenv("CLIENTES_URL", "http://shopnow-clientes.onrender.com/clientes")

st.set_page_config(page_title="ShopNow - Clientes", page_icon="👥", layout="wide")

# FUNCIÓN DE FORMATEO DE FECHAS
def formatear_fecha(fecha_str):
    """Convierte una fecha ISO del backend a dd/mm/aaaa, HH:MM"""
    if not fecha_str:
        return "N/A"
    try:
        fecha_obj = datetime.fromisoformat(str(fecha_str).replace('Z', '+00:00'))
        return fecha_obj.strftime("%d/%m/%Y, %H:%M")
    except ValueError:
        return str(fecha_str)

#LOGIN
def mostrar_login():

    col_izq, col_centro, col_der = st.columns([1, 1.5, 1])
    
    with col_centro:
        st.markdown("<h1 style='text-align: center;'>👥 Login Clientes</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Por favor, inicia sesión para acceder</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
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
                    st.error("No se pudo conectar con el Orquestador (Puerto 8002).")

# VISTA 1: TABLA PRINCIPAL
def mostrar_tabla_clientes(headers):
    st.title("👥 Clientes")
    
    col_btn1, col_btn2 = st.columns([1, 8])
    with col_btn1:
        if st.button("➕ Nuevo Cliente", type="primary"):
            st.session_state['page'] = 'create'
            st.rerun()
    with col_btn2:
        if st.button("🔄 Actualizar Tabla"):
            st.rerun()
        
    try:
        respuesta = requests.get(CLIENTES_URL, headers=headers)
        
        if respuesta.status_code == 200:
            clientes = respuesta.json()
            
            if clientes:
                campos = list(clientes[0].keys())
                st.session_state['campos_modelo'] = campos 
                
                anchos = [2] * len(campos) + [1.5] 
                
                cols_header = st.columns(anchos)
                for i, campo in enumerate(campos):
                    cols_header[i].write(f"**{campo.upper()}**")
                cols_header[-1].write("**ACCIÓN**")
                
                st.divider()
                
                for c in clientes:
                    cols_fila = st.columns(anchos)
                            
                    for i, campo in enumerate(campos):
                        if campo == 'activo':
                            es_activo = str(c[campo]).lower() == 'true' if isinstance(c[campo], str) else bool(c[campo])
                            estado = "Activo" if es_activo else "Inactivo"
                            cols_fila[i].write(estado)
                        elif campo in ['fecha_creacion', 'created_at', 'updated_at']:
                            fecha_bonita = formatear_fecha(c[campo])
                            cols_fila[i].write(fecha_bonita)
                        else:
                            cols_fila[i].write(str(c[campo]))
                            
                    with cols_fila[-1]:
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("📝", key=f"edit_{c['id_cliente']}", help="Editar cliente"):
                                st.session_state['cliente_edit'] = c
                                st.session_state['page'] = 'edit'
                                st.rerun()
                        with col_del:
                            if st.button("🗑️", key=f"del_{c['id_cliente']}", help="Eliminar cliente"):
                                st.session_state['cliente_del'] = c
                                st.session_state['page'] = 'delete'
                                st.rerun()
                        
                st.divider()
            else:
                st.info("No hay clientes registrados en la base de datos.")
                
        elif respuesta.status_code == 401:
            st.error("Tu sesión ha expirado o es inválida.")
            del st.session_state["token"]
            st.rerun()
        else:
            st.error(f"Error al consultar la API: Código {respuesta.status_code}")
            
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con el microservicio de Clientes (Puerto 8000). ¿Está encendido?")
# ==========================================
# VISTA 2: FORMULARIO DE EDICIÓN
# ==========================================
def mostrar_formulario_edicion(headers):
    c_edit = st.session_state['cliente_edit']
    st.title(f"Editar #{c_edit['id_cliente']}")
    
    if st.button("⬅ Regresar"):
        st.session_state['page'] = 'main'
        st.rerun()

    with st.form("form_edicion_cliente"):
        datos_actualizados = {}
        
        for key, val in c_edit.items():
            if key in ['id_cliente', 'fecha_creacion', 'created_at', 'updated_at']:
                st.text_input(key.capitalize(), value=str(val), disabled=True)
                

            elif key == 'activo':
                # Convertimos el valor actual a booleano real por seguridad
                es_activo = str(val).lower() == 'true' if isinstance(val, str) else bool(val)
                idx_actual = 0 if es_activo else 1
                
                # Usamos st.radio con 'horizontal=True' para que se vea súper elegante
                seleccion = st.radio(
                    "Estado del Cliente", 
                    ["Activo", "Inactivo"], 
                    index=idx_actual, 
                    horizontal=True
                )
                
                # Guardamos el equivalente booleano para el JSON
                datos_actualizados[key] = True if seleccion == "Activo" else False
                
            else:
                datos_actualizados[key] = st.text_input(key.capitalize(), value=str(val))
                
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            guardar = st.form_submit_button("Guardar Cambios", type="primary")
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar")
            
        if guardar:
            res_patch = requests.patch(f"{CLIENTES_URL}/{c_edit['id_cliente']}", json=datos_actualizados, headers=headers)
            if res_patch.status_code == 200:
                st.success("¡Cliente actualizado correctamente!")
                st.session_state['page'] = 'main'
                del st.session_state['cliente_edit']
                st.rerun() 
            else:
                st.error(f"Error al guardar: {res_patch.json().get('detail', res_patch.text)}")
                
        if cancelar:
            st.session_state['page'] = 'main'
            del st.session_state['cliente_edit']
            st.rerun()

# VISTA 3: CONFIRMACIÓN DE ELIMINACIÓN
def mostrar_confirmacion_eliminacion(headers):
    c_del = st.session_state['cliente_del']
    
    st.title("Confirmar")
    st.warning(f"¿Estás completamente seguro de que deseas eliminar al cliente **#{c_del['id_cliente']}**?")
    st.write("Esta acción procesará la baja en la base de datos oficial.")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sí, Eliminar", type="primary"):
            # Llamamos al método DELETE del backend
            res_del = requests.delete(f"{CLIENTES_URL}/{c_del['id_cliente']}", headers=headers)
            
            if res_del.status_code == 200:
                st.success("¡Cliente eliminado/dado de baja exitosamente!")
                st.session_state['page'] = 'main'
                del st.session_state['cliente_del']
                st.rerun()
            else:
                st.error(f"No se pudo eliminar: {res_del.json().get('detail', 'Error desconocido')}")
    with col2:
        if st.button("Cancelar y Regresar"):
            st.session_state['page'] = 'main'
            del st.session_state['cliente_del']
            st.rerun()

# ==========================================
# VISTA 4: CREACIÓN DE NUEVO CLIENTE
# ==========================================
def mostrar_formulario_creacion(headers):
    st.title("➕ Registrar Nuevo Cliente")
    
    if st.button("⬅️ Regresar al panel principal"):
        st.session_state['page'] = 'main'
        st.rerun()

    with st.form("form_creacion_cliente"):
        nuevo_cliente = {}
        
        campos = st.session_state.get('campos_modelo', ['nombre', 'correo', 'telefono', 'activo'])
        
        for campo in campos:
            if campo in ['id_cliente', 'fecha_creacion', 'created_at', 'updated_at']:
                continue
                
            elif campo == 'activo':
                # Por defecto un cliente nuevo entra como Activo
                seleccion = st.radio("Estado del Cliente", ["Activo", "Inactivo"], index=0, horizontal=True)
                nuevo_cliente[campo] = True if seleccion == "Activo" else False
                
            else:
                nuevo_cliente[campo] = st.text_input(campo.capitalize())
                
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            guardar = st.form_submit_button("Crear Cliente", type="primary")
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar")
            
        if guardar:
            res_post = requests.post(CLIENTES_URL, json=nuevo_cliente, headers=headers)
            if res_post.status_code in [200, 201]:
                st.success("¡Cliente registrado exitosamente!")
                st.session_state['page'] = 'main'
                st.rerun() 
            else:
                st.error(f"Error al crear: {res_post.json().get('detail', res_post.text)}")
                
        if cancelar:
            st.session_state['page'] = 'main'
            st.rerun()

# LÓGICA DEL ENRUTADOR (ROUTER)
def manejador_paginas():
    if 'page' not in st.session_state:
        st.session_state['page'] = 'main'

    st.sidebar.info("Sesión iniciada como: Administrador")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
        
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    if st.session_state['page'] == 'main':
        mostrar_tabla_clientes(headers)
    elif st.session_state['page'] == 'edit':
        mostrar_formulario_edicion(headers)
    elif st.session_state['page'] == 'delete':
        mostrar_confirmacion_eliminacion(headers)
    elif st.session_state['page'] == 'create':
        mostrar_formulario_creacion(headers)

# FLUJO PRINCIPAL
if "token" not in st.session_state:
    mostrar_login()
else:
    manejador_paginas()