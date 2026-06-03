import streamlit as st
import requests
from datetime import datetime
import os

# ==========================================
# CONFIGURACIÓN DE URLS (Ecosistema SOA)
# ==========================================
TOKEN_URL = "http://localhost:8002/token"
PEDIDOS_URL = os.getenv("PEDIDOS_URL", "http://shopnow-pedidos.onrender.com/pedidos")
CLIENTES_URL = os.getenv("CLIENTES_URL", "http://shopnow-clientes.onrender.com/clientes")
PRODUCTOS_URL = os.getenv("PRODUCTOS_URL", "http://shopnow-productos.onrender.com/v2/productos")
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://shopnow-inventario.onrender.com/inventario")

st.set_page_config(page_title="ShopNow - Pedidos", page_icon="🛒", layout="wide")

# ==========================================
# FUNCIÓN AYUDANTE: FORMATEAR FECHAS
# ==========================================
def formatear_fecha(fecha_str):
    if not fecha_str or str(fecha_str).lower() == "none":
        return "N/A"
    try:
        fecha_obj = datetime.fromisoformat(str(fecha_str).replace('Z', '+00:00'))
        return fecha_obj.strftime("%d/%m/%Y, %H:%M")
    except ValueError:
        return str(fecha_str)

# ==========================================
# MODAL 1: DETALLES COMPLETOS DE UN PEDIDO
# ==========================================
@st.dialog("🔍 Detalles Completos del Pedido")
def ver_detalles_pedido(pedido, headers):
    st.write(f"### Pedido Oficial #{pedido['id_pedido']}")
    st.caption(f"Fecha de Registro: {formatear_fecha(pedido.get('created_at'))}")
    st.divider()
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.markdown("#### 👥 Datos del Cliente")
        try:
            res_cliente = requests.get(f"{CLIENTES_URL}/{pedido['id_cliente']}", headers=headers)
            if res_cliente.status_code == 200:
                c = res_cliente.json()
                st.write(f"**Nombre:** {c.get('nombre', 'N/A')}")
                st.write(f"**Email:** {c.get('correo', 'N/A')}")
                st.write(f"**Teléfono:** {c.get('telefono', 'N/A')}")
                estado_c = "🟢 Activo" if str(c.get('activo')).lower() == 'true' else "🔴 Inactivo"
                st.write(f"**Estatus:** {estado_c}")
            else:
                st.error(f"No se pudo obtener el perfil del cliente (Código {res_cliente.status_code})")
        except requests.exceptions.ConnectionError:
            st.error("❌ Microservicio de Clientes (8000) fuera de línea.")

    with col_der:
        st.markdown("#### 📦 Información del Producto")
        try:
            res_producto = requests.get(f"{PRODUCTOS_URL}/{pedido['id_producto']}", headers=headers)
            if res_producto.status_code == 200:
                p = res_producto.json()
                st.write(f"**Descripción:** {p.get('descripcion', 'N/A')}")
                st.write(f"**Precio Unitario:** ${p.get('precio', p.get('costo_unitario', 0)):,.2f}")
                
                precio_factura = float(p.get('precio', p.get('costo_unitario', 0)))
                total_compra = precio_factura * int(pedido['cantidad'])
                
                st.write(f"**Cantidad Solicitada:** {pedido['cantidad']} piezas")
                st.markdown(f"### Total: :green[${total_compra:,.2f}]")
            else:
                st.error(f"No se pudo consultar el catálogo (Código {res_producto.status_code})")
        except requests.exceptions.ConnectionError:
            st.error("❌ Microservicio de Productos (8001) fuera de línea.")

