# The API. Small on purpose: it holds credentials and forwards bound
# parameters, nothing else.
FROM node:22-alpine

WORKDIR /app
# Copy manifests first so `npm ci` is cached and only re-runs when deps change.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src

EXPOSE 8787
CMD ["node", "src/index.js"]
