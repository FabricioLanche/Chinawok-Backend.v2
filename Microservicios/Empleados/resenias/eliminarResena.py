import boto3, json, os
from utils.cors_utils import get_cors_headers  # <-- CORS

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_RESENAS'])

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
        resena_id = event['pathParameters']['resena_id']

        table.delete_item(Key={'local_id': local_id, 'resena_id': resena_id})

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Reseña eliminada'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f"Error al eliminar reseña: {str(e)}"})
        }
