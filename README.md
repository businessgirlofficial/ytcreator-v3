# 🎬 YTCreator Studio

Pipeline completo de producción de videos para YouTube.
**Guión → Imágenes → Videos → Voz → Música → Subtítulos → Video Final**

## Instalación (Windows)

1. Instala Python 3.10+ desde https://www.python.org/downloads/
   - ⚠️ Marca "Add Python to PATH" durante la instalación

2. Haz doble clic en `instalar_y_ejecutar.bat`

3. Se abre automáticamente en tu navegador en http://localhost:8501

## Configuración inicial

1. En el panel lateral izquierdo, configura tus API Keys:
   - **Groq** (gratis): https://console.groq.com
   - **Kaggle** (gratis): https://kaggle.com/settings
   - **Pixabay** (gratis): https://pixabay.com/api/docs/

2. Haz clic en "Guardar configuración"

## Flujo de trabajo

### Paso 0 — Guión
- **Opción A:** Genera un guión viral automáticamente con Groq
- **Opción B:** Pega tu guión ya escrito

### Paso 1 — Audio (tab "Audio")
- Genera la narración con Edge TTS (400+ voces gratis)
- Descarga música de fondo de Pixabay automáticamente

### Paso 2 — Imágenes y Videos (tab "Kaggle")
- La app prepara el guión para Kaggle
- Sube los clips generados

### Paso 3 — Ensamblar (tab "Ensamblar")
- Combina clips + voz + música + subtítulos
- Exporta el video final listo para YouTube

## Estructura de archivos

```
ytcreator_studio/
├── app.py                    ← App principal
├── requirements.txt          ← Dependencias
├── instalar_y_ejecutar.bat  ← Instalador Windows
├── .env.template            ← Template de configuración
└── proyectos/               ← Tus proyectos (se crea automático)
    └── mi_video_ep01/
        ├── videos/          ← Clips de Kaggle
        ├── audio/           ← Narración generada
        ├── musica/          ← Música de fondo
        ├── output/          ← Video final
        └── guion_kaggle.json
```

## Requisitos

- Windows 10/11
- Python 3.10+
- Conexión a internet
- ~2GB de espacio en disco
