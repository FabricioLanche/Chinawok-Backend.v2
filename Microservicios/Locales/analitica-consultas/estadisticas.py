import json
import os
from utils.athena_client import AthenaQueryExecutor

def handler(event, context):
    """Lambda para consultar estadísticas generales del local (dashboard completo)"""
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
        WITH stats_pedidos AS (
            SELECT 
                local_id,
                COUNT(*) AS total_pedidos,
                COUNT(DISTINCT usuario_correo) AS clientes_unicos,
                SUM(costo) AS revenue_total,
                MIN(costo) AS pedido_minimo,
                MAX(costo) AS pedido_maximo,
                AVG(costo) AS ticket_promedio,
                SUM(CASE WHEN estado = 'recibido' THEN 1 ELSE 0 END) AS pedidos_completados,
                SUM(CASE WHEN estado = 'enviando' THEN 1 ELSE 0 END) AS pedidos_en_envio,
                SUM(CASE WHEN estado = 'empacando' THEN 1 ELSE 0 END) AS pedidos_empacando,
                SUM(CASE WHEN estado = 'cocinando' THEN 1 ELSE 0 END) AS pedidos_cocinando,
                SUM(CASE WHEN estado = 'eligiendo' THEN 1 ELSE 0 END) AS pedidos_eligiendo
            FROM pedidos
            WHERE local_id = '{local_id}'
            GROUP BY local_id
        ),
        stats_productos AS (
            SELECT 
                local_id,
                COUNT(*) AS total_productos,
                SUM(stock) AS inventario_total,
                SUM(CASE WHEN stock > 0 AND stock < 10 THEN 1 ELSE 0 END) AS productos_stock_bajo,
                SUM(CASE WHEN stock = 0 THEN 1 ELSE 0 END) AS productos_sin_stock
            FROM productos
            WHERE local_id = '{local_id}'
            GROUP BY local_id
        ),
        stats_empleados AS (
            SELECT 
                local_id,
                COUNT(*) AS total_empleados,
                SUM(CASE WHEN role = 'Cocinero' THEN 1 ELSE 0 END) AS cocineros,
                SUM(CASE WHEN role = 'Despachador' THEN 1 ELSE 0 END) AS despachadores,
                SUM(CASE WHEN role = 'Repartidor' THEN 1 ELSE 0 END) AS repartidores,
                AVG(calificacion_prom) AS calificacion_promedio_staff,
                SUM(sueldo) AS nomina_mensual
            FROM empleados
            WHERE local_id = '{local_id}'
            GROUP BY local_id
        ),
        stats_ofertas AS (
            SELECT 
                local_id,
                COUNT(*) AS ofertas_activas,
                AVG(porcentaje_descuento) AS descuento_promedio
            FROM ofertas
            WHERE local_id = '{local_id}'
                AND from_iso8601_timestamp(fecha_limite) > CURRENT_TIMESTAMP
            GROUP BY local_id
        ),
        stats_resenas AS (
            SELECT 
                local_id,
                COUNT(*) AS total_resenas,
                AVG(calificacion) AS calificacion_promedio_cliente,
                SUM(CASE WHEN calificacion >= 4.5 THEN 1 ELSE 0 END) AS resenas_excelentes,
                SUM(CASE WHEN calificacion < 3.0 THEN 1 ELSE 0 END) AS resenas_malas
            FROM resenas
            WHERE local_id = '{local_id}'
            GROUP BY local_id
        ),
        stats_combos AS (
            SELECT 
                local_id,
                COUNT(*) AS total_combos,
                SUM(CASE WHEN disponible = true THEN 1 ELSE 0 END) AS combos_disponibles
            FROM combos
            WHERE local_id = '{local_id}'
            GROUP BY local_id
        )
        SELECT 
            l.local_id,
            l.direccion,
            l.telefono,
            l.hora_apertura,
            l.hora_finalizacion,
            l.gerente.nombre AS gerente_nombre,
            l.gerente.correo AS gerente_correo,
            COALESCE(sp.total_pedidos, 0) AS total_pedidos,
            COALESCE(sp.clientes_unicos, 0) AS clientes_unicos,
            ROUND(COALESCE(sp.revenue_total, 0), 2) AS revenue_total,
            ROUND(COALESCE(sp.ticket_promedio, 0), 2) AS ticket_promedio,
            ROUND(COALESCE(sp.pedido_minimo, 0), 2) AS pedido_minimo,
            ROUND(COALESCE(sp.pedido_maximo, 0), 2) AS pedido_maximo,
            COALESCE(sp.pedidos_completados, 0) AS pedidos_completados,
            COALESCE(sp.pedidos_en_envio, 0) AS pedidos_en_envio,
            COALESCE(sp.pedidos_empacando, 0) AS pedidos_empacando,
            COALESCE(sp.pedidos_cocinando, 0) AS pedidos_cocinando,
            COALESCE(sp.pedidos_eligiendo, 0) AS pedidos_eligiendo,
            ROUND(COALESCE(sp.pedidos_completados, 0) * 100.0 / NULLIF(sp.total_pedidos, 0), 2) AS tasa_completado_pct,
            COALESCE(spr.total_productos, 0) AS total_productos,
            CAST(COALESCE(spr.inventario_total, 0) AS INTEGER) AS inventario_total,
            COALESCE(spr.productos_stock_bajo, 0) AS productos_stock_bajo,
            COALESCE(spr.productos_sin_stock, 0) AS productos_sin_stock,
            COALESCE(se.total_empleados, 0) AS total_empleados,
            COALESCE(se.cocineros, 0) AS cocineros,
            COALESCE(se.despachadores, 0) AS despachadores,
            COALESCE(se.repartidores, 0) AS repartidores,
            ROUND(COALESCE(se.calificacion_promedio_staff, 0), 2) AS calificacion_staff,
            ROUND(COALESCE(se.nomina_mensual, 0), 2) AS nomina_mensual,
            COALESCE(so.ofertas_activas, 0) AS ofertas_activas,
            ROUND(COALESCE(so.descuento_promedio, 0), 2) AS descuento_promedio_pct,
            COALESCE(sc.total_combos, 0) AS total_combos,
            COALESCE(sc.combos_disponibles, 0) AS combos_disponibles,
            COALESCE(sr.total_resenas, 0) AS total_resenas,
            ROUND(COALESCE(sr.calificacion_promedio_cliente, 0), 2) AS calificacion_cliente,
            COALESCE(sr.resenas_excelentes, 0) AS resenas_excelentes,
            COALESCE(sr.resenas_malas, 0) AS resenas_malas
        FROM locales l
        LEFT JOIN stats_pedidos sp ON l.local_id = sp.local_id
        LEFT JOIN stats_productos spr ON l.local_id = spr.local_id
        LEFT JOIN stats_empleados se ON l.local_id = se.local_id
        LEFT JOIN stats_ofertas so ON l.local_id = so.local_id
        LEFT JOIN stats_resenas sr ON l.local_id = sr.local_id
        LEFT JOIN stats_combos sc ON l.local_id = sc.local_id
        WHERE l.local_id = '{local_id}';
        """
        
        executor = AthenaQueryExecutor()
        results = executor.execute_query(query)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'local_id': local_id,
                'estadisticas': results[0] if results else {}
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }