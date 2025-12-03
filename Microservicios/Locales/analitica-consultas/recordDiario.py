import json
import os
from datetime import datetime
from utils.athena_client import AthenaQueryExecutor

def handler(event, context):
    """Lambda para consultar el récord diario de pedidos y revenue por mes"""
    # Headers CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Content-Type': 'application/json'
    }
    
    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        local_id = body.get('local_id', 'LOCAL-0001')
        year = body.get('year', datetime.now().year)
        month = body.get('month', datetime.now().month)
        
        if not local_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'local_id es requerido'})
            }
        
        query = f"""
        SELECT 
            local_id,
            DATE(from_iso8601_timestamp(fecha_entrega_aproximada)) AS fecha,
            COUNT(*) AS total_pedidos,
            ROUND(SUM(costo), 2) AS revenue_diario,
            ROUND(AVG(costo), 2) AS ticket_promedio
        FROM pedidos
        WHERE local_id = '{local_id}'
            AND YEAR(from_iso8601_timestamp(fecha_entrega_aproximada)) = {year}
            AND MONTH(from_iso8601_timestamp(fecha_entrega_aproximada)) = {month}
        GROUP BY 
            local_id,
            DATE(from_iso8601_timestamp(fecha_entrega_aproximada))
        ORDER BY fecha ASC;
        """
        
        executor = AthenaQueryExecutor()
        results = executor.execute_query(query)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'local_id': local_id,
                'year': year,
                'month': month,
                'total_dias': len(results),
                'record_diario': results
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }