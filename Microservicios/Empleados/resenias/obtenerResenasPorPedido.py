import boto3, json, os
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from utils.cors_utils import get_cors_headers

dynamodb = boto3.resource('dynamodb')
tabla_resenas = dynamodb.Table(os.environ['TABLE_RESENAS'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    headers = get_cors_headers()

    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    try:
        # Obtener pedido_id desde pathParameters o queryStringParameters
        pedido_id = None
        
        # Intentar primero desde pathParameters
        if event.get('pathParameters') and event['pathParameters'].get('pedido_id'):
            pedido_id = event['pathParameters']['pedido_id']
        # Intentar desde queryStringParameters
        elif event.get('queryStringParameters') and event['queryStringParameters'].get('pedido_id'):
            pedido_id = event['queryStringParameters']['pedido_id']
        
        if not pedido_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Falta el parámetro pedido_id'})
            }

        # Realizar scan con filtro por pedido_id
        # Nota: Scan es necesario porque pedido_id no es parte de la clave de reseñas
        # En producción, considerar agregar un GSI en pedido_id para mejor performance
        response = tabla_resenas.scan(
            FilterExpression=Attr('pedido_id').eq(pedido_id)
        )

        resenas = response['Items']

        # Si hay más páginas, continuar escaneando
        while 'LastEvaluatedKey' in response:
            response = tabla_resenas.scan(
                FilterExpression=Attr('pedido_id').eq(pedido_id),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            resenas.extend(response['Items'])

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'pedido_id': pedido_id,
                'total_resenas': len(resenas),
                'resenas': resenas
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f"Error al consultar reseñas: {str(e)}"})
        }
