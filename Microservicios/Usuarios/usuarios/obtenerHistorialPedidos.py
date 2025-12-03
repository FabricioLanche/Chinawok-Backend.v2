import json
import boto3
import os
from decimal import Decimal
from utils.cors_utils import get_cors_headers

# Tablas DynamoDB
dynamodb = boto3.resource('dynamodb')

usuarios_table_name = os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios')
pedidos_table_name = os.environ.get('TABLE_PEDIDOS', 'ChinaWok-Pedidos')

usuarios_table = dynamodb.Table(usuarios_table_name)
pedidos_table = dynamodb.Table(pedidos_table_name)


def decimal_to_float(obj):
    """Convierte Decimal a float/int para JSON"""
    if isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def parse_pedido_item(item):
    """
    Convierte un item del historial a formato estandarizado {pedido_id, local_id}
    Soporta tanto el formato antiguo (solo string) como el nuevo (objeto)
    """
    if isinstance(item, dict):
        # Formato nuevo: {"pedido_id": "xxx", "local_id": "yyy"}
        return {
            "pedido_id": item.get("pedido_id"),
            "local_id": item.get("local_id")
        }
    elif isinstance(item, str):
        # Formato antiguo: solo pedido_id como string
        # Retornar con local_id null (se debe buscar con scan)
        return {
            "pedido_id": item,
            "local_id": None
        }
    return None


def lambda_handler(event, context):
    """
    Lambda para obtener el historial de pedidos del usuario autenticado
    Usa JWT del authorizer para identificar al usuario
    
    Parámetros query opcionales:
    - detallado=true: Expande los detalles completos de cada pedido
    - limite=N: Limita el número de pedidos retornados (default: todos)
    
    Respuesta (modo simple):
    {
        "pedidos": [
            {"pedido_id": "xxx", "local_id": "yyy"},
            {"pedido_id": "zzz", "local_id": "www"}
        ]
    }
    """
    try:
        # Obtener usuario autenticado del authorizer (JWT)
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        correo_autenticado = authorizer.get("correo")
        
        if not correo_autenticado:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'No autenticado', 'message': 'Token JWT requerido'})
            }
        
        # Obtener parámetros opcionales
        query_params = event.get('queryStringParameters') or {}
        detallado = query_params.get('detallado', 'false').lower() == 'true'
        limite = int(query_params.get('limite', 0)) if query_params.get('limite') else None
        
        # Obtener usuario de DynamoDB
        response = usuarios_table.get_item(Key={'correo': correo_autenticado})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Usuario no encontrado'})
            }
        
        usuario = response['Item']
        historial_pedidos_raw = usuario.get('historial_pedidos', [])
        
        # Parsear items a formato estandarizado
        historial_pedidos = [parse_pedido_item(item) for item in historial_pedidos_raw]
        historial_pedidos = [p for p in historial_pedidos if p is not None]  # Filtrar inválidos
        
        # Aplicar límite si se especificó
        if limite and limite > 0:
            historial_pedidos = historial_pedidos[-limite:]  # Últimos N pedidos
        
        # Si no se pide detallado, retornar solo las tuplas {pedido_id, local_id}
        if not detallado:
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'message': 'Historial de pedidos obtenido',
                    'correo': correo_autenticado,
                    'total_pedidos': len(historial_pedidos),
                    'pedidos': historial_pedidos  # Array de {pedido_id, local_id}
                })
            }
        
        # Modo detallado: obtener información completa de cada pedido
        pedidos_detallados = []
        pedidos_no_encontrados = []
        
        for pedido_info in historial_pedidos:
            pedido_id = pedido_info.get("pedido_id")
            local_id = pedido_info.get("local_id")
            
            try:
                # Si tenemos local_id, usar get_item (eficiente)
                if local_id:
                    get_response = pedidos_table.get_item(
                        Key={'local_id': local_id, 'pedido_id': pedido_id}
                    )
                    
                    if 'Item' in get_response:
                        pedido = get_response['Item']
                        pedido = decimal_to_float(pedido)
                        pedidos_detallados.append(pedido)
                    else:
                        pedidos_no_encontrados.append(pedido_info)
                
                # Si no tenemos local_id, hacer scan (menos eficiente, retrocompatibilidad)
                else:
                    scan_response = pedidos_table.scan(
                        FilterExpression='pedido_id = :pid',
                        ExpressionAttributeValues={':pid': pedido_id},
                        Limit=1
                    )
                    
                    if scan_response.get('Items'):
                        pedido = scan_response['Items'][0]
                        pedido = decimal_to_float(pedido)
                        pedidos_detallados.append(pedido)
                    else:
                        pedidos_no_encontrados.append(pedido_info)
                        
            except Exception as e:
                print(f"Error obteniendo pedido {pedido_id}: {str(e)}")
                pedidos_no_encontrados.append(pedido_info)
        
        response_body = {
            'message': 'Historial de pedidos detallado obtenido',
            'correo': correo_autenticado,
            'total_pedidos': len(historial_pedidos),
            'pedidos': pedidos_detallados
        }
        
        if pedidos_no_encontrados:
            response_body['pedidos_no_encontrados'] = pedidos_no_encontrados
            response_body['warning'] = f'{len(pedidos_no_encontrados)} pedidos no encontrados (posiblemente eliminados)'
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(response_body, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'message': str(e)
            })
        }
