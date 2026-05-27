# Dockerfile do frontend — multi-stage (build com Node, serve com nginx).
# Usado só em produção (docker-compose.prod.yml). No dev, o Vite roda
# direto via imagem node no compose, sem este Dockerfile.

# ---------------------------------------------------------------------------
# Etapa 1: build do bundle estático com Vite.
FROM node:22-alpine AS build

WORKDIR /app

# Copia só os manifests primeiro pra aproveitar cache de camada: enquanto
# package*.json não mudam, o npm ci não roda de novo.
COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_URL é embutido no bundle em tempo de build (variáveis VITE_*
# viram texto no JS final). Em produção o nginx faz proxy de /api/ pro
# backend, então o front chama caminho relativo "/api/v1".
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---------------------------------------------------------------------------
# Etapa 2: nginx servindo o bundle + proxy da API.
FROM nginx:1.27-alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
