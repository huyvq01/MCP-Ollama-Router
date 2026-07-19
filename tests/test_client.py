from app.clients.ollama_client import OllamaClient

client = OllamaClient()

print(client.health())

print(client.list_models())