# The React UI is built ahead of time (frontend/ -> src/itg/static, committed), so the image only needs Python.
ARG BASE=python:3.11-slim
FROM ${BASE}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . agent-framework openai azure-identity
RUN useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "itg.server:app", "--host", "0.0.0.0", "--port", "8000"]
