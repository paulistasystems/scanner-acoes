#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/www/vhosts/scanner/html \
         /var/www/vhosts/scanner/logs \
         /usr/local/lsws/logs \
         /usr/local/lsws/conf/vhosts/scanner \
         /tmp/lshttpd

if [[ -f /ols-config/httpd_config.conf ]]; then
  cp -f /ols-config/httpd_config.conf /usr/local/lsws/conf/httpd_config.conf
fi
if [[ -f /ols-config/vhconf.conf ]]; then
  cp -f /ols-config/vhconf.conf /usr/local/lsws/conf/vhosts/scanner/vhconf.conf
fi

# Imagem oficial: /entrypoint.sh sobe o LSWS
if [[ -x /entrypoint.sh ]]; then
  exec /entrypoint.sh "$@"
fi
if [[ -x /usr/local/bin/docker-entrypoint.sh ]]; then
  exec /usr/local/bin/docker-entrypoint.sh "$@"
fi

/usr/local/lsws/bin/lswsctrl start || /usr/local/lsws/bin/lswsctrl restart || true
exec tail -F /usr/local/lsws/logs/error.log
