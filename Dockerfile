FROM node:22-slim AS frontend
WORKDIR /app/Fontend/translator-app
COPY Fontend/translator-app/package*.json ./
RUN npm ci
COPY Fontend/translator-app/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV APP_PROFILE=demo
COPY requirements-render.txt ./
RUN python -m pip install --upgrade pip && python -m pip install --no-cache-dir -r requirements-render.txt
COPY apps ./apps
COPY core ./core
COPY config ./config
COPY data ./data
COPY --from=frontend /app/Fontend/translator-app/dist ./Fontend/translator-app/dist
CMD ["python", "-m", "apps.api.main"]

