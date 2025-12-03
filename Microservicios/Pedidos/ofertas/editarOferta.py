import json
import boto3
import os
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
    """Lambda handler para actualizar una oferta en DynamoDB"""
    try:
        # Parsear body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        # Obtener keys
        local_id = body.get('local_id')
        oferta_id = body.get('oferta_id')

        if not local_id or not oferta_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Se requieren local_id y oferta_id"})
            }

        # Campos permitidos para actualización
        campos_permitidos = [
            'producto_nombre',
            'combo_id',
            'fecha_inicio',
            'fecha_limite',
            'porcentaje_descuento'
        ]
        update_data = {k: v for k, v in body.items() if k in campos_permitidos}

        if not update_data:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "No se proporcionaron campos para actualizar"})
            }

        # Validar porcentaje si viene en la actualización
        if 'porcentaje_descuento' in update_data:
            p = update_data['porcentaje_descuento']
            if not isinstance(p, (int, float)) or p < 0 or p > 100:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "porcentaje_descuento debe estar entre 0 y 100"})
                }

        # Validación de local
        exito, error_msg = verificar_local_existe(local_id)
        if not exito:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "error": "Error de validación de local",
                    "message": error_msg
                })
            }

        # Validar producto si viene
        if 'producto_nombre' in update_data:
            exito, error_msg = verificar_producto_existe(local_id, update_data['producto_nombre'])
            if not exito:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({
                        "error": "Error de validación de producto",
                        "message": error_msg
                    })
                }

        # Validar combo si viene
        if 'combo_id' in update_data:
            exito, error_msg = verificar_combo_existe(local_id, update_data['combo_id'])
            if not exito:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({
                        "error": "Error de validación de combo",
                        "message": error_msg
                    })
                }

        # Construir UpdateExpression
        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in update_data.keys()])
        expression_attribute_names = {f"#{k}": k for k in update_data.keys()}
        expression_attribute_values = {f":{k}": v for k, v in update_data.items()}

        # Actualizar registro
        response = table.update_item(
            Key={'local_id': local_id, 'oferta_id': oferta_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Oferta actualizada exitosamente",
                "data": response["Attributes"]
            }, default=str)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "error": "Error interno del servidor",
                "message": str(e)
            })
        }
