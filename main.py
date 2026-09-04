"""
JARVIS - Personal AI Assistant
Dual-mode entry point:
- Run without arguments or `python app.py`: Launches Desktop Application.
- Run with `python main.py --cli`: Launches Enhanced Terminal Assistant.
"""

import sys
import os

def run_cli():
    print("=" * 50)
    print("🤖 JARVIS AI Assistant (Terminal Mode)")
    print("Type 'exit' to quit. Ask questions or give commands like 'open notepad'.")
    print("=" * 50 + "\n")

    from core.memory import MemoryManager
    from core.history import HistoryManager
    from core.tools import AssistantTools
    from core.assistant import AssistantEngine

    memory_mgr = MemoryManager()
    history_mgr = HistoryManager()
    engine = AssistantEngine(memory_mgr, history_mgr)

    session = history_mgr.create_session("CLI Session")
    session_id = session["id"]

    user_name = memory_mgr.get_memory()["user"].get("name", "User")
    if user_name:
        print(f"Jarvis: Welcome back, {user_name}! How can I help you today?\n")

    while True:
        try:
            user_input = input(f"{user_name}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nJarvis: Goodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q"]:
            print("Jarvis: Goodbye! 👋")
            break

        print("\nJarvis: ", end="", flush=True)

        def on_chunk(token):
            print(token, end="", flush=True)

        def on_complete(full_resp, tool_info):
            print("\n")

        def on_tool(tool_info):
            action_desc = tool_info.get("result", {}).get("summary") or tool_info.get("result", {}).get("action")
            print(f"\n[⚡ Action: {action_desc}]")

        engine.stream_chat(
            session_id=session_id,
            user_message=user_input,
            on_chunk=on_chunk,
            on_complete=on_complete,
            on_tool=on_tool
        )

def main():
    if "--cli" in sys.argv or "--terminal" in sys.argv:
        run_cli()
    else:
        # Default: Launch Desktop Application
        from app import main as start_app
        start_app()

if __name__ == "__main__":
    main()
