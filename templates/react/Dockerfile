# syntax=docker/dockerfile:1.7

# --- Build the static bundle ---
FROM node:20-bookworm-slim AS build
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml .npmrc ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile
COPY tsconfig*.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public
RUN pnpm build

# --- Serve with nginx (non-root) ---
FROM nginx:1.27-alpine AS runtime
RUN addgroup -S app && adduser -S app -G app \
 && chown -R app:app /var/cache/nginx /var/run /var/log/nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=app:app /app/dist /usr/share/nginx/html
USER app
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
