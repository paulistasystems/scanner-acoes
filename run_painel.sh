#!/bin/bash
# Script para executar o Painel do Banco de Dados (somente leitura)

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

echo "Iniciando Painel do Banco de Dados..."
echo "----------------------------------------"
streamlit run painel_bd.py
