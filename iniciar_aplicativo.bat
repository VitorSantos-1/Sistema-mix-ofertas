@echo off
title Mix de Ofertas - Supermercados Opcao
cd /d "%~dp0"
cls
echo ======================================================================
echo           SISTEMA DE MIX DE OFERTAS & ENCARTES V2.0
echo                     SUPERMERCADOS OPCAO
echo ======================================================================
echo.
echo [1/2] Abrindo aplicacao no navegador (http://localhost:3001)...
timeout /t 2 /nobreak >nul
start http://localhost:3001
echo [2/2] Iniciando servidor FastAPI local...
echo.
if exist "C:\Anaconda3\python.exe" (
    "C:\Anaconda3\python.exe" main.py
) else (
    python main.py
)
pause

