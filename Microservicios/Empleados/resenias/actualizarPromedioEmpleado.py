import boto3, os
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import json
from utils.cors_utils import get_cors_headers  # <-- import CORS

dynamodb = boto3.resource('dynamodb')
tabla_resenas = dynamodb.Table(os.environ['TABLE_RESENAS'])
tabla_empleados = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- CORS headers consistentes

    try:
        print(f"[DEBUG] Evento recibido: {json.dumps(event, indent=2)}")
        print(f"[DEBUG] Número de registros: {len(event['Records'])}")

        for record in event['Records']:
            try:
                print(f"[DEBUG] Tipo de evento: {record['eventName']}")

                if record['eventName'] != 'INSERT':
                    print(f"[DEBUG] Evento ignorado (no es INSERT): {record['eventName']}")
                    continue

                item = record['dynamodb']['NewImage']
                print(f"[DEBUG] NewImage completo: {json.dumps(item, indent=2)}")

                if 'local_id' not in item or 'empleado_dni' not in item:
                    print(f"[ERROR] Faltan campos 'local_id' o 'empleado_dni' en el item")
                    continue

                local_id = item['local_id']['S']
                empleado_dni = item['empleado_dni']['S']
                pk = f"LOCAL#{local_id}#EMP#{empleado_dni}"

                response = tabla_resenas.query(KeyConditionExpression=Key('pk').eq(pk))
                items = response['Items']

                if not items:
                    print(f"[DEBUG] No se encontraron reseñas para {pk}")
                    continue

                calificaciones = [float(i['calificacion']) for i in items]
                promedio = Decimal(str(round(sum(calificaciones) / len(items), 2)))

                tabla_empleados.update_item(
                    Key={'local_id': local_id, 'dni': empleado_dni},
                    UpdateExpression="SET calificacion_prom = :p",
                    ExpressionAttributeValues={':p': promedio}
                )

                print(f"[DEBUG] Promedio actualizado exitosamente para empleado {empleado_dni}: {promedio}")

            except Exception as e:
                print(f"[ERROR] Error procesando registro individual: {str(e)}")
                import traceback
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
                continue

        return {
            'statusCode': 200,
            'headers': headers,  # <-- aplicar CORS
            'body': json.dumps({'message': 'Promedios actualizados correctamente'})
        }

    except Exception as e:
        print(f"[ERROR] Error crítico en lambda_handler: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': headers,  # <-- aplicar CORS
            'body': json.dumps({'error': str(e)})
        }
