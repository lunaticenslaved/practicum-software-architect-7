# Set token and start
export TELEGRAM_BOT_TOKEN=your_token
docker compose up --build

# Pull llama3 model into Ollama (first time only)
docker compose exec ollama ollama pull llama3
