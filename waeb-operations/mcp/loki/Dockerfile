# Loki MCP with Streamable HTTP on port 8000 (/mcp) for Open WebUI.
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json tsconfig.json ./
RUN npm ci
COPY src ./src
RUN npx tsc && npm prune --omit=dev

FROM node:22-slim
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
ENV MCP_HTTP_PORT=8000
EXPOSE 8000
USER node
CMD ["node", "dist/index.js"]
