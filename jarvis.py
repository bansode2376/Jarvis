import ollama
import json
import os

MODEL = "llama3.2:3b"

# Step 4: YOU - who the assistant is talking to
with open("you.txt", "r", encoding="utf-8") as f:
    about_me = f.read()

# Step 5: MEMORY - things it saved earlier
MEMORY_FILE = "memory.json"
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        memory = json.load(f)
else:
    memory = []

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

system_prompt = f"""You are Jarvis, a helpful, polite personal AI assistant.
About the user:
{about_me}

Things you remember:
{chr(10).join(memory) if memory else "Nothing yet."}
"""

# Step 2: HARNESS - the loop that connects everything
history = [{"role": "system", "content": system_prompt}]
print("Jarvis online. Type 'exit' to quit. Type 'remember: ...' to save a memory.")

while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        break
    if user_input.lower().startswith("remember:"):
        memory.append(user_input[9:].strip())
        save_memory()
        print("Jarvis: Noted, I'll remember that.")
        continue

    history.append({"role": "user", "content": user_input})
    response = ollama.chat(model=MODEL, messages=history)
    reply = response["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    print("Jarvis:", reply)