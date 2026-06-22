# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build args
ARG VITE_API_URL=http://localhost:8080
ARG VITE_FARO_COLLECTOR_URL=http://localhost:12347/collect
ARG VITE_APP_NAME=ecommerce-frontend
ARG VITE_APP_VERSION=1.0.0
ARG VITE_APP_ENV=production

# Build the application
RUN npm run build

# Final stage
FROM node:18-alpine

# Install serve to run the app
RUN npm install -g serve

WORKDIR /app

# Copy built app from builder
COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]