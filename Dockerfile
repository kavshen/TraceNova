FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY services/api/src ./services/api/src
COPY packages/config/src ./packages/config/src
COPY packages/logging/src ./packages/logging/src
COPY packages/common/src ./packages/common/src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "tracenova_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

