import asyncio
import os
import sys
from dotenv import load_dotenv
from typing import List, Dict, Any, Callable

# Import both interfaces
from interfaces.discord_bot_interface import DiscordInterface, intents
from interfaces.console_interface import ConsoleInterface

# Import chatbot and memory_manager
import chatbot
import memory_manager

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # This is not directly used in main, but good to keep for completeness

# --- Chatbot Processor Function ---
def kinecho_chatbot_processor(query: str, history: List[Dict[str, str]], channel_id: str) -> str:
    """
    Processes a user query using the core chatbot logic.
    This function is passed to each interface.
    """
    response = chatbot.get_chat_response(
        prompt_text=query,
        history=history,
        channel_id=channel_id
    )
    return response

async def main():
    """
    Main asynchronous function to initialize Kinecho Commander and manage interfaces.
    """
    print("Kinecho Main: Initializing Kinecho Commander...")

    # Initialize interface instances (don't start them yet)
    discord_interface = DiscordInterface(
        chatbot_processor_func=kinecho_chatbot_processor,
        intents=intents
    )
    console_interface = ConsoleInterface(
        chatbot_processor_func=kinecho_chatbot_processor
    )

    # Dictionary to hold active interface tasks
    active_interface_tasks: Dict[str, asyncio.Task] = {}

    print("\n--- Kinecho Commander Ready ---")
    print("Type 'help' for available commands.")
    print("-------------------------------\n")

    while True:
        # Determine the appropriate prompt based on whether console interface is active
        prompt_text = "Kinecho Commander > "
        # Check if console interface is currently running AND expecting chat input
        # console_interface.is_running is set by its initialize_interface and stop methods
        if "console" in active_interface_tasks and not active_interface_tasks["console"].done() and console_interface.is_running:
            prompt_text = "You (Kinecho Console) > "

        # Read user input using asyncio.to_thread to prevent blocking the event loop
        command_line = (await asyncio.to_thread(input, prompt_text)).strip()

        # --- Input Handling Logic ---
        # If console interface is active and not stopped by user, forward input to it
        if "console" in active_interface_tasks and not active_interface_tasks["console"].done() and console_interface.is_running:
            # Forward the user's input to the console interface for processing
            await console_interface.receive_message(command_line)

            # After processing, check if the console interface signaled to stop itself (e.g., by typing 'quit')
            if not console_interface.is_running:
                print("Kinecho Commander: Console Interface stopped by user input. Returning to Commander mode.")
                # Wait for the console task to truly finish its graceful shutdown
                await active_interface_tasks["console"]
                del active_interface_tasks["console"] # Remove from active tasks
            continue # Continue the loop to get the next input, either for Commander or Console

        # If console interface is NOT active for chat, process as a Commander command
        parts = command_line.split()
        command = parts[0].lower() if parts else "" # Convert command to lowercase for consistent matching
        target_interface = parts[1].lower() if len(parts) > 1 else "" # Convert target to lowercase

        if command == "start":
            if target_interface == "discord":
                if "discord" not in active_interface_tasks or active_interface_tasks["discord"].done():
                    print("Kinecho Commander: Starting Discord Interface...")
                    discord_task = asyncio.create_task(discord_interface.initialize_interface(DISCORD_BOT_TOKEN))
                    active_interface_tasks["discord"] = discord_task
                else:
                    print("Kinecho Commander: Discord Interface already running.")
            elif target_interface == "console":
                if "console" not in active_interface_tasks or active_interface_tasks["console"].done():
                    print("Kinecho Commander: Starting Console Interface...")
                    console_task = asyncio.create_task(console_interface.initialize_interface())
                    active_interface_tasks["console"] = console_task
                else:
                    print("Kinecho Commander: Console Interface already running.")
            else:
                print("Kinecho Commander: Invalid 'start' target. Use 'start discord' or 'start console'.")

        elif command == "stop":
            if target_interface == "discord":
                if "discord" in active_interface_tasks and not active_interface_tasks["discord"].done():
                    print("Kinecho Commander: Stopping Discord Interface...")
                    discord_interface.is_running = False # Signal to the bot to stop
                    await discord_interface.close() # Calls discord.Client's internal close
                    await active_interface_tasks["discord"] # Wait for the task to truly finish
                    del active_interface_tasks["discord"]
                else:
                    print("Kinecho Commander: Discord Interface not running.")
            elif target_interface == "console":
                if "console" in active_interface_tasks and not active_interface_tasks["console"].done():
                    print("Kinecho Commander: Stopping Console Interface...")
                    await console_interface.stop() # This will set is_running=False and _quit_event
                    await active_interface_tasks["console"] # Wait for initialize_interface task to finish
                    del active_interface_tasks["console"]
                else:
                    print("Kinecho Commander: Console Interface not running.")
            else:
                print("Kinecho Commander: Invalid 'stop' target. Use 'stop discord' or 'stop console'.")

        elif command == "status":
            print("\n--- Kinecho Interface Status ---")
            discord_status = "RUNNING" if "discord" in active_interface_tasks and not active_interface_tasks["discord"].done() else "STOPPED"
            console_status = "RUNNING" if "console" in active_interface_tasks and not active_interface_tasks["console"].done() else "STOPPED"
            print(f"  Discord: {discord_status}")
            print(f"  Console: {console_status}")
            print("------------------------------\n")

        elif command == "quit" or command == "exit":
            print("Kinecho Commander: Shutting down all active interfaces...")
            # Create a list of tasks to stop to avoid modifying dict during iteration
            tasks_to_stop = list(active_interface_tasks.values())
            for task in tasks_to_stop:
                if not task.done(): # Only try to stop tasks that are still running
                    # Find the name of the interface associated with this task
                    interface_name = [name for name, t in active_interface_tasks.items() if t == task][0]
                    print(f"Kinecho Commander: Stopping {interface_name}...")
                    if interface_name == "discord":
                        discord_interface.is_running = False
                        await discord_interface.close()
                    elif interface_name == "console":
                        await console_interface.stop()
                    await task # Wait for the interface's task to finish its shutdown
            print("Kinecho Commander: All interfaces stopped. Exiting.")
            break # Exit the command loop

        elif command == "help":
            print("\n--- Kinecho Commander Commands ---")
            print("  start [discord|console] - Start a specific interface.")
            print("  stop  [discord|console] - Stop a specific interface.")
            print("  status                  - Show the status of all interfaces.")
            print("  quit / exit             - Stop all running interfaces and exit Kinecho.")
            print("  help                    - Show this help message.")
            print("----------------------------------\n")
        elif command: # If command is not empty but not recognized
            print(f"Kinecho Commander: Unknown command '{command}'. Type 'help' for commands.")

    print("Kinecho Main: Kinecho Commander exited.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKinecho Main: Shutdown initiated by user via KeyboardInterrupt.")
    except Exception as e:
        print(f"Kinecho Main: An unexpected error occurred: {e}")
    finally:
        print("Kinecho Main: Application finished.")