import os
import pika
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Optional

from fastapi.security import OAuth2PasswordRequestForm
from seguridad import crear_token_acceso, verificar_token, ADMIN_USERNAME, ADMIN_PASSWORD

app = FastAPI(
    title="Departamento de Pedidos",
    description="Servicio encargado de la custodia y registro oficial de los pedidos de la empresa. \n\n" \
    "Este servicio actúa como el punto central de integración (Orquestador). Valida datos vía HTTP y envía mensajes asíncronos a Inventario. \n\n" \
    "Ejecutar en puerto **8002**. Requiere Clientes (8000), Productos (8001) e Inventario (8003).",
    version="3.0.0",
    contact={"name": "Berenice Hernández, ISC - TecNM Querétaro"}
)

# CONFIGURACIÓN DE URLS Y SERVICIOS

CLIENTES_URL = os.getenv("CLIENTES_SERVICE_URL", "http://localhost:8000/clientes")
PRODUCTOS_URL = os.getenv("PRODUCTOS_SERVICE_URL", "http://localhost:8001/v2/productos")

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://bdbere:bdbere@127.0.0.1:5672/")
COLA_INVENTARIO = 'cola_inventario'

# MODELOS PYDANTIC (Ajustados a la BD real)

class Pedido(BaseModel):
    id_pedido: int = Field(..., description="ID único numérico del pedido", example=301)
    id_cliente: int = Field(..., description="ID único del cliente", example=101)
    id_producto: int = Field(..., description="ID único del producto", example=201)
    cantidad: int = Field(..., gt=0, description="Cantidad de productos solicitados", example=2)
    created_at: Optional[datetime] = None

class PedidoRegistro(BaseModel):
    id_cliente: int = Field(..., description="ID único del cliente", example=101)
    id_producto: int = Field(..., description="ID único del producto", example=201)
    cantidad: int = Field(..., gt=0, description="Cantidad de productos solicitados", example=2)


# AYUDANTES (BD Y RABBITMQ)

def ejecutar_consulta(query: str, params: tuple = (), fetch_one=False, fetch_all=False):
    conexion = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conexion.cursor()
    resultado = None
    try:
        cursor.execute(query, params)
        if fetch_one:
            resultado = cursor.fetchone()
        elif fetch_all:
            resultado = cursor.fetchall()
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {e}")
    finally:
        cursor.close()
        conexion.close()
    return resultado

def enviar_mensaje_inventario(mensaje: dict):
    try:
        conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        canal = conexion.channel()
        canal.queue_declare(queue=COLA_INVENTARIO, durable=True)
        canal.basic_publish(
            exchange='',
            routing_key=COLA_INVENTARIO,
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(delivery_mode=2) # Mensaje persistente
        )
        conexion.close()
        print(f" [x] Mensaje encolado exitosamente: {mensaje}")
    except Exception as e:
        print(f" [!] Advertencia: No se pudo conectar a RabbitMQ. Error: {e}")


# ENDPOINT DE AUTENTICACIÓN (LOGIN)

