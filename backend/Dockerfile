FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# This keeps the container alive so we can test connectivity
CMD ["tail", "-f", "/dev/null"]