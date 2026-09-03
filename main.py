import requests
import json
import os

MODEL = "qwen3:1.7b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Always keep memory.json beside main.py
MEMORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "memory.json"
)


# ==============================
# PERMANENT MEMORY
# ==============================

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except:
            pass

    return {
        "user": {
            "name": "",
            "career_goal": "",
            "education": "",
            "projects": [],
            "skills": [],
            "preferences": [],
            "other": []
        }
    }


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=4)


memory = load_memory()


# ==============================
# SMART MEMORY DETECTION
# ==============================

def update_memory(user_message):

    memory_prompt = f"""
You are a memory extraction system for a personal AI assistant.

Analyze the user's message and identify ONLY information that is useful
to remember about the user for future conversations.

Current message:
"{user_message}"

Return ONLY valid JSON in this exact format:

{{
    "name": "",
    "career_goal": "",
    "education": "",
    "project": "",
    "skill": "",
    "preference": "",
    "other": ""
}}

Rules:

- Only include information explicitly stated by the user.
- Do not guess or invent anything.
- Leave fields empty if there is no relevant information.
- Do not save normal questions or temporary conversation.
- Save important long-term information.
- If the user gives a new project, put it in "project".
- If the user gives a career goal, put it in "career_goal".
- If the user gives their name, put it in "name".
- If the user gives education information, put it in "education".
- If the user mentions a skill they have or are learning, put it in "skill".
- If the user states a preference, put it in "preference".
"""

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": memory_prompt
                    }
                ],
                "stream": False,
                "think": False
            }
        )

        response.raise_for_status()

        result = response.json()["message"]["content"].strip()

        # Remove markdown code fences if Qwen adds them
        result = result.replace("```json", "").replace("```", "").strip()

        extracted = json.loads(result)

        # ==============================
        # SAVE EXTRACTED INFORMATION
        # ==============================

        if extracted.get("name"):
            memory["user"]["name"] = extracted["name"]

        if extracted.get("career_goal"):
            memory["user"]["career_goal"] = extracted["career_goal"]

        if extracted.get("education"):
            memory["user"]["education"] = extracted["education"]

        if extracted.get("project"):
            project = extracted["project"]

            if project not in memory["user"]["projects"]:
                memory["user"]["projects"].append(project)

        if extracted.get("skill"):
            skill = extracted["skill"]

            if skill not in memory["user"]["skills"]:
                memory["user"]["skills"].append(skill)

        if extracted.get("preference"):
            preference = extracted["preference"]

            if preference not in memory["user"]["preferences"]:
                memory["user"]["preferences"].append(preference)

        if extracted.get("other"):
            other = extracted["other"]

            if other not in memory["user"]["other"]:
                memory["user"]["other"].append(other)

        save_memory(memory)

    except Exception:
        # If memory extraction fails, don't stop the main assistant
        pass


# ==============================
# CONVERSATION MEMORY
# ==============================

messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful personal AI assistant. "
            "Use both the conversation history and permanent user memory "
            "when answering questions.\n\n"

            "PERMANENT USER MEMORY:\n"
            f"{json.dumps(memory, indent=2)}\n\n"

            "Rules:\n"
            "1. Use information from permanent memory when relevant.\n"
            "2. Use previous conversation messages when relevant.\n"
            "3. Never invent personal information.\n"
            "4. If you don't know something, say so.\n"
            "5. Be concise, friendly and helpful."
        )
    }
]


# ==============================
# START ASSISTANT
# ==============================

print("🤖 AI Assistant started!")
print("Type 'exit' to quit.\n")


# ==============================
# MAIN CHAT LOOP
# ==============================

while True:

    user_message = input("You: ")

    if user_message.lower().strip() == "exit":
        print("AI: Goodbye! 👋")
        break

    # --------------------------------
    # SMART MEMORY EXTRACTION
    # --------------------------------

    update_memory(user_message)

    # --------------------------------
    # Add message to conversation
    # --------------------------------

    messages.append({
        "role": "user",
        "content": user_message
    })

    try:

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

        ai_response = data["message"]["content"]

        # Save AI response to conversation history
        messages.append({
            "role": "assistant",
            "content": ai_response
        })

        print("AI:", ai_response)
        print()

    except requests.exceptions.ConnectionError:
        print("❌ Error: Ollama is not running.")
        print("Please start Ollama and try again.\n")

    except Exception as e:
        print("❌ Error:", e)
        print()

