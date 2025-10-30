FROM python:3.9-trixie

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY log_watcher.py ./

CMD ["python", "log_watcher.py"]

