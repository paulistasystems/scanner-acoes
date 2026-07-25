# -*- coding: utf-8 -*-
import sys
import os

# Adds the current directory to the path so python can import app
sys.path.insert(0, os.path.dirname(__file__))

# Garante que o processo Python enxergue o relógio em horário de Brasília
# (America/Sao_Paulo, UTC-3) — independente do fuso do SO (o servidor e o
# container rodam em UTC). Tem que vir ANTES de qualquer import de time/
# datetime para o tzset() rebindar o cache de fuso do C. Sem isto, logs e
# leituras de relógio "cruas" (datetime.now() sem tz) ficam em UTC enquanto
# _now_brt() fica em BRT — divergência que confunde a comparação e a leitura
# dos logs. O .env (carregado em app.py) pode sobrescrever TZ se necessário.
_tz = os.environ.get("TZ") or "America/Sao_Paulo"
os.environ["TZ"] = _tz
try:
    import time as _time
    _time.tzset()
except Exception:
    pass

# Add virtualenv site-packages to the path
VENV_SITE_PACKAGES = "/home/paulista/virtualenv/scanner/3.9/lib/python3.9/site-packages"
if os.path.exists(VENV_SITE_PACKAGES):
    sys.path.insert(0, VENV_SITE_PACKAGES)

# Import the Flask app
from app import app

# WSGI Middleware to handle Passenger/LiteSpeed subpath mapping
def application(environ, start_response):
    path_info = environ.get('PATH_INFO', '')
    if path_info.startswith('/scanner'):
        environ['SCRIPT_NAME'] = '/scanner'
        new_path = path_info[len('/scanner'):]
        if not new_path.startswith('/'):
            new_path = '/' + new_path
        environ['PATH_INFO'] = new_path
    elif path_info == '':
        environ['PATH_INFO'] = '/'
    return app(environ, start_response)
