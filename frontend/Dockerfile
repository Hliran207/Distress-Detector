# --- Stage 1: build ---
# Node image compiles the Vite/React app into static assets in /app/dist.
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies first (better layer caching when only source changes).
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json eslint.config.js ./
COPY public ./public
COPY src ./src

# Browser calls the API on the host-mapped port, not the Docker service name `mongo` or `backend`.
ARG VITE_API_BASE_URL=http://localhost:8001
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- Stage 2: serve ---
# Nginx serves static files; much smaller and more production-appropriate than Node for SPA hosting.
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
