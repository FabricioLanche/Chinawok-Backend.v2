import json
import os
from utils.athena_client import AthenaQueryExecutor

def handler(event, context):
    """Lambda para consultar los productos más vendidos por local"""
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
        
        if not local_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'local_id es requerido'})
            }
        
        query = f"""
        WITH productos_expandidos AS (
            SELECT 
                local_id,
                pedido_id,
                producto.nombre AS producto_nombre,
                producto.cantidad AS cantidad
            FROM pedidos
            CROSS JOIN UNNEST(productos) AS t(producto)
            WHERE local_id = '{local_id}'
        )
        SELECT 
            pe.local_id,
            pe.producto_nombre,
            COUNT(DISTINCT pe.pedido_id) AS pedidos_que_lo_incluyen,
            CAST(SUM(pe.cantidad) AS INTEGER) AS unidades_vendidas,
            p.categoria,
            ROUND(p.precio, 2) AS precio_unitario_actual,
            ROUND(SUM(pe.cantidad) * p.precio, 2) AS revenue_total,
            CAST(p.stock AS INTEGER) AS stock_disponible,
            ROUND(SUM(pe.cantidad) * 100.0 / SUM(SUM(pe.cantidad)) OVER (), 2) AS porcentaje_ventas
        FROM productos_expandidos pe
        LEFT JOIN productos p 
            ON pe.local_id = p.local_id 
            AND pe.producto_nombre = p.nombre
        GROUP BY 
            pe.local_id, 
            pe.producto_nombre, 
            p.categoria, 
            p.precio,
            p.stock
        ORDER BY unidades_vendidas DESC, revenue_total DESC
        LIMIT 20;
        """
        
        executor = AthenaQueryExecutor()
        results = executor.execute_query(query)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'local_id': local_id,
                'total_productos': len(results),
                'productos': results
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }