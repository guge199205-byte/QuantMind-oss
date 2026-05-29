# QuantMind OSS Edition - Nginx Gateway
FROM nginx:1.25-alpine

COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/cors.conf /etc/nginx/cors.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
