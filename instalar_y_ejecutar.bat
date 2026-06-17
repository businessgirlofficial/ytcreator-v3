@echo off
echo ================================================
echo    YTCreator Studio v3
echo ================================================
echo.
py --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no instalado. Ve a python.org/downloads
    pause & exit /b 1
)
echo [1/2] Instalando dependencias...
py -m pip install -r requirements.txt -q
echo.
echo [2/2] Iniciando YTCreator Studio v3...
echo Abriendo en: http://localhost:8501
echo Para cerrar: Ctrl+C
echo ================================================
py -m streamlit run app.py --server.port 8501
pause
