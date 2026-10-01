FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY State-of-Search/pyproject.toml /workspace/pyproject.toml
COPY State-of-Search/app /workspace/app
RUN pip install --no-cache-dir .

COPY State-of-Search/sql /workspace/sql
COPY Incident-search/generate_data.py /incident-source/generate_data.py
COPY Incident-search/generator /incident-source/generator
COPY Incident-search/seed /incident-source/seed

CMD ["streamlit", "run", "app/ui.py", "--server.address=0.0.0.0", "--server.port=8501"]
