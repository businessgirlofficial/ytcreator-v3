#!/bin/bash
# YTCreator Studio v3 — Lanza todos los servicios
# Orden: 16 microservicios → gateway → Streamlit

echo "=== YTCreator Studio v3 ==="
echo "Levantando 16 microservicios..."
python run_dev.py &
RUN_DEV_PID=$!

# Esperar a que los agentes arranquen
sleep 8

echo "Levantando gateway en puerto 7861..."
python -c "
import uvicorn
from gateway import app
uvicorn.run(app, host='0.0.0.0', port=7861)
" &
GATEWAY_PID=$!

sleep 2

echo "Levantando Streamlit en puerto 7860..."
streamlit run app.py \
    --server.port 7860 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS true \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false

# Si Streamlit se cae, matar todo
kill $RUN_DEV_PID $GATEWAY_PID 2>/dev/null
