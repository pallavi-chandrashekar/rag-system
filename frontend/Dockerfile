# Stage 1: Build
FROM node:20-alpine as build

WORKDIR /app

# Copy package files first (better caching)
COPY package*.json ./

# Install dependencies (ensuring react-markdown is installed)
RUN npm install

# Copy source code (ignoring node_modules via .dockerignore)
COPY . .

# Build the app
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]