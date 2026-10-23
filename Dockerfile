# The React UI is built ahead of time (frontend/ -> src/itg/static, committed), so the image only needs Python.
ARG BASE=python:3.11-slim
FROM ${BASE}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
# Pinned to the versions the tests and the live evaluation ran with.
RUN pip install --no-cache-dir . agent-framework==1.22.0 agent-framework-core==1.22.0 openai==3.35.1 azure-identity==1.26.0
RUN useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "itg.server:app", "--host", "0.0.0.0", "--port", "8000"]
