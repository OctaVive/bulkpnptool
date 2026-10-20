FROM php:8.4-cli-alpine
WORKDIR /app
COPY . .
EXPOSE 5001
CMD ["php", "-S", "0.0.0.0:5001", "-t", "public", "router.php"]
