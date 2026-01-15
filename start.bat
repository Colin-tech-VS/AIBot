@echo off
echo === Demarrage F1 Chatbot ===
echo.
echo 1. Activation environnement virtuel...
call .venv\Scripts\activate.bat

echo 2. Lancement serveur FastAPI...
python app.py

pause
