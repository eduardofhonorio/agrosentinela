@echo off
REM Cria as tabelas, carrega os dados de demonstração e executa a 1ª integração.
cd /d %~dp0..\backend
call .venv\Scripts\activate
python -m app.seed
python -m app.etl.pipeline
pause