# ==========================================
# MODAL 2: SELECCIONAR CLIENTE ACTIVO
# ==========================================
@st.dialog("👥 Seleccionar Cliente Activo")
def modal_seleccionar_cliente(headers):
    st.write("Elige un cliente de la lista de usuarios activos en la plataforma:")
    try:
        respuesta = requests.get(CLIENTES_URL, headers=headers)
        if respuesta.status_code == 200:
            clientes = respuesta.json()
            activos = [c for c in clientes if str(c.get('activo')).lower() == 'true' or c.get('activo') is True]
            
            if activos:
                col_id, col_nom, col_acc = st.columns([1, 3, 2])
                col_id.write("**ID**")
                col_nom.write("**Nombre**")
                col_acc.write("**Acción**")
                st.divider()
                
                for c in activos:
                    col_id, col_nom, col_acc = st.columns([1, 3, 2])
                    col_id.write(str(c['id_cliente']))
                    col_nom.write(c['nombre'])
                    with col_acc:
                        if st.button("✅ Seleccionar", key=f"sel_cli_{c['id_cliente']}"):
                            st.session_state['selected_client'] = c
                            st.rerun()
            else:
                st.info("No hay clientes activos registrados en el padrón.")
        else:
            st.error(f"Error al obtener clientes: Código {respuesta.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con el microservicio de Clientes (8000).")

# ==========================================
# MODAL 3: SELECCIONAR PRODUCTO (CON FILTRO VISUAL DE STOCK)
# ==========================================
@st.dialog("📦 Seleccionar Producto del Catálogo")
def modal_seleccionar_producto(headers):
    st.write("Elige un artículo. Solo los productos con existencias están disponibles:")
    try:
        # Hacemos las dos consultas de golpe para armar el panel
        res_prod = requests.get(PRODUCTOS_URL, headers=headers)
        res_inv = requests.get(INVENTARIO_URL, headers=headers)
        
        if res_prod.status_code == 200:
            productos = res_prod.json()
            inventario = res_inv.json() if res_inv.status_code == 200 else []
            
            # Armamos un diccionario súper rápido para buscar el stock por id_producto
            mapa_stock = {item['id_producto']: item['cantidad'] for item in inventario}
            
            if productos:
                # Agregamos la columna Stock al modal
                col_id, col_des, col_pre, col_stk, col_acc = st.columns([1, 3, 1.5, 1.5, 2])
                col_id.write("**ID**")
                col_des.write("**Descripción**")
                col_pre.write("**Precio**")
                col_stk.write("**Stock**")
                col_acc.write("**Acción**")
                st.divider()
                
                for p in productos:
                    stock_actual = int(mapa_stock.get(p['id_producto'], 0))
                    hay_stock = stock_actual > 0
                    
                    col_id, col_des, col_pre, col_stk, col_acc = st.columns([1, 3, 1.5, 1.5, 2])
                    precio_val = p.get('precio') or p.get('costo_unitario') or 0
                    
                    # --- LÓGICA VISUAL: ACTIVO VS OSCURECIDO ---
                    if hay_stock:
                        col_id.write(str(p['id_producto']))
                        col_des.write(p['descripcion'])
                        col_pre.write(f"${float(precio_val):,.2f}")
                        col_stk.write(f"📦 {stock_actual}")
                    else:
                        # Si no hay stock, usamos .caption para que se vea gris y texto tachado (~~texto~~)
                        col_id.caption(str(p['id_producto']))
                        col_des.caption(f"~~{p['descripcion']}~~")
                        col_pre.caption(f"~~${float(precio_val):,.2f}~~")
                        col_stk.caption("🚫 0")
                    
                    with col_acc:
                        if hay_stock:
                            # Botón verde normal
                            if st.button("✅ Seleccionar", key=f"sel_prod_{p['id_producto']}"):
                                st.session_state['selected_product'] = p
                                st.session_state['selected_product_stock'] = stock_actual
                                st.rerun()
                        else:
                            # Botón inactivo que lanza el error que pediste
                            if st.button("❌ Agotado", key=f"sel_prod_{p['id_producto']}"):
                                st.error("⚠️ No hay stock disponible de este producto. Por favor, selecciona otro.")
            else:
                st.info("No hay productos en el catálogo.")
        else:
            st.error(f"Error al obtener productos: Código {res_prod.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con los microservicios (Puertos 8001 / 8003).")

