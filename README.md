---
title: YTCreator Studio v3
emoji: 🎬
colorFrom: red
colorTo: gray
sdk: docker
pinned: false
license: mit
---

# YTCreator Studio v3

Pipeline completo de automatizacion de videos para YouTube con 16 agentes IA.

**Nicho → Investigacion → Titulos → Guion → Imagenes/Video → Voz → Musica → Subtitulos → Video Final**

## Arquitectura

- **12 agentes especializados** (FastAPI) — investigador, copywriter, director de arte, guionista, evaluador, prompt maker, generador visual, locucion, musica, subtitulos, editor, SEO
- **4 orquestadores** — central + 3 sub-orquestadores por departamento
- **Streamlit UI** — interfaz web con 5 tabs
- **API Gateway** — webhooks para n8n y automatizacion externa
- **Kaggle GPU** — generacion de imagenes/video con IA (gratis)

## Uso local

```bash
# 1. Instala dependencias
pip install -r requirements.txt

# 2. Configura API keys
copy .env.template .env    # Llena GROQ_API_KEY y KAGGLE_KEY

# 3. Levanta todo
python run_dev.py          # 16 microservicios
python gateway.py          # Gateway en puerto 7860
streamlit run app.py       # UI en puerto 8501
```

## Docker (Hugging Face Spaces)

```bash
docker build -t ytcreator .
docker run -p 7860:7860 --env-file .env ytcreator
```

## API Keys necesarias

| Key | Donde obtenerla | Obligatoria |
|-----|----------------|-------------|
| GROQ_API_KEY | console.groq.com | Si |
| KAGGLE_USERNAME + KAGGLE_KEY | kaggle.com/settings | Si |
| PIXABAY_API_KEY | pixabay.com/api/docs | Opcional |

## Estructura del proyecto

```
ytcreator_v3/
├── app.py              Streamlit UI
├── gateway.py          API Gateway (puerto 7860)
├── api_client.py       Cliente HTTP para Streamlit
├── run_dev.py          Levanta los 16 microservicios
├── agents/             12 agentes especializados
├── orchestrator/       4 orquestadores
├── shared/             Modulos compartidos (schemas, config, state)
├── Dockerfile          Para HF Spaces
└── start.sh            Lanza todo en Docker
```
