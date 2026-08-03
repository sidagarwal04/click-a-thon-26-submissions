# Two stages: build the bundle with node, serve it with nginx.
#
# Serving the BUILT bundle, not the dev server -- a demo should not be running
# hot-module-reload, where a transient compile error paints a full-screen
# overlay over the thing being presented.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
