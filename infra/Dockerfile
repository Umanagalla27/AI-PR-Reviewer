FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml ./
# We can use pip to install the dependencies from pyproject.toml
# In a real app we'd use poetry or hatch, but pip works with pyproject.toml
RUN pip install .[dev]

FROM python:3.11-slim as runner

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

ENV PYTHONPATH=/app
