#!/bin/bash
# Script para executar o Scanner de Abertura (10:30)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv311" ]; then
    source venv311/bin/activate
elif [ -d "venv313" ]; then
    source venv313/bin/activate
else
    echo "Erro: Nenhum venv encontrado."
    exit 1
fi

echo "Iniciando Scanner de Abertura (15m)..."
echo "----------------------------------------"
streamlit run scanner_abertura.py
