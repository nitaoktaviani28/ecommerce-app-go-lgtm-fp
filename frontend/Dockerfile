# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json ./

RUN npm install --legacy-peer-deps --no-optional

COPY . .

# Build dengan environment variables
ARG VITE_API_URL=http://localhost:8080/api
ARG VITE_FARO_COLLECTOR_URL=http://localhost:12347/collect
ARG VITE_APP_NAME=ecommerce-frontend
ARG VITE_APP_VERSION=1.0.0
ARG VITE_APP_ENV=production

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_FARO_COLLECTOR_URL=$VITE_FARO_COLLECTOR_URL
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_APP_ENV=$VITE_APP_ENV

RUN npm run build

# Final stage
FROM node:18-alpine

RUN npm install -g serve

WORKDIR /app

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
