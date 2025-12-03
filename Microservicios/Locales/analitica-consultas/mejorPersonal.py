import json
import os
from utils.athena_client import AthenaQueryExecutor

def handler(event, context):
    """Lambda para consultar el ranking del mejor personal por local"""
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
        WITH pedidos_por_empleado AS (
            SELECT
                p.local_id,
                h.empleado.dni AS empleado_dni,
                COUNT(DISTINCT p.pedido_id) AS pedidos_atendidos,
                SUM(p.costo) AS revenue_generado
            FROM pedidos p
            CROSS JOIN UNNEST(p.historial_estados) AS t(h)
            WHERE p.local_id = '{local_id}'
            AND h.empleado IS NOT NULL
            AND h.empleado.dni IS NOT NULL
            GROUP BY p.local_id, h.empleado.dni
        ),

        resenas_por_empleado AS (
            -- Reseñas al cocinero
            SELECT 
                local_id,
                cocinero_dni AS empleado_dni,
                COUNT(*) AS total_resenas
            FROM resenas
            WHERE local_id = '{local_id}'
            AND cocinero_dni IS NOT NULL
            GROUP BY local_id, cocinero_dni

            UNION ALL

            -- Reseñas al repartidor
            SELECT 
                local_id,
                repartidor_dni AS empleado_dni,
                COUNT(*) AS total_resenas
            FROM resenas
            WHERE local_id = '{local_id}'
            AND repartidor_dni IS NOT NULL
            GROUP BY local_id, repartidor_dni

            UNION ALL

            -- Reseñas al despachador
            SELECT 
                local_id,
                despachador_dni AS empleado_dni,
                COUNT(*) AS total_resenas
            FROM resenas
            WHERE local_id = '{local_id}'
            AND despachador_dni IS NOT NULL
            GROUP BY local_id, despachador_dni
        ),

        resenas_agrupadas AS (
            SELECT
                local_id,
                empleado_dni,
                SUM(total_resenas) AS total_resenas
            FROM resenas_por_empleado
            GROUP BY local_id, empleado_dni
        )

        SELECT 
            e.local_id,
            e.dni,
            e.nombre || ' ' || e.apellido AS nombre_completo,
            e.role AS rol,
            ROUND(e.sueldo, 2) AS sueldo_mensual,
            ROUND(COALESCE(e.calificacion_prom, 0), 2) AS calificacion_promedio,
            COALESCE(r.total_resenas, 0) AS total_resenas,
            COALESCE(p.pedidos_atendidos, 0) AS pedidos_atendidos,
            ROUND(COALESCE(p.revenue_generado, 0), 2) AS revenue_generado,
            ROUND(
                (COALESCE(e.calificacion_prom, 0) * 0.6) +
                (LEAST(COALESCE(p.pedidos_atendidos, 0) / 100.0, 1) * 5 * 0.3) +
                (LEAST(COALESCE(r.total_resenas, 0) / 20.0, 1) * 5 * 0.1),
                2
            ) AS score_performance
        FROM empleados e
        LEFT JOIN pedidos_por_empleado p 
            ON e.local_id = p.local_id 
            AND e.dni = p.empleado_dni
        LEFT JOIN resenas_agrupadas r 
            ON e.local_id = r.local_id 
            AND e.dni = r.empleado_dni
        WHERE e.local_id = '{local_id}'
        ORDER BY score_performance DESC, pedidos_atendidos DESC, calificacion_promedio DESC;
        """
        
        executor = AthenaQueryExecutor()
        results = executor.execute_query(query)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'local_id': local_id,
                'total_empleados': len(results),
                'empleados': results
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }