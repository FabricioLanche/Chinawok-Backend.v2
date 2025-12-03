import boto3, json, os
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from utils.cors_utils import get_cors_headers  # <-- importar CORS

dynamodb = boto3.resource('dynamodb')
tabla_resenas = dynamodb.Table(os.environ['TABLE_RESENAS'])
tabla_empleados = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- aplicar CORS

    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    try:
        local_id = event['pathParameters']['local_id']
        dni = event['pathParameters']['dni']

        # Obtener el rol del body si existe
        rol = None
        if event.get('body'):
            try:
                body = json.loads(event['body'])
                rol = body.get('rol', '').strip().lower()
            except:
                pass

        # Si no se proporcionó rol, buscar en la tabla de empleados
        if not rol:
            try:
                response_empleado = tabla_empleados.get_item(Key={'local_id': local_id, 'dni': dni})
                if 'Item' in response_empleado:
                    rol = response_empleado['Item'].get('role', '').lower()
                else:
                    return {
                        'statusCode': 404,
                        'headers': headers,
                        'body': json.dumps({'error': 'Empleado no encontrado'})
                    }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': f"Error al buscar empleado: {str(e)}"})
                }

        # Determinar qué campo de DNI buscar según el rol
        dni_field = None
        if rol == 'cocinero':
            dni_field = 'cocinero_dni'
        elif rol == 'despachador':
            dni_field = 'despachador_dni'
        elif rol == 'repartidor':
            dni_field = 'repartidor_dni'
        else:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f"Rol '{rol}' no válido. Debe ser cocinero, despachador o repartidor"})
            }

        # Consultar reseñas filtrando por local_id y el campo de DNI correspondiente
        response = tabla_resenas.query(
            KeyConditionExpression=Key('local_id').eq(local_id),
            FilterExpression=Attr(dni_field).eq(dni)
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'empleado': {'local_id': local_id, 'dni': dni, 'rol': rol},
                'total_resenas': len(response['Items']),
                'resenas': response['Items']
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f"Error al consultar reseñas: {str(e)}"})
        }
