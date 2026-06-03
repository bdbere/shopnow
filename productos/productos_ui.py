import streamlit as st
import requests
from datetime import datetime

# ==========================================
# CONFIGURACIÓN DE URLS
# ==========================================
TOKEN_URL = "http://localhost:8002/token"
PRODUCTOS_URL = "http://localhost:8001/v2/productos"
INVENTARIO_URL = "http://localhost:8003/inventario"

st.set_page_config(page_title="ShopNow - Productos", page_icon="📦", layout="wide")

# ==========================================
# FUNCIÓN AYUDANTE: FORMATEAR FECHAS
# ==========================================
def formatear_fecha(fecha_str):
    if not fecha_str or str(fecha_str).lower() == "none" or "legacy" in str(fecha_str).lower():
        return str(fecha_str)
    try:
        fecha_obj = datetime.fromisoformat(str(fecha_str).replace('Z', '+00:00'))
        return fecha_obj.strftime("%d/%m/%Y, %H:%M")
    except ValueError:
        return str(fecha_str)

# LOGIN
def mostrar_login():
    # Creamos las 3 columnas para centrar y reducir el ancho del formulario
    col_izq, col_centro, col_der = st.columns([1, 1.5, 1])
    
    with col_centro:
        # Usamos HTML para forzar el centrado perfecto de los textos
        st.markdown("<h1 style='text-align: center;'>📦 Login Productos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Por favor, inicia sesión para acceder al catálogo de productos.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            
            # Hacemos que el botón abarque el ancho total de nuestra columna central
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

# ==========================================
# VISTA 1: TABLA PRINCIPAL (PRODUCTOS + INVENTARIO)
# ==========================================
def mostrar_tabla_productos(headers):
    st.title("📦 Productos (V2)")
    
    col_btn1, col_btn2 = st.columns([1, 8])
    with col_btn1:
        if st.button("➕ Nuevo Producto", type="primary"):
            st.session_state['page'] = 'create'
            st.rerun()
    with col_btn2:
        if st.button("🔄 Actualizar Tabla"):
            st.rerun()
            
    try:
        respuesta_prod = requests.get(PRODUCTOS_URL, headers=headers)
        
        if respuesta_prod.status_code == 200:
            productos = respuesta_prod.json()
            
            if productos:
                # --- INTEGRACIÓN DE INVENTARIO ---
                try:
                    respuesta_inv = requests.get(INVENTARIO_URL, headers=headers)
                    if respuesta_inv.status_code == 200:
                        inventario = respuesta_inv.json()
                        mapa_inventario = {item['id_producto']: item['cantidad'] for item in inventario}
                        for p in productos:
                            p['cantidad'] = mapa_inventario.get(p['id_producto'], 0)
                    else:
                        st.warning("No se pudo cargar el stock.")
                except requests.exceptions.ConnectionError:
                    st.warning("Servicio de Inventario (8003) no disponible.")
                    for p in productos:
                        p['cantidad'] = "N/A"
                # ---------------------------------

                campos = list(productos[0].keys())
                st.session_state['campos_modelo'] = campos 
                
                anchos = [2] * len(campos) + [1.5] 
                
                cols_header = st.columns(anchos)
                for i, campo in enumerate(campos):
                    cols_header[i].write(f"**{campo.upper()}**")
                cols_header[-1].write("**ACCIÓN**")
                
                st.divider()
                
                for p in productos:
                    cols_fila = st.columns(anchos)
                            
                    for i, campo in enumerate(campos):
                        if campo == 'activo':
                            es_activo = str(p[campo]).lower() == 'true' if isinstance(p[campo], str) else bool(p[campo])
                            estado = "Activo" if es_activo else "Inactivo"
                            cols_fila[i].write(estado)
                        elif campo in ['fecha_creacion', 'created_at', 'updated_at']:
                            fecha_bonita = formatear_fecha(p[campo])
                            cols_fila[i].write(fecha_bonita)
                        elif campo == 'cantidad':
                            cols_fila[i].write(f"**{p[campo]}** unid.")
                        else:
                            cols_fila[i].write(str(p[campo]))
                            
                    with cols_fila[-1]:
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("📝", key=f"edit_{p['id_producto']}", help="Editar producto"):
                                st.session_state['producto_edit'] = p
                                st.session_state['page'] = 'edit'
                                st.rerun()
                        with col_del:
                            if st.button("🗑️", key=f"del_{p['id_producto']}", help="Eliminar producto"):
                                st.session_state['producto_del'] = p
                                st.session_state['page'] = 'delete'
                                st.rerun()
                        
                st.divider()
            else:
                st.info("No hay productos registrados en la base de datos.")
                
        elif respuesta_prod.status_code == 401:
            st.error("Tu sesión ha expirado o es inválida.")
            del st.session_state["token"]
            st.rerun()
        else:
            st.error(f"Error al consultar la API de Productos: Código {respuesta_prod.status_code}")
            
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con el microservicio de Productos (Puerto 8001). ¿Está encendido?")

# ==========================================
# VISTA 2: FORMULARIO DE EDICIÓN
# ==========================================
def mostrar_formulario_edicion(headers):
    p_edit = st.session_state['producto_edit']
    st.title(f"Editar Producto #{p_edit['id_producto']}")
    
    if st.button("⬅ Regresar al catálogo"):
        st.session_state['page'] = 'main'
        st.rerun()

    datos_actualizados = {}
    
    st.subheader("📝 Datos Generales")
    for key, val in p_edit.items():
        if key in ['id_producto', 'fecha_creacion', 'created_at', 'updated_at']:
            valor_mostrar = formatear_fecha(val) if 'fecha' in key or 'at' in key else val
            st.text_input(key.capitalize(), value=str(valor_mostrar), disabled=True)
            
        elif key == 'activo':
            es_activo = str(val).lower() == 'true' if isinstance(val, str) else bool(val)
            idx_actual = 0 if es_activo else 1
            seleccion = st.radio("Estado del Producto", ["Activo", "Inactivo"], index=idx_actual, horizontal=True)
            datos_actualizados[key] = True if seleccion == "Activo" else False
            
        elif key == 'cantidad':
            pass 
        else:
            datos_actualizados[key] = st.text_input(key.capitalize(), value=str(val))
            
    st.divider()
    st.subheader("Ajuste de Inventario")
    cantidad_actual = p_edit.get('cantidad', 0)
    if cantidad_actual == "N/A": cantidad_actual = 0
    
    st.info(f"Existencia actual: **{cantidad_actual}** unidades")
    
    accion_inv = st.radio(
        "¿Deseas modificar las existencias?", 
        ["Sin cambios", "Incrementar", "Descontar"], 
        horizontal=True
    )
    
    valor_ajuste = 0
    if accion_inv != "Sin cambios":
        valor_ajuste = st.number_input(f"Unidades a {accion_inv.lower()}:", min_value=1, step=1, value=1)
    # -------------------------------------------
    
    st.divider()
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        guardar = st.button("Guardar Todos los Cambios", type="primary")
    with col_btn2:
        cancelar = st.button("Cancelar")
        
    if guardar:
        errores = False
        
        res_patch = requests.patch(f"{PRODUCTOS_URL}/{p_edit['id_producto']}", json=datos_actualizados, headers=headers)
        if res_patch.status_code != 200:
            st.error(f"Error al actualizar producto: {res_patch.json().get('detail', res_patch.text)}")
            errores = True
            
        if accion_inv != "Sin cambios" and valor_ajuste > 0:
            nueva_cantidad = int(cantidad_actual)
            if accion_inv == "Incrementar":
                nueva_cantidad += valor_ajuste
            elif accion_inv == "Descontar":
                nueva_cantidad -= valor_ajuste
                if nueva_cantidad < 0: nueva_cantidad = 0 
            
            res_inv = requests.patch(f"{INVENTARIO_URL}/{p_edit['id_producto']}", json={"cantidad": nueva_cantidad}, headers=headers)
            if res_inv.status_code not in [200, 201]:
                st.error(f"Error al actualizar inventario: {res_inv.json().get('detail', res_inv.text)}")
                errores = True

        if not errores:
            st.success("¡Producto e Inventario actualizados correctamente!")
            st.session_state['page'] = 'main'
            del st.session_state['producto_edit']
            st.rerun() 
            
    if cancelar:
        st.session_state['page'] = 'main'
        del st.session_state['producto_edit']
        st.rerun()

# ==========================================
# VISTA 3: CONFIRMACIÓN DE ELIMINACIÓN
# ==========================================
def mostrar_confirmacion_eliminacion(headers):
    p_del = st.session_state['producto_del']
    
    st.title("Confirmar Acción")
    st.warning(f"¿Estás completamente seguro de que deseas eliminar el producto **#{p_del['id_producto']}**?")
    
    if st.button("⬅ Cancelar y Regresar"):
        st.session_state['page'] = 'main'
        del st.session_state['producto_del']
        st.rerun()

    st.divider()
    
    if st.button("Sí, Eliminar Definitivamente", type="primary"):
        res_del = requests.delete(f"{PRODUCTOS_URL}/{p_del['id_producto']}", headers=headers)
        if res_del.status_code == 200:
            st.success("¡Producto eliminado exitosamente!")
            st.session_state['page'] = 'main'
            del st.session_state['producto_del']
            st.rerun()
        else:
            st.error(f"No se pudo eliminar: {res_del.json().get('detail', 'Error desconocido')}")

# ==========================================
# VISTA 4: CREACIÓN DE NUEVO PRODUCTO
# ==========================================
def mostrar_formulario_creacion(headers):
    st.title("➕ Registrar Nuevo Producto")
    
    if st.button("⬅ Regresar al catálogo"):
        st.session_state['page'] = 'main'
        st.rerun()

    with st.form("form_creacion_producto"):
        nuevo_producto = {}
        campos = st.session_state.get('campos_modelo', ['descripcion', 'precio', 'activo', 'cantidad'])
        
        cantidad_inicial = 0 
        
        for campo in campos:
            if campo in ['id_producto', 'fecha_creacion', 'created_at', 'updated_at']:
                continue
            elif campo == 'activo':
                seleccion = st.radio("Estado del Producto", ["Activo", "Inactivo"], index=0, horizontal=True)
                nuevo_producto[campo] = True if seleccion == "Activo" else False
            elif campo == 'cantidad':
                st.write("---")
                st.subheader("Inventario Inicial")
                cantidad_inicial = st.number_input("Existencias iniciales del producto:", min_value=0, step=1, value=0)
            else:
                nuevo_producto[campo] = st.text_input(campo.capitalize())
                
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            guardar = st.form_submit_button("Crear Producto", type="primary")
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar")
            
        if guardar:
            errores = False
            res_post = requests.post(PRODUCTOS_URL, json=nuevo_producto, headers=headers)
            
            if res_post.status_code in [200, 201]:
                respuesta_json = res_post.json()
                id_nuevo_prod = respuesta_json.get('id_producto') or respuesta_json.get('id')
                
                if id_nuevo_prod is not None:
                    payload_inv = {"cantidad": cantidad_inicial}
                    res_inv = requests.patch(f"{INVENTARIO_URL}/{id_nuevo_prod}", json=payload_inv, headers=headers)
                    
                    if res_inv.status_code not in [200, 201]:
                        st.error(f"Producto creado, pero falló el inventario: {res_inv.json().get('detail', res_inv.text)}")
                        errores = True
                else:
                    st.warning("Producto creado, pero el backend no devolvió su ID. El inventario se quedó en 0.")
            else:
                st.error(f"Error al crear producto: {res_post.json().get('detail', res_post.text)}")
                errores = True
                
            if not errores:
                st.success("¡Producto e Inventario registrados exitosamente!")
                st.session_state['page'] = 'main'
                st.rerun() 
                
        if cancelar:
            st.session_state['page'] = 'main'
            st.rerun()
# ==========================================
# LÓGICA DEL ENRUTADOR (ROUTER)
# ==========================================
def manejador_paginas():
    if 'page' not in st.session_state:
        st.session_state['page'] = 'main'

    st.sidebar.info("Sesión iniciada como: Administrador")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear() 
        st.rerun()
        
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    if st.session_state['page'] == 'main':
        mostrar_tabla_productos(headers)
    elif st.session_state['page'] == 'edit':
        mostrar_formulario_edicion(headers)
    elif st.session_state['page'] == 'delete':
        mostrar_confirmacion_eliminacion(headers)
    elif st.session_state['page'] == 'create':
        mostrar_formulario_creacion(headers)

# ==========================================
# FLUJO DE INICIO
# ==========================================
if "token" not in st.session_state:
    mostrar_login()
else:
    manejador_paginas()