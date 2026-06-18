#!/bin/bash
# YTCreator Studio v3 — Lanza todos los servicios + nginx reverse proxy
# nginx (7860) -> Streamlit (7862) + Gateway API (7861)

echo "=== YTCreator Studio v3 ==="

echo "Levantando 16 microservicios..."
python run_dev.py &
RUN_DEV_PID=$!

sleep 8

echo "Levantando gateway en puerto 7861..."
python -c "
import uvicorn
from gateway import app
uvicorn.run(app, host='0.0.0.0', port=7861)
" &
GATEWAY_PID=$!

sleep 2

echo "Levantando Streamlit en puerto 7862 (interno)..."
streamlit run app.py \
    --server.port 7862 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false &
STREAMLIT_PID=$!

sleep 2

echo "Levantando nginx reverse proxy en puerto 7860..."
nginx -g "daemon off;" &
NGINX_PID=$!

echo ""
echo "=== Todo listo ==="
echo "  UI Streamlit:  https://TU-SPACE.hf.space/"
echo "  API Gateway:   https://TU-SPACE.hf.space/api/"
echo "  API Health:    https://TU-SPACE.hf.space/api/health"
echo "  Webhook n8n:   https://TU-SPACE.hf.space/api/pipeline/webhook"
echo ""

wait -n $NGINX_PID $STREAMLIT_PID $GATEWAY_PID $RUN_DEV_PID

echo "Un servicio se cayo. Apagando todo..."
kill $NGINX_PID $STREAMLIT_PID $GATEWAY_PID $RUN_DEV_PID 2>/dev/null
