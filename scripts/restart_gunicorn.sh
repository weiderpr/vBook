#!/bin/bash

# Configuration
APP_DIR="/root/verticebook"
VENV_BIN="$APP_DIR/.venv/bin"
GUNICORN_BIN="$VENV_BIN/gunicorn"
PORT=8000
LOG_FILE="$APP_DIR/server.log"
ERROR_LOG="$APP_DIR/server.error.log"

echo "Reinicio cirúrgico do Gunicorn para VérticeBook..."

# 1. Identificar processos do verticebook
PIDS=$(ps -ef | grep "$GUNICORN_BIN" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo "Finalizando processos antigos: $PIDS"
    kill -9 $PIDS
    sleep 2
else
    echo "Nenhum processo antigo encontrado."
fi

# 2. Verificar se a porta 8000 ficou livre
if netstat -tpln | grep ":$PORT " > /dev/null; then
    echo "ERRO: A porta $PORT ainda está ocupada. Verifique manualmente."
    exit 1
fi

# 3. Iniciar Gunicorn com logs habilitados
echo "Iniciando Gunicorn na porta $PORT..."
$GUNICORN_BIN verticebook.wsgi:application \
    --bind 127.0.0.1:$PORT \
    --workers 3 \
    --daemon \
    --access-logfile "$LOG_FILE" \
    --error-logfile "$ERROR_LOG" \
    --capture-output \
    --enable-stdio-inheritance

if [ $? -eq 0 ]; then
    echo "Gunicorn iniciado com sucesso!"
    echo "Logs disponíveis em: $ERROR_LOG"
else
    echo "FALHA ao iniciar o Gunicorn."
    exit 1
fi
