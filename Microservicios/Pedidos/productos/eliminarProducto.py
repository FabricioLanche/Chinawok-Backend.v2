import json
import boto3
import os
from boto3.dynamodb.conditions import Attr
from utils.cors_utils import get_cors_headers

# Clientes DynamoDB
dynamodb = boto3.resource('dynamodb')

table_productos = dynamodb.Table(os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos'))
table_combos = dynamodb.Table(os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos'))
table_ofertas = dynamodb.Table(os.environ.get('TABLE_OFERTAS', 'ChinaWok-Ofertas'))


def eliminar_combos_relacionados(local_id, nombre_producto):
    """Elimina todos los combos que contienen el producto eliminado"""
    try:
        # Scan para encontrar combos que contengan el producto
        response = table_combos.scan(
            FilterExpression=Attr('local_id').eq(local_id) & Attr('productos_nombres').contains(nombre_producto)
        )
        
        combos_eliminados = []
        for combo in response.get('Items', []):
            # Eliminar el combo
            table_combos.delete_item(
                Key={
                    'local_id': combo['local_id'],
                    'combo_id': combo['combo_id']
                }
            )
            combos_eliminados.append(combo['combo_id'])
        
        return combos_eliminados
    
    except Exception as e:
        print(f"Error eliminando combos relacionados: {str(e)}")
        return []


def eliminar_ofertas_relacionadas(local_id, nombre_producto):
    """Elimina todas las ofertas que referencian el producto eliminado"""
    try:
        # Scan para encontrar ofertas del producto
        response = table_ofertas.scan(
            FilterExpression=Attr('local_id').eq(local_id) & Attr('producto_nombre').eq(nombre_producto)
        )
        
        ofertas_eliminadas = []
        for oferta in response.get('Items', []):
            # Eliminar la oferta
            table_ofertas.delete_item(
                Key={
                    'local_id': oferta['local_id'],
                    'oferta_id': oferta['oferta_id']
                }
            )
            ofertas_eliminadas.append(oferta['oferta_id'])
        
        return ofertas_eliminadas
    
    except Exception as e:
        print(f"Error eliminando ofertas relacionadas: {str(e)}")
        return []


def handler(event, context):
    """
    Lambda handler para eliminar un producto y todas sus referencias
    Elimina automáticamente:
    - El producto
    - Combos que lo contienen
    - Ofertas que lo referencian
    """
    cors_headers = get_cors_headers()

    try:
        # Obtener parámetros
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        local_id = params.get('local_id') or path_params.get('local_id') or body.get('local_id')
        nombre = params.get('nombre') or path_params.get('nombre') or body.get('nombre')
        
        if not local_id or not nombre:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Se requieren local_id y nombre'})
            }
        
        # Verificar que el producto existe antes de eliminar
        response = table_productos.get_item(Key={'local_id': local_id, 'nombre': nombre})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Producto no encontrado'})
            }
        
        producto = response['Item']
        
        # 1. Eliminar combos relacionados
        combos_eliminados = eliminar_combos_relacionados(local_id, nombre)
        
        # 2. Eliminar ofertas relacionadas
        ofertas_eliminadas = eliminar_ofertas_relacionadas(local_id, nombre)
        
        # 3. Eliminar el producto
        table_productos.delete_item(Key={'local_id': local_id, 'nombre': nombre})
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Producto y referencias eliminadas exitosamente',
                'data': {
                    'producto': {
                        'local_id': local_id,
                        'nombre': nombre
                    },
                    'referencias_eliminadas': {
                        'combos': len(combos_eliminados),
                        'combos_ids': combos_eliminados,
                        'ofertas': len(ofertas_eliminadas),
                        'ofertas_ids': ofertas_eliminadas
                    }
                }
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Error interno del servidor', 'message': str(e)})
        }