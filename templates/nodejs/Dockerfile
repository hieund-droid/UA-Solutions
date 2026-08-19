# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS base
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NODE_ENV=production
RUN corepack enable

# --- Install deps ---
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml .npmrc ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --prod=false

# --- Build ---
FROM deps AS build
COPY tsconfig*.json ./
COPY src ./src
RUN pnpm run build

# --- Runtime (non-root, prod deps only) ---
FROM base AS runtime
WORKDIR /app
COPY package.json pnpm-lock.yaml .npmrc ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --prod
COPY --from=build /app/dist ./dist
RUN addgroup --system --gid 1001 app \
 && adduser --system --uid 1001 --ingroup app app
USER app
# HTTP-service shape adds `EXPOSE 3000` above this line — see
# shapes/http-service/Dockerfile-additions.txt.
CMD ["node", "dist/src/main.js"]
