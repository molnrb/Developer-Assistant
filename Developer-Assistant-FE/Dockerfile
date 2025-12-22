# 1. Build stage
FROM node:20-alpine AS build

WORKDIR /src
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# 2. Serve stage (Nginx)
FROM nginx:1.27-alpine AS prod

# A Vite build alapból "dist" mappába teszi a kész statikus fájlokat
COPY --from=build /src/dist /usr/share/nginx/html

# (opcionálisan: saját nginx.conf, ha kell API proxy)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
