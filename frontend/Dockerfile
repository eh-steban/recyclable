# Multi-stage Dockerfile for Next.js (App Router).
# Stages: deps -> dev (hot reload) | builder -> runner (prod parity).
#
# NOTE: Vercel does NOT use this Dockerfile -- it builds Next.js itself from
# the repo root. This file is for local prod-parity testing and any future
# self-hosted deploy. The default `target` for `docker compose up` is `dev`.

# ---------- deps ----------
FROM node:24-alpine AS deps
WORKDIR /app
# Better caching: copy lockfile first
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# ---------- dev (hot reload, mounted source) ----------
FROM node:24-alpine AS dev
WORKDIR /app
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
# Source is bind-mounted by docker-compose; this COPY is a parity fallback.
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---------- builder ----------
FROM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- runner (prod parity) ----------
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

# Non-root user (node image ships with `node` UID 1000)
USER node

# Next.js standalone output -- enable in next.config.ts: `output: 'standalone'`
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
