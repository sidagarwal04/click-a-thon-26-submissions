# InsightIQ API (Node / Express)
# Railway injects PORT at runtime.
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY src ./src
EXPOSE 8080
USER node
CMD ["node", "src/index.js"]
