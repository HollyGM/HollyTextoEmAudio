#!/bin/bash
# Duplo clique para abrir o Texto em Áudio.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Primeira execução: instalando dependências..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || exit 1
fi
exec .venv/bin/python -m texto_audio
