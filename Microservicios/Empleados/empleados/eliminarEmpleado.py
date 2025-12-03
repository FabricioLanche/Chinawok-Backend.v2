import boto3, json, os
from utils.cors_utils import get_cors_headers  # <-- importado

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])

def lambda_handler(event, context):
    cors_headers = get_cors_headers()  # <-- reemplaza headers manuales

    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    local_id = event['pathParameters']['local_id']
    dni = event['pathParameters']['dni']

    table.delete_item(Key={'local_id': local_id, 'dni': dni})

    return {
        'statusCode': 200,
        'headers': cors_headers,  # <-- reemplazado
        'body': json.dumps({'message': 'Empleado eliminado'})
    }
