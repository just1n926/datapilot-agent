FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATAPILOT_MODE=demo \
    DATAPILOT_DEMO_FILE=/app/sample_data/sales_demo.xlsx \
    OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=0

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY sample_data ./sample_data
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 datapilot
USER datapilot
EXPOSE 8000
CMD ["datapilot", "serve", "--host", "0.0.0.0"]
