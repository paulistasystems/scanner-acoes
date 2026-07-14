FROM php:8.2-cli-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      libsqlite3-dev pkg-config \
    && docker-php-ext-install pdo_sqlite \
    && docker-php-ext-enable pdo_sqlite \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /var/www/php
COPY php/yahoo_chart.php /var/www/php/yahoo_chart.php
ENV SCANNER_DB=/data/scanner.db
EXPOSE 8008
CMD ["php", "-S", "0.0.0.0:8008", "-t", "/var/www/php"]
