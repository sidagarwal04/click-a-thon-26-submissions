# Multi-stage: build the Vite app, then serve the static output via nginx,
# reverse-proxying API calls to the `api` service (see nginx.conf) -- the
# same relative-path contract vite.config.ts's dev proxy uses, so no app
# code differs between dev and prod.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
