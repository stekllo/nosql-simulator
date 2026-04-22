# syntax=docker/dockerfile:1.7
FROM node:20-slim

WORKDIR /app

# pnpm
RUN corepack enable && corepack prepare pnpm@10 --activate

# Кэш слоя зависимостей
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

COPY . .

EXPOSE 3000

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "3000"]
