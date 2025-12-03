import json
import boto3
import os
import uuid
from botocore.exceptions import ClientError
from utils.cors_utils import get_cors_headers   # <<< CORS unificado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_OFERTAS', 'ChinaWok-Ofertas')
table = dynamodb.Table(table_name)

# Tabla de locales
locales_table_name = os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales')
locales_table = dynamodb.Table(locales_table_name)

# Tabla de productos
productos_table_name = os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos')
productos_table = dynamodb.Table(productos_table_name)

# Tabla de combos
combos_table_name = os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos')
combos_table = dynamodb.Table(combos_table_name)


def verificar_local_existe(local_id):
    """Verifica que el local exista"""
    try:
        response = locales_table.get_item(Key={'local_id': local_id})
        if 'Item' not in response:
            return False, f"El local '{local_id}' no existe"
        return True, None
    except ClientError as e:
        return False, f"Error al verificar local: {str(e)}"


def verificar_producto_existe(local_id, producto_nombre):
    """Verifica que el producto exista en el local especificado"""
    try:
        response = productos_table.get_item(
            Key={'local_id': local_id, 'nombre': producto_nombre}
        )
        if 'Item' not in response:
            return False, f"El producto '{producto_nombre}' no existe en el local {local_id}"
        return True, None
    except ClientError as e:
        return False, f"Error al verificar producto: {str(e)}"


def verificar_combo_existe(local_id, combo_id):
    """Verifica que el combo exista en el local especificado"""
    try:
        response = combos_table.get_item(
            Key={'local_id': local_id, 'combo_id': combo_id}
        )
        if 'Item' not in response:
            return False, f"El combo '{combo_id}' no existe en el local {local_id}"
        return True, None
    except ClientError as e:
        return False, f"Error al verificar combo: {str(e)}"


def handler(event, context):
    """Lambda handler para crear una oferta en DynamoDB"""
    try:
        # Parsear el body del evento
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        # Validación manual de campos requeridos
        campos_requeridos = ['local_id', 'porcentaje_descuento', 'fecha_inicio', 'fecha_limite']
        for campo in campos_requeridos:
            if campo not in body:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": f"Campo requerido faltante: {campo}"})
                }
        
        # Validar que tenga producto_nombre o combo_id
        if 'producto_nombre' not in body and 'combo_id' not in body:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Debe especificar producto_nombre o combo_id"})
            }
        
        # Validar porcentaje_descuento
        porcentaje = body.get('porcentaje_descuento')
        if not isinstance(porcentaje, (int, float)) or porcentaje < 0 or porcentaje > 100:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "porcentaje_descuento debe estar entre 0 y 100"})
            }
        
        local_id = body.get('local_id')
        
        # Verificar que el local existe
        exito, error_msg = verificar_local_existe(local_id)
        if not exito:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Error de validación de local", "message": error_msg})
            }
        
        # Verificar producto si se especificó
        if 'producto_nombre' in body:
            exito, error_msg = verificar_producto_existe(local_id, body['producto_nombre'])
            if not exito:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Error de validación de producto", "message": error_msg})
                }
        
        # Verificar combo si se especificó
        if 'combo_id' in body:
            exito, error_msg = verificar_combo_existe(local_id, body['combo_id'])
            if not exito:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Error de validación de combo", "message": error_msg})
                }
        
        # Generar oferta_id automáticamente con UUID
        body['oferta_id'] = str(uuid.uuid4())
        
        # Insertar en DynamoDB
        table.put_item(Item=body)
        
        return {
            "statusCode": 201,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Oferta creada exitosamente", "data": body})
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Error interno del servidor", "message": str(e)})
        }
