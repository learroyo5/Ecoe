FROM node:22-alpine AS deps

WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app
ARG NEXT_PUBLIC_API_URL=/api
ARG INTERNAL_API_URL=http://backend:8000
# Optional: override the live-timer WebSocket URL/port for topologies other
# than "docker-compose direct" or "prod behind nginx" (see src/lib/ws.ts).
ARG NEXT_PUBLIC_WS_URL=""
ARG NEXT_PUBLIC_BACKEND_WS_PORT=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV INTERNAL_API_URL=$INTERNAL_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_BACKEND_WS_PORT=$NEXT_PUBLIC_BACKEND_WS_PORT
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=/api
ENV INTERNAL_API_URL=http://backend:8000

COPY --from=builder --chown=node:node /app/package*.json ./
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/node_modules ./node_modules

# Run as the unprivileged node user shipped with the base image.
USER node

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
