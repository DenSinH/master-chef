FROM python:3.11-slim-bookworm

WORKDIR /app

COPY ./src/requirements.txt .
RUN pip install -r requirements.txt

COPY ./src .

WORKDIR webapp

ENTRYPOINT ["python", "app.py"]