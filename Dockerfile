FROM python:3.11-slim

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY ./src src

WORKDIR /usr/src/app/src
CMD ["python", "-m", "gge_utility_bot.main"]