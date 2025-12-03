import json
import boto3
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

stepfunctions = boto3.client('stepfunctions', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

def lambda_handler(event, context):
    """Lambda para iniciar el workflow de Step Functions"""
    print(f'Iniciando workflow: {json.dumps(event)}')
    
    # Manejar invocación desde API Gateway
    if 'body' in event:
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
    else:
        body = event
    
    local_id = body.get('local_id')
    pedido_id = body.get('pedido_id')
    
    if not local_id or not pedido_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Faltan parámetros requeridos: local_id y pedido_id'}),
            'headers': {'Content-Type': 'application/json'}
        }
    
    try:
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        
        if not state_machine_arn:
            raise ValueError('STATE_MACHINE_ARN no está configurado en las variables de entorno')
        
        print(f'State Machine ARN: {state_machine_arn}')
        
        # Verificar si hay ejecuciones en curso para este pedido
        ejecucion_existente = None
        try:
            response = stepfunctions.list_executions(
                stateMachineArn=state_machine_arn,
                statusFilter='RUNNING',
                maxResults=100
            )
            
            for execution in response.get('executions', []):
                if pedido_id in execution['name']:
                    ejecucion_existente = execution
                    print(f'Ejecución en curso encontrada: {execution["name"]}')
                    break
        except Exception as e:
            print(f'Error verificando ejecuciones existentes: {str(e)}')
        
        # Si hay una ejecución en curso, detenerla y limpiar empleados
        if ejecucion_existente:
            execution_arn = ejecucion_existente['executionArn']
            
            try:
                # Detener la ejecución anterior
                print(f'Deteniendo ejecución anterior: {execution_arn}')
                stepfunctions.stop_execution(
                    executionArn=execution_arn,
                    error='Reintento',
                    cause='Se solicitó reiniciar el workflow para este pedido'
                )
                print('Ejecución anterior detenida')
                
                # Invocar lambda para liberar empleados y resetear estado del pedido
                try:
                    print('Liberando empleados y reseteando pedido...')
                    lambda_response = lambda_client.invoke(
                        FunctionName=f'{os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "").rsplit("-", 2)[0]}-workflow-liberar-pedido',
                        InvocationType='RequestResponse',
                        Payload=json.dumps({
                            'local_id': local_id,
                            'pedido_id': pedido_id,
                            'motivo': 'reintento_workflow',
                            'resetear_estado': True
                        })
                    )
                    
                    result = json.loads(lambda_response['Payload'].read())
                    print(f'Empleados liberados: {result.get("liberados", 0)}')
                    print(f'Pedido reseteado: {result.get("pedido_reseteado", False)}')
                    
                except Exception as e:
                    print(f'Error al liberar pedido: {str(e)}')
                    # Continuar de todos modos, el error no es crítico
                
            except Exception as e:
                print(f'Error al detener ejecución: {str(e)}')
        
        # Nombre de ejecución único que incluye timestamp
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        execution_name = f'pedido-{pedido_id}-{timestamp}'
        
        # Iniciar la ejecución del Step Function
        response = stepfunctions.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps({
                'local_id': local_id,
                'pedido_id': pedido_id
            })
        )
        
        execution_arn = response['executionArn']
        start_date = response['startDate'].isoformat()
        
        mensaje = 'Workflow iniciado exitosamente'
        if ejecucion_existente:
            mensaje = 'Workflow reiniciado exitosamente (ejecución anterior detenida)'
        
        print(f'{mensaje}: {execution_arn}')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': mensaje,
                'execution_arn': execution_arn,
                'execution_name': execution_name,
                'pedido_id': pedido_id,
                'local_id': local_id,
                'start_date': start_date,
                'reiniciado': ejecucion_existente is not None,
                'console_url': f'https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/{execution_arn}'
            }),
            'headers': {'Content-Type': 'application/json'}
        }
        
    except stepfunctions.exceptions.ExecutionAlreadyExists:
        # Este caso es muy raro ahora, pero lo manejamos por si acaso
        return {
            'statusCode': 409,
            'body': json.dumps({
                'error': f'Ya existe una ejecución con el mismo nombre para el pedido {pedido_id}',
                'pedido_id': pedido_id,
                'solucion': 'Por favor, intenta nuevamente en unos segundos'
            }),
            'headers': {'Content-Type': 'application/json'}
        }
        
    except Exception as e:
        print(f'Error al iniciar workflow: {str(e)}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            }),
            'headers': {'Content-Type': 'application/json'}
        }