# LOGIN
def mostrar_login():
    # Creamos las 3 columnas para centrar y reducir el ancho del formulario
    col_izq, col_centro, col_der = st.columns([1, 1.5, 1])
    
    with col_centro:
        # Usamos HTML para forzar el centrado perfecto del título y la descripción
        st.markdown("<h1 style='text-align: center;'>🛒 Login Pedidos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Por favor, inicia sesión para acceder al centro de mando de ventas.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            
            # El botón abarca el ancho total de la columna central
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
# FUNCIÓN PRINCIPAL (ORQUESTADOR UI)
# ==========================================
def mostrar_panel_pedidos():
    st.title("🛒 Centro de Orquestación de Pedidos")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
        
    st.sidebar.info("Sesión iniciada como: Administrador Central")
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    tab1, tab2, tab3 = st.tabs(["📋 Historial de Pedidos", "➕ Nuevo Pedido", "❌ Cancelar Pedido"])
    
    # ---------------------------------------------------
    # PESTAÑA 1: HISTORIAL DE PEDIDOS
    # ---------------------------------------------------
    with tab1:
        col_tit, col_btn = st.columns([8, 2])
        with col_tit:
            st.subheader("Pedidos Registrados")
        with col_btn:
            if st.button("🔄 Actualizar Tabla"):
                st.rerun()
            
        try:
            respuesta = requests.get(PEDIDOS_URL, headers=headers)
            if respuesta.status_code == 200:
                pedidos = respuesta.json()
                if pedidos:
                    campos = list(pedidos[0].keys())
                    
                    if 'sort_col' not in st.session_state:
                        st.session_state['sort_col'] = 'id_pedido' 
                    if 'sort_reverse' not in st.session_state:
                        st.session_state['sort_reverse'] = True 
                        
                    llave_real = st.session_state['sort_col']
                    es_reversa = st.session_state['sort_reverse']
                    
                    def obtener_valor(x):
                        valor = x.get(llave_real)
                        if valor is None:
                            return "" if llave_real in ['fecha_creacion', 'created_at'] else 0
                        return valor

                    pedidos_ordenados = sorted(pedidos, key=obtener_valor, reverse=es_reversa)

                    anchos = [2] * len(campos) + [1.5]
                    cols_header = st.columns(anchos)
                    
                    for i, campo in enumerate(campos):
                        flecha = ""
                        if st.session_state['sort_col'] == campo:
                            flecha = " ⬇️" if st.session_state['sort_reverse'] else " ⬆️"
                            
                        if cols_header[i].button(f"{campo.upper()}{flecha}", key=f"sort_{campo}"):
                            if st.session_state['sort_col'] == campo:
                                st.session_state['sort_reverse'] = not st.session_state['sort_reverse']
                            else:
                                st.session_state['sort_col'] = campo
                                st.session_state['sort_reverse'] = False
                            st.rerun()
                            
                    cols_header[-1].write("**ACCIÓN**")
                    st.divider()
                    
                    for p in pedidos_ordenados:
                        cols_fila = st.columns(anchos)
                        for i, campo in enumerate(campos):
                            if campo in ['fecha_creacion', 'created_at']:
                                cols_fila[i].write(formatear_fecha(p[campo]))
                            else:
                                cols_fila[i].write(str(p[campo]))
                        
                        with cols_fila[-1]:
                            if st.button("🔍 Ver detalles", key=f"det_{p['id_pedido']}", help="Inspección profunda distribuida"):
                                ver_detalles_pedido(p, headers)
                                
                    st.divider()
                else:
                    st.info("No hay pedidos registrados en la base de datos.")
            elif respuesta.status_code == 401:
                st.error("Tu sesión ha expirado.")
                st.session_state.clear()
                st.rerun()
        except requests.exceptions.ConnectionError:
            st.error("Error de conexión con la API de Pedidos.")

    # ---------------------------------------------------
    # PESTAÑA 2: CREAR PEDIDO
    # ---------------------------------------------------
    with tab2:
        st.subheader("Procesar una Nueva Venta")
        st.write("Selecciona los datos del cliente y producto usando los buscadores:")
        
        col_c, col_p, col_q = st.columns(3)
        
        with col_c:
            st.markdown("### 👥 Cliente")
            if 'selected_client' in st.session_state:
                c = st.session_state['selected_client']
                st.success(f"**Seleccionado:** \n{c['nombre']} (ID: {c['id_cliente']})")
                if st.button("🔄 Cambiar Cliente", key="btn_change_cli"):
                    del st.session_state['selected_client']
                    st.rerun()
            else:
                st.info("Ningún cliente seleccionado.")
                if st.button("🔍 Buscar Cliente Activo", key="btn_search_cli"):
                    modal_seleccionar_cliente(headers)
                    
        with col_p:
            st.markdown("### 📦 Producto")
            if 'selected_product' in st.session_state:
                p = st.session_state['selected_product']
                st.success(f"**Seleccionado:** \n{p['descripcion']} (ID: {p['id_producto']})")
                if st.button("🔄 Cambiar Producto", key="btn_change_prod"):
                    del st.session_state['selected_product']
                    if 'selected_product_stock' in st.session_state:
                        del st.session_state['selected_product_stock']
                    st.rerun()
            else:
                st.info("Ningún producto seleccionado.")
                if st.button("🔍 Buscar Producto", key="btn_search_prod"):
                    modal_seleccionar_producto(headers)
                    
        stock_valido = True
        
        with col_q:
            st.markdown("### 📊 Cantidad")
            cantidad = st.number_input("Cantidad a comprar:", min_value=1, step=1, value=1, key="input_cantidad")
            
            if 'selected_product_stock' in st.session_state:
                stock_disponible = st.session_state['selected_product_stock']
                st.info(f"💡 Unidades disponibles en almacén: **{stock_disponible}**")
                
                if cantidad > stock_disponible:
                    st.error(f"⚠️ ¡Error! Sólo hay **{stock_disponible}** unidades disponibles. Ajusta la cantidad.")
                    stock_valido = False
            else:
                st.caption("Selecciona un producto para verificar el stock.")

        st.divider()
        
        if st.button("🛒 Confirmar y Procesar Venta", type="primary", key="btn_submit_pedido", disabled=not stock_valido):
            if 'selected_client' not in st.session_state:
                st.error("Falta seleccionar el cliente.")
            elif 'selected_product' not in st.session_state:
                st.error("Falta seleccionar el producto.")
            else:
                nuevo_pedido = {
                    "id_cliente": int(st.session_state['selected_client']['id_cliente']),
                    "id_producto": int(st.session_state['selected_product']['id_producto']),
                    "cantidad": int(cantidad)
                }
                
                respuesta = requests.post(PEDIDOS_URL, json=nuevo_pedido, headers=headers)
                
                if respuesta.status_code == 201:
                    st.success(f"✅ ¡Éxito! {respuesta.json()['mensaje']}")
                    st.balloons()
                    del st.session_state['selected_client']
                    del st.session_state['selected_product']
                    if 'selected_product_stock' in st.session_state:
                        del st.session_state['selected_product_stock']
                    st.rerun()
                else:
                    try:
                        detalle_error = respuesta.json().get('detail', 'Error desconocido')
                    except:
                        detalle_error = f"El Orquestador se cayó (Código {respuesta.status_code})."
                    st.error(f"❌ Error: {detalle_error}")

    # ---------------------------------------------------
    # PESTAÑA 3: CANCELAR PEDIDO
    # ---------------------------------------------------
    with tab3:
        st.subheader("Devoluciones y Cancelaciones")
        st.write("Al cancelar, el orquestador enviará una orden de compensación para devolver el stock.")
        
        with st.form("form_cancelar_pedido"):
            id_cancelar = st.number_input("ID del Pedido a Cancelar", min_value=1, step=1)
            submit_cancelar = st.form_submit_button("❌ Ejecutar Cancelación")
            
            if submit_cancelar:
                respuesta = requests.delete(f"{PEDIDOS_URL}/{id_cancelar}", headers=headers)
                if respuesta.status_code == 200:
                    st.success(f"✅ ¡Pedido {id_cancelar} cancelado! Stock retornado al inventario.")
                else:
                    st.error(f"❌ Error: {respuesta.json().get('detail', 'No se pudo cancelar')}")

# ==========================================
# LÓGICA DE NAVEGACIÓN
# ==========================================
if "token" not in st.session_state:
    mostrar_login()
else:
    mostrar_panel_pedidos()