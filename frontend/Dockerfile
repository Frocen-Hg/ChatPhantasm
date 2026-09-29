FROM node:20-alpine AS build
WORKDIR /app
# 可通过 --build-arg NPM_REGISTRY=国内镜像 加速
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --registry=${NPM_REGISTRY}
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80