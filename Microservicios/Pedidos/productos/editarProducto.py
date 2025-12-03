import json
import boto3
import os
from decimal import Decimal
from utils.cors_utils import get_cors_headers  # <-- agregado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos')
table = dynamodb.Table(table_name)

# Categorías válidas
CATEGORIAS_VALIDAS = [
    "Arroces", "Tallarines", "Pollo al wok", "Carne de res", "Cerdo",
    "Mariscos", "Entradas", "Guarniciones", "Sopas", "Combos", "Bebidas", "Postres"
]

def convertir_floats_a_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convertir_floats_a_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convertir_floats_a_decimal(item) for item in obj]
    return obj

def handler(event, context):
    """
    Lambda handler para actualizar un producto en DynamoDB
    """
    cors_headers = get_cors_headers()  # <-- agregado

    try:
        # Parsear el body del evento
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        local_id = body.get('local_id')
        nombre = body.get('nombre')
        
        if not local_id or not nombre:
            return {
                'statusCode': 400,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': 'Se requieren local_id y nombre'})
            }
        
        update_data = {k: v for k, v in body.items() if k not in ['local_id', 'nombre']}
        
        if not update_data:
            return {
                'statusCode': 400,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': 'No se proporcionaron campos para actualizar'})
            }
        
        if 'precio' in update_data:
            if not isinstance(update_data['precio'], (int, float)) or update_data['precio'] < 0:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': 'precio debe ser un número positivo'})
                }
        
        if 'categoria' in update_data:
            if update_data['categoria'] not in CATEGORIAS_VALIDAS:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': f'categoria debe ser una de: {", ".join(CATEGORIAS_VALIDAS)}'})
                }
        
        if 'stock' in update_data:
            if not isinstance(update_data['stock'], int) or update_data['stock'] < 0:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': 'stock debe ser un entero positivo'})
                }
        
        existing_product = table.get_item(Key={'local_id': local_id, 'nombre': nombre})
        
        if 'Item' not in existing_product:
            return {
                'statusCode': 404,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': 'Producto no encontrado', 'message': f"El producto '{nombre}' no existe en el local {local_id}"})
            }
        
        update_data_decimal = convertir_floats_a_decimal(update_data)
        
        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in update_data_decimal.keys()])
        expression_attribute_names = {f"#{k}": k for k in update_data_decimal.keys()}
        expression_attribute_values = {f":{k}": v for k, v in update_data_decimal.items()}
        
        response = table.update_item(
            Key={'local_id': local_id, 'nombre': nombre},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'message': 'Producto actualizado exitosamente', 'data': response['Attributes']}, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': 'Error interno del servidor', 'message': str(e)})
        }
