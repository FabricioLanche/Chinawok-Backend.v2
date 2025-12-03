import json
import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import time
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import random as random_module

# Cargar variables de entorno desde .env en la raíz del proyecto
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)

# Configuración de AWS DynamoDB
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
dynamodb_client = boto3.client('dynamodb', region_name=AWS_REGION)

# Nombres de las tablas DynamoDB
TABLE_LOCALES = os.getenv('TABLE_LOCALES')
TABLE_USUARIOS = os.getenv('TABLE_USUARIOS')
TABLE_PRODUCTOS = os.getenv('TABLE_PRODUCTOS')
TABLE_EMPLEADOS = os.getenv('TABLE_EMPLEADOS')
TABLE_COMBOS = os.getenv('TABLE_COMBOS')
TABLE_PEDIDOS = os.getenv('TABLE_PEDIDOS')
TABLE_OFERTAS = os.getenv('TABLE_OFERTAS')
TABLE_RESENAS = os.getenv('TABLE_RESENAS')
TABLE_CONEXIONES = os.getenv('TABLE_CONEXIONES')

# Carpeta con los datos JSON
DATA_DIR = "dynamodb_data"

# Mapeo de archivos JSON a tablas y sus claves
TABLE_MAPPING = {
    "locales.json": {
        "table_name": TABLE_LOCALES,
        "pk": "local_id",
        "sk": None
    },
    "usuarios.json": {
        "table_name": TABLE_USUARIOS,
        "pk": "correo",
        "sk": None
    },
    "productos.json": {
        "table_name": TABLE_PRODUCTOS,
        "pk": "local_id",
        "sk": "nombre"
    },
    "empleados.json": {
        "table_name": TABLE_EMPLEADOS,
        "pk": "local_id",
        "sk": "dni"
    },
    "combos.json": {
        "table_name": TABLE_COMBOS,
        "pk": "local_id",
        "sk": "combo_id"
    },
    "pedidos.json": {
        "table_name": TABLE_PEDIDOS,
        "pk": "local_id",
        "sk": "pedido_id"
    },
    "ofertas.json": {
        "table_name": TABLE_OFERTAS,
        "pk": "local_id",
        "sk": "oferta_id"
    },
    "resenas.json": {
        "table_name": TABLE_RESENAS,
        "pk": "local_id",
        "sk": "resena_id"
    },
    "conexiones.json": {
        "table_name": TABLE_CONEXIONES,
        "pk": "usuario_correo",
        "sk": "pedido_id"
    }
}


