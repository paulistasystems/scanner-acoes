#!/bin/bash
# Script para executar o scanner de ações no ambiente virtual

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Ativar ambiente virtual
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Erro: venv não encontrado. Execute: python3 -m venv venv"
    exit 1
fi

# Definir modo (padrão: todos)
MODE="${1:-todos}"

# Executar o scanner
echo "Executando scanner no modo: $MODE"
echo "----------------------------------------"
python scanner_consolidado.py "$MODE"
