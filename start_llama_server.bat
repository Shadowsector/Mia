@echo off
REM Запуск llama-server вручную (запустить один раз перед GUI)

echo Starting llama-server...
echo This window must stay open while using Mia PM OS
echo.

cd C:\llama.cpp
llama-server.exe -m C:\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf --port 8080 --n-gpu-layers 35 --ctx-size 8192 --threads 8

pause
