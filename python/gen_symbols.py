#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera ``php/symbols.json`` a partir do universo autoritativo do scanner.

Fonte: ``symbols_fallback.ATIVOS_B3_AMPLIADO`` (mesma lista que o scanner usa em
produção). O ``php/yahoo_probe.php`` lê este JSON para testar a cobertura do
Yahoo Chart API a partir do servidor.

Rode sempre que o universo mudar::

    venv39/bin/python python/gen_symbols.py

O output é fixo em ``php/symbols.json`` (lê-se a partir do mesmo directório que
``yahoo_probe.php`` no servidor) — não segue a localização deste script.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))

import symbols_fallback  # noqa: E402

out = list(symbols_fallback.ATIVOS_B3_AMPLIADO)
dest = REPO_ROOT / "php" / "symbols.json"
dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)} símbolos -> {dest}")
