# ============================================================
# Frontend — Next.js Application Container (Phase 15)
# ============================================================

# Stage 1: Build Next.js application
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json tsconfig.json next.config.ts postcss.config.mjs eslint.config.mjs ./
RUN npm ci

COPY public/ ./public/
COPY src/ ./src/

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

# Stage 2: Minimal Production Runner
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.ts ./

USER node

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

CMD ["npm", "start"]
