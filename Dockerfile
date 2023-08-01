FROM python:3.9-buster
WORKDIR /app

COPY ./src/requirements.txt .
RUN pip install -r requirements.txt

COPY ./src .

WORKDIR webapp
ENTRYPOINT ["python", "app.py"]