def convert_float_to_decimal(obj):
    """
    Convierte float a Decimal recursivamente para compatibilidad con DynamoDB
    """
    if isinstance(obj, list):
        return [convert_float_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_float_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def get_table_keys(filename):
    """Obtiene las claves PK y SK para una tabla específica"""
    config = TABLE_MAPPING.get(filename)
    if config:
        return config["pk"], config["sk"]
    return None, None


def get_dynamodb_client():
    """
    Crea y retorna un cliente de DynamoDB usando credenciales de ~/.aws/credentials
    """
    try:
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        
        # Verificar conexión intentando listar tablas
        client = boto3.client('dynamodb', region_name=AWS_REGION)
        client.list_tables(Limit=1)
        
        return dynamodb
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'UnrecognizedClientException':
            print(f"❌ Error de credenciales: Verifica tu archivo ~/.aws/credentials")
        else:
            print(f"❌ Error al conectar con DynamoDB: {e.response['Error']['Message']}")
        return None
    except Exception as e:
        print(f"❌ Error al conectar con DynamoDB: {e}")
        return None


def table_exists(table_name):
    """Verifica si una tabla existe en DynamoDB"""
    try:
        dynamodb_client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        else:
            raise


def enable_streams_on_existing_table(table_name):
    """
    Habilita DynamoDB Streams en una tabla existente si no están habilitados
    """
    try:
        # Verificar estado actual de los streams
        response = dynamodb_client.describe_table(TableName=table_name)
        stream_spec = response['Table'].get('StreamSpecification', {})
        
        if stream_spec.get('StreamEnabled', False):
            print(f"   ✅ Streams ya están habilitados en '{table_name}'")
            return True
        
        # Habilitar streams
        print(f"   🔄 Habilitando DynamoDB Streams en '{table_name}'...")
        dynamodb_client.update_table(
            TableName=table_name,
            StreamSpecification={
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            }
        )
        
        # Esperar a que la tabla se actualice
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        
        print(f"   ✅ Streams habilitados exitosamente en '{table_name}'")
        return True
        
    except ClientError as e:
        print(f"   ⚠️  Error habilitando streams: {e.response['Error']['Message']}")
        return False


def create_table(table_name, pk_name, sk_name=None):
    """
    Crea una tabla en DynamoDB con DynamoDB Streams habilitados
    """
    print(f"   📋 Tabla '{table_name}' no existe. Creándola con Streams habilitados...")
    
    # Configuración de claves
    key_schema = [{'AttributeName': pk_name, 'KeyType': 'HASH'}]
    attribute_definitions = [{'AttributeName': pk_name, 'AttributeType': 'S'}]
    
    if sk_name:
        key_schema.append({'AttributeName': sk_name, 'KeyType': 'RANGE'})
        attribute_definitions.append({'AttributeName': sk_name, 'AttributeType': 'S'})
    
    try:
        table_config = {
            'TableName': table_name,
            'KeySchema': key_schema,
            'AttributeDefinitions': attribute_definitions,
            'BillingMode': 'PAY_PER_REQUEST',
            # 🆕 HABILITAR DYNAMODB STREAMS
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            }
        }
        
        table = dynamodb.create_table(**table_config)
        
        print(f"   ⏳ Esperando a que la tabla '{table_name}' esté activa...")
        table.wait_until_exists()

        # Habilitar TTL si es la tabla de conexiones WebSocket
        if table_name == TABLE_CONEXIONES:
            try:
                print(f"   ⏰ Habilitando TTL para auto-eliminación de conexiones antiguas...")
                dynamodb_client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print(f"   ✅ TTL habilitado en '{table_name}' (atributo: ttl)")
            except Exception as e:
                print(f"   ⚠️  No se pudo habilitar TTL: {str(e)}")
        
        print(f"   ✅ Tabla '{table_name}' creada exitosamente con Streams habilitados")
        return True
        
    except ClientError as e:
        print(f"   ❌ Error al crear tabla '{table_name}': {e.response['Error']['Message']}")
        return False


def load_json_file(filename):
    """
    Carga un archivo JSON y retorna su contenido
    """
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return convert_float_to_decimal(data)
    except FileNotFoundError:
        print(f"⚠️  Archivo no encontrado: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️  Error al decodificar JSON en {filename}: {e}")
        return None


def delete_all_items_from_table(table_name, pk_name, sk_name=None):
    """Elimina todos los items de una tabla de DynamoDB"""
    try:
        table = dynamodb.Table(table_name)
        
        print(f"   🗑️  Escaneando items en '{table_name}'...")
        
        # Escanear todos los items
        response = table.scan()
        items = response.get('Items', [])
        
        # Manejar paginación
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        if not items:
            print(f"   ℹ️  La tabla '{table_name}' ya está vacía")
            return True
        
        print(f"   🗑️  Eliminando {len(items)} items de '{table_name}'...")
        
        # Eliminar en lotes
        with table.batch_writer() as batch:
            for item in items:
                key = {pk_name: item[pk_name]}
                if sk_name:
                    key[sk_name] = item[sk_name]
                batch.delete_item(Key=key)
        
        print(f"   ✅ {len(items)} items eliminados de '{table_name}'")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            print(f"   ⚠️  La tabla '{table_name}' no existe, se creará al poblar")
            return True
        else:
            print(f"   ❌ Error al limpiar tabla: {e.response['Error']['Message']}")
            return False
    except Exception as e:
        print(f"   ❌ Error inesperado al limpiar tabla: {str(e)}")
        return False


