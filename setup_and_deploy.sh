#!/bin/bash

# Aumentar memoria de Node.js para Serverless Framework
export NODE_OPTIONS="--max-old-space-size=4096"

# Colores para los logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
log_success() { echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"; }
log_error() { echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"; }
log_warning() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  $1${NC}"; }
log_info() { echo -e "${CYAN}[$(date +'%H:%M:%S')] ℹ️  $1${NC}"; }

# Banner
echo ""
echo "═════════════════════════════════════════════════════════════"
echo "         🥡 CHINAWOK BACKEND - DEPLOY MAESTRO 🥡           "
echo "═════════════════════════════════════════════════════════════"
echo ""

# Verificar archivo .env
if [ ! -f .env ]; then
    log_error "No se encontró el archivo .env"
    log_info "Copia .env.example a .env y configúralo:"
    log_info "  cp .env.example .env"
    log_info "  nano .env"
    exit 1
fi

log_success "Archivo .env encontrado"

# Verificar e instalar Serverless Framework
log "Verificando Serverless Framework..."
if ! command -v serverless &> /dev/null; then
    log_warning "Serverless Framework no está instalado"
    log "Instalando Serverless Framework globalmente..."
    
    # Verificar si npm está instalado
    if ! command -v npm &> /dev/null; then
        log_error "npm no está instalado. Instálalo primero:"
        log_error "  sudo apt update && sudo apt install -y nodejs npm"
        exit 1
    fi
    
    # Instalar serverless
    sudo npm install -g serverless
    
    if [ $? -eq 0 ]; then
        log_success "Serverless Framework instalado correctamente"
    else
        log_error "Error al instalar Serverless Framework"
        exit 1
    fi
else
    log_success "Serverless Framework encontrado: $(serverless --version | head -n1)"
fi

# Verificar credenciales AWS
log "Verificando credenciales AWS..."

if [ -f ~/.aws/credentials ]; then
    log_success "Archivo de credenciales AWS encontrado: ~/.aws/credentials"
    
    # Verificar si el perfil default existe
    if grep -q "\[default\]" ~/.aws/credentials; then
        log_success "Perfil [default] encontrado"
    else
        log_warning "Perfil [default] no encontrado. Usando credenciales del entorno."
    fi
else
    log_warning "Archivo ~/.aws/credentials no encontrado"
    log_warning "Buscando credenciales en variables de entorno..."
    
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        log_success "Credenciales AWS encontradas en variables de entorno"
    else
        log_error "No se encontraron credenciales de AWS"
        log_error "Por favor, configura tus credenciales en ~/.aws/credentials o en variables de entorno"
        exit 1
    fi
fi

# Verificar conectividad con AWS
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "No se pudo conectar con AWS. Verifica tus credenciales."
    exit 1
fi
log_success "Credenciales AWS verificadas"

# Función para construir Lambda Layer
build_layer() {
    log "🔧 Construyendo Lambda Layer compartido..."
    
    cd Layers || exit 1
    
    # Limpiar build anterior completamente
    log "🗑️  Limpiando estructura anterior del layer..."
    rm -rf python/lib
    rm -rf python/libs
    rm -rf python-dependencies
    rm -rf .serverless
    
    # Crear estructura correcta para Lambda Layer
    mkdir -p python/lib/python3.12/site-packages
    
    # IMPORTANTE: Asegurar que utils existe antes de continuar
    if [ ! -d "python/utils" ]; then
        log_error "❌ ERROR: python/utils/ no existe"
        exit 1
    fi
    
    # Instalar dependencias de terceros
    log "📦 Instalando dependencias de terceros..."
    pip install -r requirements.txt \
        -t python/lib/python3.12/site-packages \
        --quiet \
        --upgrade \
        --no-cache-dir
    
    if [ $? -ne 0 ]; then
        log_error "Error al instalar dependencias del layer"
        exit 1
    fi
    
    log_success "✅ Dependencias instaladas en python/lib/python3.12/site-packages/"
    
    # Verificar estructura final
    log "🔍 Verificando estructura del layer..."
    
    # Verificar que utils tiene archivos
    utils_files=$(find python/utils -type f -name "*.py" | wc -l)
    log_info "   📂 python/utils/ contiene $utils_files archivos .py"
    
    if [ "$utils_files" -eq 0 ]; then
        log_error "❌ ERROR: python/utils/ no contiene archivos .py"
        exit 1
    fi
    
    # Listar archivos de utils para debug
    log_info "   📋 Archivos en python/utils/:"
    ls -1 python/utils/*.py | while read file; do
        log_info "      - $(basename $file)"
    done
    
    # Verificar PyJWT
    if [ -d "python/lib/python3.12/site-packages/jwt" ]; then
        log_info "   ✅ PyJWT instalado correctamente"
    else
        log_warning "   ⚠️  PyJWT NO se instaló correctamente"
    fi
    
    cd ..
    log_success "Lambda Layer construido correctamente"
}

# 🆕 NUEVA FUNCIÓN: Obtener ARNs de streams y actualizar .env
get_stream_arns() {
    log ""
    log "═══════════════════════════════════════════════════════════"
    log "🔍 Obteniendo ARNs de DynamoDB Streams"
    log "═══════════════════════════════════════════════════════════"
    
    # Leer nombres de tablas del .env
    source .env
    
    declare -A tables=(
        ["LOCALES"]="$TABLE_LOCALES"
        ["PRODUCTOS"]="$TABLE_PRODUCTOS"
        ["EMPLEADOS"]="$TABLE_EMPLEADOS"
        ["COMBOS"]="$TABLE_COMBOS"
        ["PEDIDOS"]="$TABLE_PEDIDOS"
        ["OFERTAS"]="$TABLE_OFERTAS"
        ["RESENAS"]="$TABLE_RESENAS"
    )
    
    # Crear archivo temporal para nuevas variables
    temp_env=$(mktemp)
    
    # Copiar .env existente
    cp .env "$temp_env"
    
    # Remover variables antiguas de stream si existen
    sed -i '/^STREAM_ARN_/d' "$temp_env"
    
    log_info "Consultando ARNs de streams en AWS..."
    
    for key in "${!tables[@]}"; do
        table_name="${tables[$key]}"
        
        if [ -z "$table_name" ]; then
            log_warning "⚠️  Tabla $key no está configurada, saltando..."
            continue
        fi
        
        log "   📊 Obteniendo stream ARN para: $table_name"
        
        # Obtener el ARN del stream usando AWS CLI
        stream_arn=$(aws dynamodb describe-table \
            --table-name "$table_name" \
            --query 'Table.LatestStreamArn' \
            --output text 2>/dev/null)
        
        if [ $? -eq 0 ] && [ "$stream_arn" != "None" ] && [ -n "$stream_arn" ]; then
            log_success "   ✅ Stream ARN obtenido: ${stream_arn:0:60}..."
            
            # Agregar al archivo temporal
            echo "STREAM_ARN_${key}=${stream_arn}" >> "$temp_env"
        else
            log_warning "   ⚠️  No se pudo obtener stream ARN para $table_name"
            log_warning "   ℹ️  Asegúrate de que la tabla existe y tiene streams habilitados"
        fi
    done
    
    # Reemplazar .env con el nuevo archivo
    mv "$temp_env" .env
    
    log_success "✅ ARNs de streams guardados en .env"
    log ""
}

# Función para habilitar DynamoDB Streams
enable_dynamodb_streams() {
    log ""
    log "🔄 Verificando y habilitando DynamoDB Streams..."
    log "────────────────────────────────────────────────────────────"
    
    cd DataGenerator || exit 1
    
    # Verificar si el script existe
    if [ ! -f enable_streams.py ]; then
        log_warning "Script enable_streams.py no encontrado"
        log_info "Los Streams se habilitarán al crear las tablas con DataPoblator"
        cd ..
        return 0
    fi
    
    # Ejecutar el script de habilitación de streams
    python3 enable_streams.py
    
    local exit_code=$?
    cd ..
    
    if [ $exit_code -eq 0 ]; then
        log_success "Verificación de Streams completada"
        return 0
    else
        log_warning "Hubo algunos problemas al verificar Streams"
        log_info "Continuando con el proceso..."
        return 0
    fi
}

# Función para generar y poblar datos
populate_data() {
    log ""
    log "═══════════════════════════════════════════════════════════"
    log "📊 Generación y población de datos"
    log "═══════════════════════════════════════════════════════════"
    
    cd DataGenerator || exit 1
    
    # Instalar dependencias de Python del DataGenerator
    log "📦 Instalando dependencias de DataGenerator..."
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt --quiet
        
        if [ $? -eq 0 ]; then
            log_success "Dependencias de DataGenerator instaladas correctamente"
        else
            log_error "Error al instalar dependencias de DataGenerator"
            cd ..
            exit 1
        fi
    else
        log_error "Archivo requirements.txt no encontrado en DataGenerator/"
        cd ..
        exit 1
    fi
    
    # Verificar existencia de datos generados
    log "🔍 Verificando existencia de datos generados..."
    
    if [ -d "dynamodb_data" ] && [ "$(ls -A dynamodb_data)" ]; then
        log_warning "La carpeta dynamodb_data ya existe y contiene archivos"
        read -p "¿Deseas regenerar los datos? (s/n): " respuesta
        
        if [ "$respuesta" = "s" ] || [ "$respuesta" = "S" ]; then
            log "🗑️  Eliminando datos anteriores..."
            rm -rf dynamodb_data
            log_success "Datos anteriores eliminados"
        else
            log "⏭️  Saltando generación de datos. Usando datos existentes."
        fi
    fi
    
    # Generar datos si no existen
    if [ ! -d "dynamodb_data" ] || [ ! "$(ls -A dynamodb_data)" ]; then
        log "📝 Generando nuevos datos..."
        log "────────────────────────────────────────────────────────────"
        
        python3 DataGenerator.py
        
        if [ $? -eq 0 ]; then
            log "────────────────────────────────────────────────────────────"
            log_success "Datos generados correctamente en dynamodb_data/"
        else
            log_error "Error al generar datos"
            cd ..
            exit 1
        fi
    else
        log_success "Usando datos existentes en dynamodb_data/"
    fi
    
    # Poblar DynamoDB
    log "🗄️  Poblando DynamoDB..."
    log "────────────────────────────────────────────────────────────"
    
    python3 DataPoblator.py
    
    if [ $? -eq 0 ]; then
        log "────────────────────────────────────────────────────────────"
        log_success "Datos poblados correctamente en DynamoDB"
        log ""
        log "📊 Resumen de datos:"
        log "   ✅ Datos generados en dynamodb_data/"
        log "   ✅ Datos poblados en DynamoDB"
        log "   ✅ DynamoDB Streams habilitados en todas las tablas"
    else
        log_error "Error al poblar DynamoDB"
        cd ..
        exit 1
    fi
    
    cd ..
    
    # 🆕 HABILITAR STREAMS DESPUÉS DE POBLAR DATOS
    log ""
    log "═══════════════════════════════════════════════════════════"
    log "🔄 Post-configuración: Verificando Streams"
    log "═══════════════════════════════════════════════════════════"
    enable_dynamodb_streams
    
    # 🆕 OBTENER ARNs DE STREAMS
    get_stream_arns
}

# Función para mostrar URLs de los servicios desplegados
show_endpoints() {
    log ""
    log "═══════════════════════════════════════════════════════"
    log "         📡 ENDPOINTS DE MICROSERVICIOS                "
    log "═══════════════════════════════════════════════════════"
    log ""
    
    # Arrays de servicios
    declare -A service_dirs=(
        ["👤 Usuarios"]="Microservicios/Usuarios"
        ["🏪 Locales (incluye Analítica)"]="Microservicios/Locales"
        ["👨‍🍳 Empleados"]="Microservicios/Empleados"
        ["🍜 Pedidos (incluye Workflow)"]="Microservicios/Pedidos"
    )
    
    # Obtener región de AWS
    AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    
    # Obtener endpoints usando AWS CLI
    for service_name in "${!service_dirs[@]}"; do
        service_path="${service_dirs[$service_name]}"
        
        if [ -d "$service_path" ]; then
            # Extraer el nombre del servicio del serverless.yml
            cd "$service_path" || continue
            sls_service=$(grep "^service:" serverless.yml | awk '{print $2}')
            
            if [ -n "$sls_service" ]; then
                # Buscar API Gateway usando AWS CLI
                api_id=$(aws apigateway get-rest-apis --region "$AWS_REGION" --query "items[?name=='dev-$sls_service'].id" --output text 2>/dev/null)
                
                if [ -n "$api_id" ] && [ "$api_id" != "None" ]; then
                    endpoint="https://${api_id}.execute-api.${AWS_REGION}.amazonaws.com/dev"
                    log_success "$service_name"
                    log "   URL: $endpoint"
                else
                    log_warning "$service_name - API no encontrada en AWS"
                fi
            else
                log_warning "$service_name - No se pudo leer serverless.yml"
            fi
            
            cd - > /dev/null || exit 1
        fi
    done
    
    log ""
}

# Función para verificar/crear bucket S3
ensure_s3_bucket() {
    local bucket_name="${1:-chinawok-data}"
    
    log "🪣 Verificando bucket S3: $bucket_name"
    
    # Verificar si el bucket existe y es accesible
    if aws s3 ls "s3://$bucket_name" >/dev/null 2>&1; then
        log_success "✅ Bucket '$bucket_name' ya existe y es accesible"
        
        # Verificar permisos de escritura
        log "🔍 Verificando permisos de escritura..."
        if echo "test" | aws s3 cp - "s3://$bucket_name/.test-write-permission" 2>/dev/null; then
            aws s3 rm "s3://$bucket_name/.test-write-permission" >/dev/null 2>&1
            log_success "✅ Permisos de escritura confirmados"
            return 0
        else
            log_error "❌ No tienes permisos de escritura en '$bucket_name'"
            return 1
        fi
    fi
    
    # El bucket no existe, intentar crearlo
    log "📦 Bucket no existe, intentando crear..."
    
    if aws s3 mb "s3://$bucket_name" --region us-east-1 2>&1; then
        log_success "✅ Bucket '$bucket_name' creado exitosamente"
        
        # Configurar bucket
        configure_bucket "$bucket_name"
        return 0
    else
        # Si falla por nombre duplicado, intentar con UUID corto
        log_warning "⚠️  Nombre '$bucket_name' no disponible"
        
        # Generar UUID corto (8 caracteres)
        local uuid_short=$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 8 | head -n 1)
        local bucket_with_uuid="${bucket_name}-${uuid_short}"
        
        log_info "💡 Intentando con nombre único: $bucket_with_uuid"
        
        if aws s3 mb "s3://$bucket_with_uuid" --region us-east-1 2>&1; then
            log_success "✅ Bucket '$bucket_with_uuid' creado exitosamente"
            
            # Actualizar .env con el nuevo nombre
            log "📝 Actualizando .env con el nuevo nombre de bucket..."
            sed -i "s/^S3_BUCKET_NAME=.*/S3_BUCKET_NAME=$bucket_with_uuid/" .env
            log_success "✅ .env actualizado con S3_BUCKET_NAME=$bucket_with_uuid"
            
            # Configurar bucket
            configure_bucket "$bucket_with_uuid"
            return 0
        else
            log_error "❌ Error al crear bucket con UUID"
            
            # Último intento: usar Account ID
            local account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
            if [ -n "$account_id" ]; then
                local bucket_with_account="chinawok-data-${account_id}"
                log_info "💡 Último intento con Account ID: $bucket_with_account"
                
                if aws s3 mb "s3://$bucket_with_account" --region us-east-1 2>&1; then
                    log_success "✅ Bucket '$bucket_with_account' creado exitosamente"
                    
                    # Actualizar .env
                    sed -i "s/^S3_BUCKET_NAME=.*/S3_BUCKET_NAME=$bucket_with_account/" .env
                    log_success "✅ .env actualizado con S3_BUCKET_NAME=$bucket_with_account"
                    
                    # Configurar bucket
                    configure_bucket "$bucket_with_account"
                    return 0
                fi
            fi
            
            log_error "❌ No se pudo crear ningún bucket"
            return 1
        fi
    fi
}

# Función auxiliar para configurar un bucket S3
configure_bucket() {
    local bucket_name="$1"
    
    log "🔄 Configurando bucket '$bucket_name'..."
    
    # Configurar versionado
    aws s3api put-bucket-versioning \
        --bucket "$bucket_name" \
        --versioning-configuration Status=Enabled \
        --region us-east-1 2>/dev/null
    
    # Configurar bloqueo de acceso público
    aws s3api put-public-access-block \
        --bucket "$bucket_name" \
        --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region us-east-1 2>/dev/null
    
    # Configurar reglas de ciclo de vida
    cat > /tmp/lifecycle-policy.json << 'EOF'
{
  "Rules": [
    {
      "Id": "DeleteOldIngestionData",
      "Status": "Enabled",
      "Filter": {"Prefix": "data-ingestion/"},
      "Expiration": {"Days": 90}
    },
    {
      "Id": "DeleteOldAthenaResults",
      "Status": "Enabled",
      "Filter": {"Prefix": "athena-results/"},
      "Expiration": {"Days": 30}
    }
  ]
}
EOF
    
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "$bucket_name" \
        --lifecycle-configuration file:///tmp/lifecycle-policy.json \
        --region us-east-1 2>/dev/null
    
    rm -f /tmp/lifecycle-policy.json
    
    log_success "✅ Bucket configurado completamente"
}

# Función para ejecutar crawler inicial y esperar completación
initialize_glue_crawler() {
    log ""
    log "🔍 Inicializando Glue Crawler para mapear schemas..."
    
    # Leer variables del .env
    source .env
    
    local crawler_name="${GLUE_CRAWLER_NAME:-chinawok-analytics-crawler}"
    local database_name="${ATHENA_DATABASE:-chinawok_analytics}"
    
    # Verificar si el crawler ya existe
    if aws glue get-crawler --name "$crawler_name" &>/dev/null; then
        log_info "Crawler '$crawler_name' ya existe"
    else
        log "📝 Creando crawler '$crawler_name'..."
        
        # Crear el crawler
        aws glue create-crawler \
            --name "$crawler_name" \
            --role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/LabRole" \
            --database-name "$database_name" \
            --targets "{\"S3Targets\":[{\"Path\":\"s3://${S3_BUCKET_NAME}/${S3_INGESTION_PREFIX}/\"}]}" \
            --description "Crawler para mapear schemas de datos DynamoDB" \
            --schema-change-policy '{"UpdateBehavior":"UPDATE_IN_DATABASE","DeleteBehavior":"DEPRECATE_IN_DATABASE"}' \
            --recrawl-policy '{"RecrawlBehavior":"CRAWL_EVERYTHING"}' \
            --region us-east-1 2>/dev/null
        
        if [ $? -eq 0 ]; then
            log_success "✅ Crawler creado exitosamente"
        else
            log_warning "⚠️  No se pudo crear el crawler (puede que ya exista)"
        fi
    fi
    
    # Ejecutar el crawler
    log "🚀 Ejecutando crawler para mapear schemas iniciales..."
    
    aws glue start-crawler --name "$crawler_name" --region us-east-1 2>/dev/null
    
    if [ $? -eq 0 ]; then
        log_success "✅ Crawler iniciado"
        
        # Esperar a que complete (máximo 5 minutos)
        log "⏳ Esperando completación del crawler (esto puede tardar 1-2 minutos)..."
        
        local max_attempts=30
        local attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            sleep 10
            attempt=$((attempt + 1))
            
            # Verificar estado del crawler
            local state=$(aws glue get-crawler --name "$crawler_name" --query 'Crawler.State' --output text 2>/dev/null)
            
            if [ "$state" == "READY" ]; then
                # Verificar si fue exitoso
                local last_status=$(aws glue get-crawler --name "$crawler_name" --query 'Crawler.LastCrawl.Status' --output text 2>/dev/null)
                
                if [ "$last_status" == "SUCCEEDED" ]; then
                    log_success "✅ Crawler completado exitosamente"
                    
                    # Mostrar tablas creadas
                    log_info "📊 Verificando tablas creadas en Glue..."
                    local tables=$(aws glue get-tables --database-name "$database_name" --query 'TableList[].Name' --output text 2>/dev/null)
                    
                    if [ -n "$tables" ]; then
                        log_success "✅ Tablas mapeadas: $tables"
                    fi
                    
                    return 0
                else
                    log_error "❌ Crawler falló: $last_status"
                    return 1
                fi
            fi
            
            echo -n "."
        done
        
        log_warning "⚠️  Crawler aún ejecutándose después de 5 minutos"
        log_info "Puedes verificar el estado manualmente en la consola de AWS Glue"
        return 0
    else
        log_warning "⚠️  Crawler ya está en ejecución o hubo un error"
        return 0
    fi
}

# Menú de opciones
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  📋 OPCIONES DE DESPLIEGUE                           "
echo "═══════════════════════════════════════════════════════"
echo "  1) 🚀 Despliegue completo (infraestructura + apps)  "
echo "  2) 🏗️  Solo infraestructura (S3 + datos + Glue)     "
echo "  3) ⚙️  Solo microservicios (Lambda + APIs)          "
echo "  4) 🗑️  Eliminar todo (remove)                       "
echo "═══════════════════════════════════════════════════════"
echo ""
read -p "Selecciona una opción (1-4): " opcion

case $opcion in
    1)
        log_info "Iniciando despliegue completo..."
        
        # Paso 1: Verificar/crear bucket S3
        log ""
        log "═══════════════════════════════════════════════════════"
        log "🪣 PASO 1/6: Verificando infraestructura S3"
        log "═══════════════════════════════════════════════════════"
        
        # Leer nombre del bucket del .env
        BUCKET_NAME=$(grep '^S3_BUCKET_NAME=' .env | cut -d '=' -f2)
        BUCKET_NAME=${BUCKET_NAME:-chinawok-data}
        
        if ! ensure_s3_bucket "$BUCKET_NAME"; then
            log_error "No se pudo configurar el bucket S3"
            exit 1
        fi
        
        # Paso 2: Construir Lambda Layer
        log ""
        log "═══════════════════════════════════════════════════════"
        log "🔧 PASO 2/6: Construyendo Lambda Layer compartido"
        log "═══════════════════════════════════════════════════════"
        build_layer
        
        # Paso 3: Poblar datos (incluye habilitación de Streams y obtención de ARNs)
        populate_data
        
        # Paso 4: Despliegue de microservicios SECUENCIAL
        log ""
        log "═══════════════════════════════════════════════════════"
        log "⚙️  PASO 4/6: Despliegue secuencial de microservicios"
        log "═══════════════════════════════════════════════════════"
        log_info "💡 Desplegando servicios uno por uno para evitar sobrecarga"
        log ""
        
        # Array de servicios en orden de dependencia (solo nombres de servicio)
        declare -a services=(
            "shared-layer:🔧 Lambda Layer"
            "usuarios:👤 Usuarios"
            "locales:🏪 Locales"
            "empleados:👨‍🍳 Empleados"
            "pedidos:🍜 Pedidos"
        )
        
        deploy_failed=0
        
        for service_info in "${services[@]}"; do
            IFS=':' read -r service_name service_label <<< "$service_info"
            
            log ""
            log "───────────────────────────────────────────────────"
            log "📦 Desplegando: $service_label"
            log "───────────────────────────────────────────────────"
            
            # Construir layer si es necesario
            if [ "$service_name" == "shared-layer" ]; then
                build_layer
            fi
            
            # Desplegar usando serverless compose con --service específico
            serverless deploy --service="$service_name" --stage dev --verbose
            
            if [ $? -eq 0 ]; then
                log_success "✅ $service_label desplegado correctamente"
                
                # Pausa de recuperación para t3.micro (15 segundos)
                log_info "⏸️  Pausa de 15s para recuperación de recursos..."
                sleep 15
            else
                log_error "❌ Error al desplegar $service_label"
                deploy_failed=1
                break
            fi
        done
        
        if [ $deploy_failed -eq 0 ]; then
            log_success "🎉 Todos los microservicios desplegados exitosamente"

            # Paso 5: Inicializar Glue Crawler
            log ""
            log "═══════════════════════════════════════════════════════"
            log "🔍 PASO 5/5: Inicializando Glue Crawler"
            log "═══════════════════════════════════════════════════════"
            
            initialize_glue_crawler
            
            # Mostrar endpoints
            show_endpoints
            
            # Mostrar resumen de Streams
            log ""
            log "═══════════════════════════════════════════════════════"
            log "🔄 Estado de DynamoDB Streams"
            log "═══════════════════════════════════════════════════════"
            log_info "✅ Streams habilitados en todas las tablas"
            log_info "✅ Lambda streamProcessor desplegado"
            log_info "✅ Glue Crawler ejecutado - Schemas mapeados"
            log_info "📊 Sistema de analítica en tiempo real ACTIVO"
            log_info "🎯 Athena listo para consultas desde el minuto 1"
        else
            log_error "Error en despliegue de microservicios"
            log_error "Puedes intentar desplegar manualmente el servicio que falló"
            exit 1
        fi
        ;;
        
    2)
        log_info "Desplegando solo infraestructura de datos..."
        
        # Paso 1: Verificar/crear bucket S3
        log ""
        log "═══════════════════════════════════════════════════════"
        log "🪣 PASO 1/3: Verificando infraestructura S3"
        log "═══════════════════════════════════════════════════════"
        
        BUCKET_NAME=$(grep '^S3_BUCKET_NAME=' .env | cut -d '=' -f2)
        BUCKET_NAME=${BUCKET_NAME:-chinawok-data}
        
        if ! ensure_s3_bucket "$BUCKET_NAME"; then
            log_error "No se pudo configurar el bucket S3"
            exit 1
        fi
        
        # Paso 2: Poblar datos (incluye habilitación de Streams y obtención de ARNs)
        log ""
        log "═══════════════════════════════════════════════════════"
        log "📊 PASO 2/3: Poblando datos y configurando Streams"
        log "═══════════════════════════════════════════════════════"
        populate_data
        
        # Paso 3: Inicializar Glue Crawler
        log ""
        log "═══════════════════════════════════════════════════════"
        log "🔍 PASO 3/3: Inicializando Glue Crawler"
        log "═══════════════════════════════════════════════════════"
        initialize_glue_crawler
        
        log_success "✨ Infraestructura de datos lista"
        log_info "📊 Datos poblados con Streams habilitados"
        log_info "🎯 Glue Crawler ejecutado - Athena listo"
        ;;
    3)
        log_info "Desplegando microservicios secuencialmente..."
        
        # Array de servicios en orden de dependencia (solo nombres de servicio)
        declare -a services=(
            "shared-layer:🔧 Lambda Layer"
            "usuarios:👤 Usuarios"
            "locales:🏪 Locales"
            "empleados:👨‍🍳 Empleados"
            "pedidos:🍜 Pedidos"
        )
        
        deploy_failed=0
        
        for service_info in "${services[@]}"; do
            IFS=':' read -r service_name service_label <<< "$service_info"
            
            log ""
            log "═══════════════════════════════════════════════════════"
            log "📦 Desplegando: $service_label"
            log "═══════════════════════════════════════════════════════"
            
            # Construir layer si es necesario
            if [ "$service_name" == "shared-layer" ]; then
                build_layer
            fi
            
            # Desplegar usando serverless compose con --service específico
            serverless deploy --service="$service_name" --stage dev --verbose
            
            if [ $? -eq 0 ]; then
                log_success "✅ $service_label desplegado correctamente"
                
                # Pausa de recuperación (15 segundos)
                if [ "$service_name" != "pedidos" ]; then
                    log_info "⏸️  Pausa de 15s para recuperación de recursos..."
                    sleep 15
                fi
            else
                log_error "❌ Error al desplegar $service_label"
                deploy_failed=1
                break
            fi
        done
        
        if [ $deploy_failed -eq 0 ]; then
            log_success "🎉 Todos los microservicios desplegados exitosamente"
            show_endpoints
        else
            log_error "Error en despliegue de microservicios"
            exit 1
        fi
        ;;
    4)
        log_warning "⚠️  ADVERTENCIA: Esto eliminará TODOS los recursos"
        read -p "¿Estás seguro? (s/n): " confirmar
        if [ "$confirmar" = "s" ] || [ "$confirmar" = "S" ]; then
            log "Eliminando recursos..."
            serverless remove
            
            if [ $? -eq 0 ]; then
                log_success "Recursos eliminados exitosamente"
            else
                log_error "Error al eliminar recursos"
                exit 1
            fi
        else
            log_info "Operación cancelada"
        fi
        ;;
        
    *)
        log_error "Opción inválida"
        exit 1
        ;;
esac

echo ""
log_success "✨ Operación completada"
echo ""