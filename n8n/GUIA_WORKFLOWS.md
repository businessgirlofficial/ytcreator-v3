# Guia de Workflows n8n — YTCreator Studio v3

## URLs importantes

- **API YTCreator**: `https://businessgirlofficial-ytcreator-v3.hf.space`
- **API Health**: `https://businessgirlofficial-ytcreator-v3.hf.space/api/health`
- **n8n**: `https://businessgirlofficial-ytcreator-n8n.hf.space`

Reemplaza `businessgirlofficial` con tu usuario de HF si es diferente.

## Importar workflows (rapido)

Los 3 workflows estan listos como JSON importable:

1. `workflow_1_nuevo_video.json` — trigger manual via webhook
2. `workflow_2_pipeline_completado.json` — callback cuando el pipeline termina
3. `workflow_3_video_diario.json` — cron diario a las 8am

**Para importar:** en n8n ve a Settings > Import from File y selecciona cada JSON.

> **Importante:** despues de importar, edita los URLs en los nodos HTTP Request
> si tu Space tiene un nombre diferente a `businessgirlofficial-ytcreator-v3`.

---

## Workflow 1: "Nuevo Video" (trigger manual)

### Nodos:

1. **Webhook Trigger** (POST)
   - Metodo: POST
   - Path: `/webhook/nuevo-video`
   - Body esperado: `{"nicho": "finanzas personales", "canal": "MiCanal"}`

2. **HTTP Request** (POST al API)
   - URL: `https://TU-SPACE.hf.space/api/pipeline/webhook`
   - Metodo: POST
   - Body:
     ```json
     {
       "nicho": "{{$json.nicho}}",
       "canal": "{{$json.canal}}",
       "callback_url": "https://TU-N8N-SPACE.hf.space/webhook/pipeline-completado"
     }
     ```
   - Respuesta esperada: `{"proyecto_id": "proy_xxxx", "estado": "iniciado"}`

3. **Respond to Webhook**
   - Responder con: `{"mensaje": "Pipeline iniciado", "proyecto_id": "{{$json.proyecto_id}}"}`

### Para probar:
```bash
curl -X POST https://TU-N8N-SPACE.hf.space/webhook/nuevo-video \
  -H "Content-Type: application/json" \
  -d '{"nicho": "finanzas personales", "canal": "MiCanal"}'
```

---

## Workflow 2: "Pipeline Completado" (callback)

### Nodos:

1. **Webhook Trigger** (POST)
   - Path: `/webhook/pipeline-completado`
   - Body esperado del API:
     ```json
     {
       "proyecto_id": "proy_xxxx",
       "estado": "completado",
       "video_final_path": "/data/proyectos/xxx/output/final.mp4"
     }
     ```

2. **IF** (condicion)
   - Condicion: `{{$json.estado}}` es igual a `completado`

3. **True → Telegram / Email**
   - Mensaje: "Video listo! Proyecto: {{$json.proyecto_id}}"
   - Link de descarga: `https://TU-SPACE.hf.space/api/download/{{$json.proyecto_id}}/final`

4. **False → Telegram / Email**
   - Mensaje: "Error en pipeline: {{$json.error}}"

### Configurar Telegram (opcional):
1. Crea un bot con @BotFather en Telegram
2. Obtiene el token del bot
3. Envia un mensaje al bot para obtener tu chat_id
4. En n8n: agrega credencial Telegram con el token
5. Usa el nodo "Telegram" con chat_id y el mensaje

---

## Workflow 3: "Video Diario Automatico" (cron)

### Nodos:

1. **Schedule Trigger** (Cron)
   - Expresion: `0 8 * * *` (cada dia a las 8am)

2. **HTTP Request** (POST al API)
   - URL: `https://TU-SPACE.hf.space/api/pipeline/webhook`
   - Body:
     ```json
     {
       "nicho": "finanzas personales",
       "canal": "MiCanal",
       "callback_url": "https://TU-N8N-SPACE.hf.space/webhook/pipeline-completado"
     }
     ```

---

## Despliegue de n8n en HF Spaces

1. Crear un nuevo Space en huggingface.co:
   - Nombre: `ytcreator-n8n`
   - SDK: Docker
   - Subir el `Dockerfile` de esta carpeta

2. Configurar Secrets en el Space:
   - `N8N_BASIC_AUTH_USER`: tu usuario
   - `N8N_BASIC_AUTH_PASSWORD`: tu password

3. Acceder a n8n en `https://TU-USUARIO-ytcreator-n8n.hf.space`

4. Crear los workflows siguiendo las guias de arriba
