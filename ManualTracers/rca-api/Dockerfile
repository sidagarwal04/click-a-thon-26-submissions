FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm config set strict-ssl false \
    && npm install --omit=dev \
    && npm config delete strict-ssl
COPY server.js sample-reports.js mock-series.js report-store.js live-series.js ./
ENV RCA_API_PORT=3002
EXPOSE 3002
CMD ["node", "server.js"]
