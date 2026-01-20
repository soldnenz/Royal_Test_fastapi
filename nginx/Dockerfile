FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Устанавливаем зависимости и собираем фронтенд для production
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Собираем админ панель для production
FROM node:20-alpine AS frontend-admin-builder
WORKDIR /app

COPY frontend_admin/package*.json ./frontend_admin/
WORKDIR /app/frontend_admin
RUN npm ci
COPY frontend_admin/ ./
RUN npm run build

FROM nginx:alpine AS dev
ARG NGINX_ENV=dev

COPY nginx/nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /etc/nginx/conf.d /usr/share/nginx/html

# Удаляем дефолтную конфигурацию nginx
RUN rm -f /etc/nginx/conf.d/default.conf

RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

COPY nginx/conf.d/ /tmp/conf.d/

# Dev-конфиги: проксирование на Vite dev server и backend на хосте
RUN cp /tmp/conf.d/frontend.dev.conf /etc/nginx/conf.d/frontend.conf && \
    rm -rf /tmp/conf.d

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]

FROM nginx:alpine AS prod
ARG NGINX_ENV=prod

COPY nginx/nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /etc/nginx/conf.d /usr/share/nginx/html

# Удаляем дефолтную конфигурацию nginx
RUN rm -f /etc/nginx/conf.d/default.conf

RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

COPY nginx/conf.d/ /tmp/conf.d/

# Prod-конфиги: статика из собранного фронта + прокси на backend
RUN cp /tmp/conf.d/frontend.prod.conf /etc/nginx/conf.d/frontend.conf && \
    rm -rf /tmp/conf.d

# Копируем собранный frontend
COPY --from=frontend-builder --chown=nginx:nginx /app/frontend/dist /usr/share/nginx/html

# Копируем собранную админ панель
COPY --from=frontend-admin-builder --chown=nginx:nginx /app/frontend_admin/dist /usr/share/nginx/html/UDKeZNwbGVdH2iXEjkUFCkAuQb4Z1bbz

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]