@app.post("/token", tags=["Seguridad"], summary="Iniciar sesión como Administrador")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Recibe usuario y contraseña, y si son correctos, devuelve el token JWT."""
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    
    # Creamos su pase de acceso con su nombre de usuario
    token = crear_token_acceso({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}

# ENDPOINTS

@app.get(
    "/pedidos", 
    response_model=List[Pedido], 
    tags=["Lectura"],
    summary="Consultar historial de pedidos",
    responses={
        200: {
            "description": "Lista de pedidos obtenida exitosamente desde PostgreSQL",
            "content": {
                "application/json": {
                    "example": [{
                        "id_pedido": 1,
                        "id_cliente": 101,
                        "id_producto": 1,
                        "cantidad": 2,
                        "created_at": "2026-05-13T12:00:00"
                    }]
                }
            }
        }
    }
)
def obtener_pedidos():
    """Retorna la lista completa de pedidos registrados."""
    query = "SELECT * FROM pedidos ORDER BY id_pedido DESC;"
    return ejecutar_consulta(query, fetch_all=True)

@app.post(
    "/pedidos", 
    tags=["Escritura"], 
    status_code=201,
    summary="Crear un nuevo pedido",
    responses={
        201: {
            "description": "Pedido registrado y enviado a la cola de inventario",
            "content": {"application/json": {"example": {"mensaje": "Pedido registrado y encolado para inventario", "id_pedido": 1}}}
        },
        400: {"description": "El cliente o producto no existe o está inactivo"},
        503: {"description": "Servicio de Clientes o Productos no disponible"}
    }
)

def crear_pedido(nuevo_pedido: PedidoRegistro, request: Request, token_payload: dict = Depends(verificar_token)):
    """
    Registra un pedido orquestando múltiples servicios:
    1. Verifica el JWT para identidad.
    2. Valida la existencia del Cliente y Producto vía HTTP.
    3. Guarda el pedido en BD.
    4. Envía la orden a RabbitMQ para descontar stock asíncronamente.
    """

    token_crudo = request.headers.get("Authorization")
    headers_seguridad = {"Authorization": token_crudo}

    # Validar Cliente 
    try:
        res_cliente = requests.get(f"{CLIENTES_URL}/{nuevo_pedido.id_cliente}", headers=headers_seguridad)
        if res_cliente.status_code == 404:
            raise HTTPException(status_code=404, detail="El cliente no existe en la base de datos")
        elif res_cliente.status_code != 200:
            raise HTTPException(status_code=400, detail=f"El servicio Clientes bloqueó la petición (Código {res_cliente.status_code})")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Servicio de clientes no disponible")

    # Validar Producto
    try:
        res_producto = requests.get(f"{PRODUCTOS_URL}/{nuevo_pedido.id_producto}", headers=headers_seguridad)
        if res_producto.status_code == 404:
            raise HTTPException(status_code=404, detail="El producto no existe en el catálogo")
        elif res_producto.status_code != 200:
            raise HTTPException(status_code=400, detail=f"El servicio Productos bloqueó la petición (Código {res_producto.status_code})")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Servicio de productos no disponible")
    
    # BD Central - Registrar el pedido y obtener su ID generado
    query = "SELECT hb_pedidos_registrar(%s, %s, %s) AS id_pedido;"
    params = (nuevo_pedido.id_cliente, nuevo_pedido.id_producto, nuevo_pedido.cantidad)
    
    resultado = ejecutar_consulta(query, params, fetch_one=True)
    nuevo_id = resultado['id_pedido']

    # Enviar orden al Inventario vía RabbitMQ
    mensaje_inventario = {
        "id_pedido": nuevo_id,
        "id_producto": nuevo_pedido.id_producto,
        "cantidad": nuevo_pedido.cantidad,
        "operacion": "descontar"
    }
    enviar_mensaje_inventario(mensaje_inventario)
    
    return {
        "mensaje": "Pedido registrado y encolado para inventario", 
        "id_pedido": nuevo_id
    }

@app.delete(
    "/pedidos/{id_pedido}", 
    tags=["Escritura"], 
    summary="Eliminar y cancelar un pedido",
    responses={
        200: {
            "description": "Pedido eliminado físicamente",
            "content": {
                "application/json": {"example": {"mensaje": "Pedido cancelado exitosamente y stock retornado", "status": "success"}}
            }
        },
        404: {"description": "Pedido no encontrado"}
    }
)
def cancelar_pedido(id_pedido: int):
    """
    Elimina un pedido físicamente de la base de datos (debido a la falta de campo de estado) 
    y envía un mensaje a RabbitMQ para regresar el stock al inventario.
    """
   # Consultar los datos del pedido ANTES de borrarlo 
    query_select = "SELECT id_producto, cantidad FROM pedidos WHERE id_pedido = %s;"
    pedido_a_borrar = ejecutar_consulta(query_select, (id_pedido,), fetch_one=True)
    
    if not pedido_a_borrar:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
    # Llamar al Procedure para eliminarlo físicamente
    query_delete = "CALL hb_pedidos_eliminar(%s);"
    ejecutar_consulta(query_delete, (id_pedido,))
    
    # Enviar mensaje de compensación a RabbitMQ
    mensaje_inventario = {
        "id_pedido": id_pedido,
        "id_producto": pedido_a_borrar['id_producto'],
        "cantidad": pedido_a_borrar['cantidad'],
        "operacion": "incrementar" 
    }
    enviar_mensaje_inventario(mensaje_inventario)
    
    return {"mensaje": "Pedido cancelado exitosamente y stock retornado", "status": "success"}