def batch_write_items(table, items, table_name):
    """Escribe items en lotes a DynamoDB con procesamiento paralelo y retry"""
    success_count = 0
    error_count = 0
    total_items = len(items)
    
    batch_size = 25
    count_lock = Lock()
    batches = [items[i:i + batch_size] for i in range(0, total_items, batch_size)]
    
    def process_batch_with_retry(batch, max_retries=5):
        local_success = 0
        local_errors = 0
        
        for attempt in range(max_retries):
            try:
                with table.batch_writer() as batch_writer:
                    for item in batch:
                        try:
                            batch_writer.put_item(Item=item)
                            local_success += 1
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                                raise
                            else:
                                local_errors += 1
                                if local_errors <= 3:
                                    error_msg = e.response['Error']['Message']
                                    print(f"      ⚠️  Error ValidationException: {error_msg}")
                        except Exception as e:
                            local_errors += 1
                            if local_errors <= 3:
                                print(f"      ⚠️  Error inesperado: {str(e)[:100]}")
                
                return local_success, local_errors
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ProvisionedThroughputExceededException':
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random_module.uniform(0, 1)
                        time.sleep(wait_time)
                        local_success = 0
                        local_errors = 0
                        continue
                else:
                    local_errors += len(batch)
                    return 0, local_errors
        
        return local_success, local_errors
    
    try:
        num_threads = min(10, len(batches))
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(process_batch_with_retry, batch): batch for batch in batches}
            
            for future in as_completed(futures):
                try:
                    local_success, local_errors = future.result()
                    with count_lock:
                        success_count += local_success
                        error_count += local_errors
                        
                        if (success_count % 500 == 0) or (success_count + error_count >= total_items):
                            porcentaje = ((success_count + error_count) / total_items) * 100
                            print(f"      📊 Progreso: {success_count}/{total_items} ({porcentaje:.1f}%) - Errores: {error_count}")
                
                except Exception as e:
                    with count_lock:
                        error_count += len(futures[future])
                    print(f"      ⚠️  Error en lote: {str(e)[:80]}")
        
    except Exception as e:
        print(f"   ❌ Error en procesamiento paralelo: {str(e)}")
        return success_count, total_items - success_count
    
    return success_count, error_count


def ask_user_action_global():
    """
    Pregunta al usuario qué hacer con los datos existentes (aplica a todas las tablas)
    """
    auto_replace = os.getenv('AUTO_REPLACE', 'false').lower() == 'true'
    
    if auto_replace:
        print("\n   🤖 Modo automático activado: REPLACE")
        print("   ✅ Se eliminarán todos los datos existentes antes de insertar")
        return "replace"
    
    print("\n" + "=" * 60)
    print("❓ ACCIÓN GLOBAL PARA DATOS EXISTENTES")
    print("=" * 60)
    print("\nAlgunas tablas pueden contener datos existentes.")
    print("¿Qué deseas hacer con los datos en TODAS las tablas?")
    print("\n   1) Agregar datos nuevos (mantener los datos actuales)")
    print("   2) Eliminar datos existentes y reemplazar con nuevos datos")
    
    while True:
        choice = input("\n   Selecciona una opción (1/2): ").strip()
        if choice == "1":
            print("\n   ✅ Se agregarán datos nuevos manteniendo los existentes")
            return "append"
        elif choice == "2":
            print("\n   ✅ Se eliminarán todos los datos existentes antes de insertar")
            return "replace"
        else:
            print("   ⚠️  Opción inválida. Por favor selecciona 1 o 2")


def populate_table(dynamodb, filename, table_config, global_action=None):
    """Puebla una tabla de DynamoDB con datos de un archivo JSON"""
    table_name = table_config["table_name"]
    pk_name = table_config["pk"]
    sk_name = table_config["sk"]
    
    print(f"\n📤 Poblando tabla: {table_name}")
    print(f"   Archivo: {filename}")
    print(f"   Claves: PK={pk_name}" + (f", SK={sk_name}" if sk_name else ""))
    
    # Verificar si la tabla existe, si no, crearla
    if not table_exists(table_name):
        if not create_table(table_name, pk_name, sk_name):
            print(f"   ❌ No se pudo crear la tabla '{table_name}'. Saltando...")
            return False
        time.sleep(2)
    else:
        print(f"   ✅ Tabla '{table_name}' existe")
        
        # 🆕 HABILITAR STREAMS SI NO ESTÁN HABILITADOS
        enable_streams_on_existing_table(table_name)
        
        # Si hay una acción global definida y es "replace", limpiar la tabla
        if global_action == "replace":
            try:
                table = dynamodb.Table(table_name)
                response = table.scan(Limit=1)
                
                if response.get('Count', 0) > 0:
                    print(f"   🗑️  Limpiando datos existentes de '{table_name}'...")
                    if not delete_all_items_from_table(table_name, pk_name, sk_name):
                        print(f"   ❌ Error al limpiar la tabla. Saltando...")
                        return False
                else:
                    print(f"   ℹ️  La tabla '{table_name}' está vacía")
            except Exception as e:
                print(f"   ⚠️  No se pudo verificar contenido de la tabla: {e}")
        elif global_action == "append":
            print(f"   ℹ️  Agregando datos a la tabla existente")
    
    # Cargar datos del archivo
    items = load_json_file(filename)
    
    if items is None:
        return False
    
    if not isinstance(items, list):
        print(f"   ❌ El archivo debe contener un array JSON")
        return False
    
    if len(items) == 0:
        print(f"   ⚠️  El archivo está vacío, no hay datos para insertar")
        return True
    
    print(f"   📊 Total de items a insertar: {len(items)}")
    
    try:
        table = dynamodb.Table(table_name)
        success_count, error_count = batch_write_items(table, items, table_name)
        
        print(f"   ✅ Insertados exitosamente: {success_count} items")
        if error_count > 0:
            print(f"   ⚠️  Errores: {error_count} items")
        
        return error_count == 0
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"   ❌ Error de AWS: {error_code} - {error_msg}")
        return False
    except Exception as e:
        print(f"   ❌ Error inesperado: {str(e)}")
        return False


