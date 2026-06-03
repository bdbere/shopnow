import os
import pika
import json
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List
from seguridad import verificar_token

# CONFIGURACIÓN Y MODELOS
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://bdbere:bdbere@127.0.0.1:5672/")
COLA_INVENTARIO = 'cola_inventario'

class InventarioBase(BaseModel):
    id_producto: int = Field(..., description="ID único del producto", example=1)
    cantidad: int = Field(..., ge=0, description="Cantidad disponible en stock", example=50)

class OperacionStock(BaseModel):
    cantidad: int = Field(..., gt=0, description="Cantidad a descontar o incrementar", example=2)

class InventarioUpdate(BaseModel):
    cantidad: int = Field(..., ge=0, description="Nueva cantidad de existencias")

# AYUDANTE DE BASES DE DATOS
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
        raise e
    finally:
        cursor.close()
        conexion.close()
    return resultado

# LÓGICA DE CONSUMO DE MENSAJES DE RABBITMQ
def procesar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body)
        id_pedido = mensaje.get("id_pedido")
        id_producto = mensaje.get("id_producto")
        cantidad = mensaje.get("cantidad")
        operacion = mensaje.get("operacion", "descontar") 
        
        print(f" [*] Recibida orden de pedido {id_pedido} - Producto {id_producto} - Operación: {operacion}")

        try:
            if operacion == "descontar":
                print(f" [√] Notificación procesada: El stock ({cantidad} unid.) fue descontado correctamente por el Trigger de la BD Central.")
            
            elif operacion == "incrementar":
                query = "CALL hb_inventario_incrementar(%s, %s);"
                ejecutar_consulta(query, (id_producto, cantidad))
                print(f" [√] Stock retornado (compensación) exitosamente en BD por cancelación.")
            
            # Confirmamos a RabbitMQ que el mensaje se procesó correctamente
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f" [X] Error devuelto por la BD: {e}")
            # Confirmamos igual para que no se quede atascado en un ciclo infinito de reintentos
            ch.basic_ack(delivery_tag=method.delivery_tag) 
            
    except Exception as e:
        print(f" [!] Error grave en consumidor: {e}")
        # Si hubo un fallo de red o del sistema, le decimos a RabbitMQ que reencole el mensaje
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def iniciar_consumidor():
    try:
        conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        canal = conexion.channel()
        canal.queue_declare(queue=COLA_INVENTARIO, durable=True)
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(queue=COLA_INVENTARIO, on_message_callback=procesar_mensaje)
        canal.start_consuming()
    except Exception as e:
        print(f" [!] Error conexión RabbitMQ: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    hilo = threading.Thread(target=iniciar_consumidor, daemon=True)
    hilo.start()
    yield

# FASTAPI
app = FastAPI(
    title="Departamento de Inventario",
    dependencies=[Depends(verificar_token)],
    description="Servicio encargado de gestionar el stock de los productos en tiempo real.",
    version="3.0.0",
    lifespan=lifespan
)

@app.get("/inventario", response_model=List[InventarioBase], tags=["Consultas"], summary="Obtener todo el inventario")
def obtener_inventario():
    return ejecutar_consulta("SELECT * FROM inventario ORDER BY id_producto ASC;", fetch_all=True)

@app.post("/inventario", tags=["Operaciones"], status_code=201, summary="Registrar stock inicial")
def registrar_stock(nuevo: InventarioBase):
    try:
        query = "CALL hb_inventario_agregar(%s, %s);"
        ejecutar_consulta(query, (nuevo.id_producto, nuevo.cantidad))
        return {"mensaje": "Stock registrado exitosamente mediante SP"}
    except Exception:
        raise HTTPException(status_code=400, detail="El producto ya tiene un registro o no existe")

@app.post("/inventario/{id_producto}/descontar", tags=["Operaciones"], summary="Descontar stock manualmente")
def descontar_stock(id_producto: int, operacion: OperacionStock):
    # Verificamos si existe primero para dar un error 404 limpio
    existe = ejecutar_consulta("SELECT id_producto FROM inventario WHERE id_producto = %s", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado en inventario")
        
    try:
        query = "CALL hb_inventario_descontar(%s, %s);"
        ejecutar_consulta(query, (id_producto, operacion.cantidad))
        return {"mensaje": "Stock descontado mediante SP exitosamente"}
    except Exception as e:
        # Atrapamos la excepción 'Stock insuficiente' de PostgreSQL
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventario/{id_producto}/incrementar", tags=["Operaciones"], summary="Incrementar stock manualmente")
def incrementar_stock(id_producto: int, operacion: OperacionStock):
    existe = ejecutar_consulta("SELECT id_producto FROM inventario WHERE id_producto = %s", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado en inventario")
        
    query = "CALL hb_inventario_incrementar(%s, %s);"
    ejecutar_consulta(query, (id_producto, operacion.cantidad))
    
    return {"mensaje": "Stock incrementado mediante SP exitosamente"}

@app.patch("/inventario/{id_producto}", tags=["Escritura"], summary="Actualizar existencias manualmente")
def actualizar_inventario(id_producto: int, datos: InventarioUpdate, token_payload: dict = Depends(verificar_token)):
    """
    Permite al Orquestador o al Administrador ajustar la cantidad exacta de un producto.
    """
    # Verificamos si el producto ya tiene un registro en inventario
    query_check = "SELECT id_producto FROM inventario WHERE id_producto = %s;"
    existe = ejecutar_consulta(query_check, (id_producto,), fetch_one=True)
    
    if existe:
        # Si existe, actualizamos la cantidad
        query_update = "UPDATE inventario SET cantidad = %s, updated_at = NOW() WHERE id_producto = %s;"
        ejecutar_consulta(query_update, (datos.cantidad, id_producto))
        return {"mensaje": "Inventario actualizado correctamente", "nueva_cantidad": datos.cantidad}
    else:
        # Si no existe (producto nuevo), lo insertamos
        query_insert = "INSERT INTO inventario (id_producto, cantidad) VALUES (%s, %s);"
        ejecutar_consulta(query_insert, (id_producto, datos.cantidad))
        return {"mensaje": "Inventario inicializado correctamente", "nueva_cantidad": datos.cantidad}