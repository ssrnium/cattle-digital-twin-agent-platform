FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY simulator.py .
ENV MQTT_HOST=mosquitto \
    ADMIN_URL=http://cow-admin:8081
CMD ["python", "simulator.py", "--mode", "online", "--interval", "10"]
