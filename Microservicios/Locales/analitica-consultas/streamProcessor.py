import json
import os
import boto3
from decimal import Decimal
from datetime import datetime
from utils.logger import get_logger
from utils.dynamodb_client import get_table_data
from utils.s3_client import upload_to_s3

logger = get_logger(__name__)

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Mapeo de ARN de tabla a nombre de tabla y clave S3
TABLE_MAPPING = {
    'ChinaWok-Locales': 'locales',
    'ChinaWok-Usuarios': 'usuarios',
    'ChinaWok-Productos': 'productos',
    'ChinaWok-Empleados': 'empleados',
    'ChinaWok-Combos': 'combos',
    'ChinaWok-Pedidos': 'pedidos',
    'ChinaWok-Ofertas': 'ofertas',
    'ChinaWok-Resenas': 'resenas',
}

S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
S3_PREFIX = os.environ.get('S3_INGESTION_PREFIX', 'data-ingestion')

# Mapeo de tabla a su clave primaria
PRIMARY_KEYS = {
    'ChinaWok-Locales': 'local_id',
    'ChinaWok-Usuarios': 'correo',
    'ChinaWok-Productos': ['local_id', 'nombre'],
    'ChinaWok-Empleados': ['local_id', 'dni'],
    'ChinaWok-Combos': ['local_id', 'combo_id'],
    'ChinaWok-Pedidos': ['local_id', 'pedido_id'],
    'ChinaWok-Ofertas': ['local_id', 'oferta_id'],
    'ChinaWok-Resenas': ['local_id', 'resena_id'],
}

def extract_table_name_from_arn(event_source_arn):
    """
    Extrae el nombre de la tabla del ARN del stream
    ARN format: arn:aws:dynamodb:region:account-id:table/TABLE_NAME/stream/timestamp
    """
    try:
        parts = event_source_arn.split('/')
        table_name = parts[1]
        return table_name
    except Exception as e:
        logger.error(f'Error extrayendo nombre de tabla del ARN: {str(e)}')
        return None


def get_table_key(table_name):
    """
    Obtiene la clave S3 correspondiente al nombre de la tabla
    """
    return TABLE_MAPPING.get(table_name)

