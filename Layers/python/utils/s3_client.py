"""
Cliente de S3 para operaciones comunes
"""
import boto3
import json
from datetime import datetime
from decimal import Decimal

s3_client = boto3.client('s3')


class DecimalEncoder(json.JSONEncoder):
    """Encoder para convertir Decimal a float en JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def upload_to_s3(bucket: str, key: str, data: list) -> str:
    """
    Sube datos a S3 en formato JSON Lines (JSONL) para compatibilidad con Glue
    SOBREESCRIBE el archivo si ya existe (no crea versiones con timestamp)
    
    Args:
        bucket: Nombre del bucket S3
        key: Ruta completa del archivo en S3 (se recomienda usar nombre fijo)
        data: Lista de diccionarios a subir
    
    Returns:
        str: URI completa de S3 (s3://bucket/key)
    """
    try:
        # Convertir lista de dicts a JSON Lines (una línea por objeto)
        jsonl_lines = []
        for item in data:
            json_line = json.dumps(item, cls=DecimalEncoder, ensure_ascii=False)
            jsonl_lines.append(json_line)
        
        # Unir líneas con salto de línea
        jsonl_content = '\n'.join(jsonl_lines)
        
        # Cambiar extensión a .jsonl para claridad
        if key.endswith('.json'):
            key = key.replace('.json', '.jsonl')
        
        # Timestamp para metadata (no en el nombre del archivo)
        upload_timestamp = datetime.utcnow().isoformat() + 'Z'
        
        # Subir a S3 (SOBREESCRIBE si ya existe)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=jsonl_content.encode('utf-8'),
            ContentType='application/x-ndjson',
            Metadata={
                'records': str(len(data)),
                'format': 'jsonl',
                'upload_timestamp': upload_timestamp,
                'last_updated': upload_timestamp
            }
        )
        
        s3_uri = f's3://{bucket}/{key}'
        print(f'✅ Archivo subido/actualizado: {s3_uri}')
        print(f'   Registros: {len(data)}, Formato: JSONL, Última actualización: {upload_timestamp}')
        
        return s3_uri
        
    except Exception as e:
        print(f'❌ Error subiendo archivo a S3: {str(e)}')
        raise Exception(f'Error subiendo archivo a S3: {str(e)}')


def list_s3_files(bucket: str, prefix: str) -> list:
    """
    Lista archivos en un bucket S3 bajo un prefijo
    
    Args:
        bucket: Nombre del bucket
        prefix: Prefijo/path para filtrar
    
    Returns:
        list: Lista de keys de archivos
    """
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )
        
        files = []
        if 'Contents' in response:
            files = [obj['Key'] for obj in response['Contents']]
        
        return files
        
    except Exception as e:
        print(f'Error listando archivos S3: {str(e)}')
        return []

def delete_old_versions(bucket: str, prefix: str, keep_latest: int = 1):
    """
    Elimina versiones antiguas de archivos en S3, manteniendo solo las más recientes
    
    Args:
        bucket: Nombre del bucket
        prefix: Prefijo/path de los archivos
        keep_latest: Número de versiones a mantener (por defecto: 1)
    
    Returns:
        int: Número de archivos eliminados
    """
    try:
        files = list_s3_files(bucket, prefix)
        
        if len(files) <= keep_latest:
            return 0
        
        # Ordenar por fecha de modificación (más reciente primero)
        files_with_metadata = []
        for key in files:
            response = s3_client.head_object(Bucket=bucket, Key=key)
            files_with_metadata.append({
                'key': key,
                'last_modified': response['LastModified']
            })
        
        files_with_metadata.sort(key=lambda x: x['last_modified'], reverse=True)
        
        # Eliminar archivos antiguos
        deleted_count = 0
        for file_info in files_with_metadata[keep_latest:]:
            s3_client.delete_object(Bucket=bucket, Key=file_info['key'])
            deleted_count += 1
            print(f'🗑️  Eliminado archivo antiguo: {file_info["key"]}')
        
        return deleted_count
        
    except Exception as e:
        print(f'Error eliminando versiones antiguas: {str(e)}')
        return 0
