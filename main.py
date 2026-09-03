import requests

MODEL = "qwen3:1.7b"
OLLAMA_URL = "http://localhost:11434/api/chat"

print("🤖 AI Assistant started!")
print("Type 'exit' to quit.\n")

# ==============================
# CONVERSATION MEMORY
# ==============================

messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful personal AI assistant. "
            "You have access to the entire conversation history in the messages. "
            "Always use previous messages when answering questions. "
            
            "If the user tells you personal information such as their name, "
            "remember it during the current conversation. "
            
            "For example, if the user says 'hi im Lessly' or "
            "'my name is Lessly', then the user's name is Lessly. "
            "If the user later asks 'what is my name?', answer 'Your name is Lessly.' "
            
            "Do not ask for information that the user has already provided "
            "in the conversation. "
            
            "Do not invent facts about the user. "
            "Be concise, friendly, and helpful."
        )
    }
]

# ==============================
# MAIN CHAT LOOP
# ==============================

while True:

    user_message = input("You: ")

    # Exit
    if user_message.lower().strip() == "exit":
        print("AI: Goodbye! 👋")
        break

    # Add user message to conversation memory
    messages.append({
        "role": "user",
        "content": user_message
    })

    try:

        # Send entire conversation history to Ollama
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "think": False
            }
        )

        response.raise_for_status()

        data = response.json()

        # Get AI response
        ai_response = data["message"]["content"]

        # Save AI response to conversation memory
        messages.append({
            "role": "assistant",
            "content": ai_response
        })

        print("AI:", ai_response)
        print()

    except requests.exceptions.ConnectionError:
        print("❌ Error: Ollama is not running.")
        print("Start Ollama and try again.\n")

    except Exception as e:
        print("❌ Error:", e)
        print()
