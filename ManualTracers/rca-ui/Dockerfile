FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm config set strict-ssl false \
    && npm install \
    && npm config delete strict-ssl
COPY . .
# Empty = same-origin; nginx proxies /api to rca-api
ARG VITE_RCA_API_URL=
ENV VITE_RCA_API_URL=$VITE_RCA_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
