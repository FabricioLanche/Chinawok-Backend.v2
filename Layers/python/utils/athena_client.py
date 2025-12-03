import boto3
import time
import os
from typing import List, Dict, Any

class AthenaQueryExecutor:
    def __init__(self):
        # Boto3 lee automáticamente de ~/.aws/config y ~/.aws/credentials
        # Si no encuentra región, usa us-east-1 por defecto
        session = boto3.Session()
        region = session.region_name or os.environ.get('AWS_REGION', 'us-east-1')
        
        self.client = boto3.client('athena', region_name=region)
        
        # Leer variables de entorno con valores por defecto seguros
        self.database = os.environ.get('ATHENA_DATABASE', 'chinawok_analytics')
        
        # Construir la URI completa de S3 a partir del path
        output_path = os.environ.get('S3_BUCKET_NAME') + '/athena-results/'
        # Si ya comienza con s3://, usar tal cual; si no, agregar el prefijo
        if output_path.startswith('s3://'):
            self.output_location = output_path
        else:
            # Remover posibles barras iniciales y asegurar barra final
            output_path = output_path.strip('/')
            self.output_location = f's3://{output_path}/'
        
        self.workgroup = 'primary'
        
        print(f"Athena Client inicializado - Region: {region}, Database: {self.database}, Workgroup: {self.workgroup}")
        print(f"Output Location: {self.output_location}")
    
    def execute_query(self, query_string: str) -> List[Dict[str, Any]]:
        """Ejecuta una consulta en Athena y retorna los resultados"""
        try:
            # Iniciar ejecución de consulta
            response = self.client.start_query_execution(
                QueryString=query_string,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location},
                WorkGroup=self.workgroup
            )
            
            query_execution_id = response['QueryExecutionId']
            print(f"Query iniciada: {query_execution_id}")
            
            # Esperar a que termine la ejecución
            self._wait_for_query_completion(query_execution_id)
            
            # Obtener resultados
            results = self._get_query_results(query_execution_id)
            return results
            
        except Exception as e:
            print(f"Error ejecutando query en Athena: {str(e)}")
            raise
    
    def _wait_for_query_completion(self, query_execution_id: str, max_attempts: int = 60):
        """Espera a que la query termine de ejecutarse"""
        for _ in range(max_attempts):
            response = self.client.get_query_execution(QueryExecutionId=query_execution_id)
            status = response['QueryExecution']['Status']['State']
            
            print(f"Estado de query {query_execution_id}: {status}")
            
            if status == 'SUCCEEDED':
                return True
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Query falló con estado: {status}. Razón: {reason}")
            
            time.sleep(2)  # Esperar 2 segundos
        
        raise Exception('Timeout esperando resultado de query')
    
    def _get_query_results(self, query_execution_id: str) -> List[Dict[str, Any]]:
        """Obtiene los resultados de la query y los convierte a JSON"""
        response = self.client.get_query_results(QueryExecutionId=query_execution_id)
        
        # Extraer nombres de columnas
        columns = [col['Name'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        
        # Extraer filas (saltar la primera que es el header)
        rows = response['ResultSet']['Rows'][1:]
        
        # Convertir a lista de diccionarios
        results = []
        for row in rows:
            row_dict = {}
            for i, col_name in enumerate(columns):
                row_dict[col_name] = row['Data'][i].get('VarCharValue')
            results.append(row_dict)
        
        return results
