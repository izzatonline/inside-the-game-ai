FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend ./
RUN npm run build -- --outDir /ui/dist --emptyOutDir

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY --from=ui /ui/dist ./src/itg/static
RUN pip install --no-cache-dir . agent-framework openai azure-identity azure-eventhub
RUN useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "itg.server:app", "--host", "0.0.0.0", "--port", "8000"]
