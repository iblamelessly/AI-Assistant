import requests

print("🤖 AI Assistant started!")
print("Type 'exit' to quit.\n")

while True:
    user_message = input("You: ")

    if user_message.lower() == "exit":
        print("AI: Goodbye! 👋")
        break

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen3:4b",
            "prompt": user_message,
            "stream": False
        }
    )

    ai_response = response.json()["response"]

    print("AI:", ai_response)
    print()