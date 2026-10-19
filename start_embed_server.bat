@echo off
REM Embedding server for Mia PM OS RAG (bge-m3). Keep this window open.
REM Chat server uses port 8080; this one uses 8081.

cd C:\llama.cpp
llama-server.exe -m C:\models\bge-m3-Q8_0.gguf --port 8081 --embedding --pooling cls --host 127.0.0.1 --threads 8

pause
