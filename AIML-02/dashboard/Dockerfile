FROM node:24-alpine AS build
WORKDIR /app
ARG VITE_API_URL=http://localhost:8000
ARG VITE_ORTHANC_URL=http://localhost:8042
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_ORTHANC_URL=$VITE_ORTHANC_URL
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