def decimal_to_float(obj):
    """Convierte Decimal a float para JSON"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_record_key(record, table_name):
    """Genera una clave única para identificar el registro"""
    pk = PRIMARY_KEYS.get(table_name)
    
    if isinstance(pk, list):
        # Composite key
        return tuple(record.get(k) for k in pk)
    else:
        # Single key
        return record.get(pk)


def load_existing_data(table_key):
    """Carga el archivo JSONL existente de S3 y lo convierte a dict"""
    s3_key = f'{S3_PREFIX}/{table_key}/data.jsonl'
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        
        # Convertir JSONL a dict indexado por clave primaria
        records = {}
        for line in content.strip().split('\n'):
            if line:
                record = json.loads(line)
                # Usar el nombre de tabla original, no table_key
                table_name = None
                for tn, tk in TABLE_MAPPING.items():
                    if tk == table_key:
                        table_name = tn
                        break
                
                if table_name:
                    key = get_record_key(record, table_name)
                    records[key] = record
        
        logger.info(f'📖 Cargados {len(records)} registros existentes de {table_key}')
        return records
        
    except s3_client.exceptions.NoSuchKey:
        logger.info(f'📄 Archivo no existe aún: {s3_key}. Creando nuevo.')
        return {}
    except Exception as e:
        logger.error(f'Error cargando datos existentes: {str(e)}')
        return {}


def save_data_to_s3(table_key, records):
    """Guarda el dict de registros como JSONL en S3"""
    s3_key = f'{S3_PREFIX}/{table_key}/data.jsonl'
    
    # Convertir dict a JSONL
    jsonl_lines = [json.dumps(record, default=decimal_to_float) for record in records.values()]
    jsonl_content = '\n'.join(jsonl_lines)
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=jsonl_content.encode('utf-8'),
        ContentType='application/x-ndjson'
    )
    
    return f's3://{S3_BUCKET}/{s3_key}'

def handler(event, context):
    """
    Procesa eventos de DynamoDB Streams de forma INCREMENTAL
    Actualiza solo el archivo de la tabla modificada aplicando cambios
    
    Estrategia: INCREMENTAL UPDATE (solo procesa cambios del stream)
    - Lee el archivo existente de S3
    - Aplica solo los cambios detectados (INSERT/MODIFY/REMOVE)
    - Sobrescribe el archivo con los datos actualizados
    """
    try:
        # Agrupar cambios por tabla
        changes_by_table = {}
        
        logger.info(f'📥 Recibidos {len(event["Records"])} eventos de DynamoDB Streams')
        
        # Procesar cada registro del stream
        for record in event['Records']:
            event_name = record['eventName']  # INSERT, MODIFY, REMOVE
            event_source_arn = record['eventSourceARN']
            table_name = extract_table_name_from_arn(event_source_arn)
            
            if not table_name:
                continue
            
            if table_name not in changes_by_table:
                changes_by_table[table_name] = []
            
            # Deserializar el registro
            from boto3.dynamodb.types import TypeDeserializer
            deserializer = TypeDeserializer()
            
            if event_name in ['INSERT', 'MODIFY']:
                changed_record = record['dynamodb'].get('NewImage')
                if changed_record:
                    normal_record = {k: deserializer.deserialize(v) for k, v in changed_record.items()}
                    changes_by_table[table_name].append({
                        'event_type': event_name,
                        'data': normal_record
                    })
                    logger.info(f'📝 {event_name}: {table_name}')
            
            elif event_name == 'REMOVE':
                old_record = record['dynamodb'].get('OldImage')
                if old_record:
                    normal_record = {k: deserializer.deserialize(v) for k, v in old_record.items()}
                    changes_by_table[table_name].append({
                        'event_type': 'REMOVE',
                        'data': normal_record
                    })
                    logger.info(f'🗑️  REMOVE: {table_name}')
        
        # Procesar cada tabla modificada
        results = []
        for table_name, changes in changes_by_table.items():
            try:
                table_key = get_table_key(table_name)
                
                if not table_key:
                    logger.warning(f'⚠️  Tabla no mapeada: {table_name}')
                    continue
                
                logger.info(f'🔄 Procesando {len(changes)} cambios en tabla: {table_name}')
                
                # 1. Cargar datos existentes de S3
                existing_records = load_existing_data(table_key)
                
                inserts = 0
                updates = 0
                deletes = 0
                
                # 2. Aplicar cambios incrementalmente
                for change in changes:
                    event_type = change['event_type']
                    data = change['data']
                    key = get_record_key(data, table_name)
                    
                    if event_type == 'INSERT':
                        existing_records[key] = data
                        inserts += 1
                    
                    elif event_type == 'MODIFY':
                        existing_records[key] = data
                        updates += 1
                    
                    elif event_type == 'REMOVE':
                        if key in existing_records:
                            del existing_records[key]
                            deletes += 1
                
                # 3. Guardar archivo actualizado en S3
                s3_uri = save_data_to_s3(table_key, existing_records)
                
                result = {
                    'table': table_name,
                    'table_key': table_key,
                    'total_records': len(existing_records),
                    'inserts': inserts,
                    'updates': updates,
                    'deletes': deletes,
                    's3_location': s3_uri,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'status': 'success'
                }
                
                results.append(result)
                logger.info(f'✅ Archivo actualizado: {table_name} → {len(existing_records)} registros totales')
                logger.info(f'   (+{inserts} inserts, ~{updates} updates, -{deletes} deletes)')
                
            except Exception as e:
                logger.error(f'❌ Error procesando tabla {table_name}: {str(e)}', exc_info=True)
                results.append({
                    'table': table_name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Resumen final
        success_count = len([r for r in results if r['status'] == 'success'])
        failed_count = len([r for r in results if r['status'] == 'failed'])
        
        logger.info(f'📊 Procesamiento completado: {success_count} exitosos, {failed_count} fallidos')
        
        return {
            'statusCode': 200,
            'processed_tables': len(changes_by_table),
            'successful': success_count,
            'failed': failed_count,
            'results': results
        }
        
    except Exception as e:
        logger.error(f'❌ Error crítico en stream processor: {str(e)}', exc_info=True)
        raise
    """
    Procesa eventos de DynamoDB Streams de múltiples tablas
    Cuando detecta cambios, actualiza el archivo JSONL completo en S3
    
    Estrategia: FULL REFRESH (recarga completa de la tabla)
    - Es más simple y confiable que el incremental
    - Garantiza consistencia total con DynamoDB
    - Eficiente para tablas de tamaño moderado (<100k registros)
    """
    try:
        # El evento puede contener múltiples records de múltiples tablas
        processed_tables = set()
        
        logger.info(f'📥 Recibidos {len(event["Records"])} eventos de DynamoDB Streams')
        
        # Identificar qué tablas fueron modificadas
        for record in event['Records']:
            event_source_arn = record['eventSourceARN']
            table_name = extract_table_name_from_arn(event_source_arn)
            
            if table_name:
                processed_tables.add(table_name)
                event_name = record['eventName']  # INSERT, MODIFY, REMOVE
                logger.info(f'📝 Detectado cambio en tabla: {table_name} (Evento: {event_name})')
        
        # Para cada tabla modificada, hacer un FULL REFRESH
        results = []
        for table_name in processed_tables:
            try:
                table_key = get_table_key(table_name)
                
                if not table_key:
                    logger.warning(f'⚠️  Tabla no mapeada: {table_name}')
                    continue
                
                logger.info(f'🔄 Iniciando FULL REFRESH para tabla: {table_name}')
                
                # 1. Obtener TODOS los datos actuales de DynamoDB
                items = get_table_data(table_name)
                logger.info(f'✅ Obtenidos {len(items)} registros de {table_name}')
                
                # 2. Subir a S3 (sobrescribe el archivo existente)
                s3_key = f'{S3_PREFIX}/{table_key}/data.jsonl'
                s3_uri = upload_to_s3(S3_BUCKET, s3_key, items)
                
                result = {
                    'table': table_name,
                    'table_key': table_key,
                    'records': len(items),
                    's3_location': s3_uri,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'status': 'success'
                }
                
                results.append(result)
                logger.info(f'✅ FULL REFRESH completado: {table_name} → {s3_uri}')
                
            except Exception as e:
                logger.error(f'❌ Error procesando tabla {table_name}: {str(e)}', exc_info=True)
                results.append({
                    'table': table_name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Resumen final
        success_count = len([r for r in results if r['status'] == 'success'])
        failed_count = len([r for r in results if r['status'] == 'failed'])
        
        logger.info(f'📊 Procesamiento completado: {success_count} exitosos, {failed_count} fallidos')
        
        return {
            'statusCode': 200,
            'processed_tables': len(processed_tables),
            'successful': success_count,
            'failed': failed_count,
            'results': results
        }
        
    except Exception as e:
        logger.error(f'❌ Error crítico en stream processor: {str(e)}', exc_info=True)
        raise