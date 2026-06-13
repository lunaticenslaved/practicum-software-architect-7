FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Task3/faiss_index/ Task3/faiss_index/
COPY Task4/ Task4/
COPY Task7/ Task7/

ENV OLLAMA_HOST=http://ollama:11434
ENV OLLAMA_MODEL=llama3

CMD ["python", "Task4/bot.py"]
