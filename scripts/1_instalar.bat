@echo off
REM AgroSentinela - instalacao (Windows). Execute a partir da pasta do projeto.
cd /d %~dp0..

python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERRO] Python nao encontrado.
  echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH",
  echo desative os aliases python.exe/python3.exe em Configuracoes ^> Aplicativos ^>
  echo Configuracoes avancadas ^> Aliases de execucao, e rode este script de novo.
  pause
  exit /b 1
)
node --version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Node.js nao encontrado. Instale a versao LTS em https://nodejs.org/ e rode de novo.
  pause
  exit /b 1
)

if not exist .env copy .env.example .env
echo === Backend: criando ambiente virtual Python ===
python -m venv backend\.venv || goto erro
call backend\.venv\Scripts\activate || goto erro
python -m pip install -r backend\requirements.txt || goto erro
echo === Frontend: instalando pacotes ===
cd frontend
call npm install || goto erro
cd ..
echo.
echo Instalacao concluida. Revise o arquivo .env (usuario/senha do MySQL e URI do MongoDB)
echo e rode scripts\2_carregar_dados.bat
pause
exit /b 0

:erro
echo.
echo [ERRO] A instalacao falhou na etapa acima. Copie a mensagem de erro e peca ajuda.
pause
exit /b 1
