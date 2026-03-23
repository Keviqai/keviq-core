FROM node:22-slim AS base
RUN corepack enable

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/
COPY packages/api-client/package.json ./packages/api-client/
COPY packages/domain-types/package.json ./packages/domain-types/
COPY packages/live-state/package.json ./packages/live-state/
COPY packages/permissions/package.json ./packages/permissions/
COPY packages/routing/package.json ./packages/routing/
COPY packages/server-state/package.json ./packages/server-state/
COPY packages/ui-state/package.json ./packages/ui-state/
RUN pnpm install --frozen-lockfile --filter @keviq/web...

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml .npmrc ./
COPY packages/api-client/package.json ./packages/api-client/
COPY packages/domain-types/package.json ./packages/domain-types/
COPY packages/live-state/package.json ./packages/live-state/
COPY packages/permissions/package.json ./packages/permissions/
COPY packages/routing/package.json ./packages/routing/
COPY packages/server-state/package.json ./packages/server-state/
COPY packages/ui-state/package.json ./packages/ui-state/
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile --filter @keviq/web...
COPY tsconfig.base.json ./
COPY packages/ ./packages/
COPY apps/web/ ./apps/web/
RUN pnpm --filter @keviq/web run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
# Next.js standalone in monorepo preserves directory structure
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
