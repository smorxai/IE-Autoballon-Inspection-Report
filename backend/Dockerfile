# From AI_Engine (parent of frontend/ and backend/):
#   docker build -f backend/Dockerfile .
FROM python:3.10-slim

WORKDIR /app
COPY frontend /app/frontend
COPY backend /app/backend

WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 9080
CMD ["python", "serve_balloon.py"]
