# Dashboard — Vite build served as static files by nginx.
# Vite inlines import.meta.env.VITE_* at BUILD time, and these are HOST-browser URLs
# (the browser runs on your machine, not inside the compose network) — hence localhost,
# not service names. docker-compose passes them as build args.
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_API_URL=http://localhost:8000
ARG VITE_LIBRECHAT_URL=http://localhost:3080
ENV VITE_API_URL=$VITE_API_URL \
    VITE_LIBRECHAT_URL=$VITE_LIBRECHAT_URL
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
