# ---- Build Stage ----
FROM node:18-alpine AS build
WORKDIR /app

# Install dependencies first (for better caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code and build the Vite React app
COPY . .

# Pass in the backend URL dynamically at build time
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ---- Production Stage ----
FROM nginx:alpine

# Remove default Nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built React artifacts to Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration to handle React Router (SPA) routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