def verify_credentials():
    """
    Verifica que las credenciales de AWS estén disponibles
    """
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials is None:
            print("❌ ERROR: No se encontraron credenciales de AWS")
            print("   Configura el archivo ~/.aws/credentials con el formato:")
            print("   [default]")
            print("   aws_access_key_id=YOUR_ACCESS_KEY_ID")
            print("   aws_secret_access_key=YOUR_SECRET_ACCESS_KEY")
            print("   aws_session_token=YOUR_SESSION_TOKEN (opcional)")
            return False
        
        return True
    except Exception as e:
        print(f"❌ ERROR al verificar credenciales: {e}")
        return False


def verify_table_names():
    """
    Verifica que los nombres de las tablas estén configurados
    """
    missing_tables = []
    for filename, config in TABLE_MAPPING.items():
        if not config["table_name"]:
            missing_tables.append(filename)

    if missing_tables:
        print("⚠️  ADVERTENCIA: Algunas tablas no están configuradas en .env:")
        for filename in missing_tables:
            print(f"   - {filename}")
        print("\n   Estas tablas serán omitidas")
        return False
    return True


def main():
    """
    Función principal que ejecuta la población de todas las tablas
    """
    print("=" * 60)
    print("🚀 CHINA WOK - DATA POBLATOR (con DynamoDB Streams)")
    print("=" * 60)

    # Verificar credenciales
    if not verify_credentials():
        return

    # Verificar nombres de tablas
    verify_table_names()

    # Verificar que existe la carpeta de datos
    if not os.path.exists(DATA_DIR):
        print(f"\n❌ ERROR: La carpeta '{DATA_DIR}/' no existe")
        print("   Ejecuta primero el script DataGenerator.py")
        return

    # Conectar a DynamoDB
    print(f"\n🔌 Conectando a DynamoDB en región: {AWS_REGION}")
    dynamodb = get_dynamodb_client()

    if dynamodb is None:
        print("❌ No se pudo establecer conexión con DynamoDB")
        return

    print("✅ Conexión establecida exitosamente")

    # Preguntar acción global una sola vez
    global_action = ask_user_action_global()

    # Poblar cada tabla
    print("\n" + "=" * 60)
    print("📊 INICIANDO POBLACIÓN DE TABLAS (con Streams habilitados)")
    print("=" * 60)

    results = {}
    for filename, config in TABLE_MAPPING.items():
        if config["table_name"]:
            success = populate_table(dynamodb, filename, config, global_action)
            results[filename] = success

    # Resumen final
    print("\n" + "=" * 60)
    print("📋 RESUMEN FINAL")
    print("=" * 60)

    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful

    print(f"\n✅ Tablas pobladas exitosamente: {successful}")
    if failed > 0:
        print(f"❌ Tablas con errores: {failed}")
    
    print(f"\n🔄 DynamoDB Streams habilitados en todas las tablas")
    print(f"   Las actualizaciones se sincronizarán automáticamente con S3")

    print("\n" + "=" * 60)
    print("🎉 PROCESO COMPLETADO")
    print("=" * 60)


if __name__ == "__main__":
    main()