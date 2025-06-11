import asyncio
import os
import sys
from dotenv import load_dotenv
from typing import List, Dict, Any, Callable
from interfaces.discord_bot_interface import DiscordInterface, intents
from interfaces.console_interface import ConsoleInterface
import chatbot
import memory_manager

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # This isn't directly used in main, but good practice to be safe

# --- Chatbot Processor Function ---
def kinecho_chatbot_processor(user_id: str, user_message: str, channel_id: str, interface_type: str) -> str:
    """
    Processes a user message using the core chatbot logic.
    This function is passed to each interface.
    """
    print(f"DEBUG: kinecho_chatbot_processor received: user_id={user_id}, message='{user_message}', channel_id={channel_id}, interface_type={interface_type}")
    response = chatbot.get_chat_response(
        user_id=user_id,
        prompt_text=user_message, # Renamed query to user_message for clarity
        channel_id=channel_id,
        interface_type=interface_type
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

        # STEP 1: Parse the command for the main loop immediately
        parts = command_line.split()
        command = parts[0].lower() if parts else "" # Convert command to lowercase for consistent matching
        target_interface = parts[1].lower() if len(parts) > 1 else "" # Convert target to lowercase

        # STEP 2: Handle main Kinecho Commander commands FIRST
        # These commands should always be processed by the commander, regardless of console state.
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
                    await asyncio.sleep(0.01)
                    continue
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
                    await active_interface_tasks["discord"] # Wait for the task to finish
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
            shutdown_tasks = []
            for interface_name, task in list(active_interface_tasks.items()):
                print(f"Kinecho Commander: Attempting to stop {interface_name} interface.")
                if interface_name == "discord":
                    if discord_interface:
                        # Signal discord bot to stop and add its close method to shutdown tasks
                        discord_interface.is_running = False
                        shutdown_tasks.append(asyncio.create_task(discord_interface.close()))
                elif interface_name == "console":
                    if console_interface:
                        # Signal console interface to stop and add its stop method to shutdown tasks
                        shutdown_tasks.append(asyncio.create_task(console_interface.stop()))
            
            # Wait for all explicit interface shutdown calls to complete
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True) # Use return_exceptions=True to allow other tasks to complete even if one fails

            # Now, wait for the main tasks of each interface to complete if they haven't already
            for interface_name, task in list(active_interface_tasks.items()):
                if not task.done(): # If the main interface task is still running (e.g., waiting for its _quit_event)
                    print(f"Kinecho Commander: Waiting for {interface_name} task to finish...")
                    await task # Await its completion

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

        # STEP 3: If it's NOT a commander command AND the console is active,
        # then route it to the console interface for chatbot processing.
        # This condition now only runs if the input was NOT a commander command.
        elif prompt_text == "You (Kinecho Console) > " and command_line: # Ensure command_line is not empty
            # Create a mock_message object as console_interface.receive_message expects it
            user_id = "console_user" # A placeholder user ID for console
            channel_id = "kinecho_console_chat" # A placeholder channel ID for console
            mock_message = type('MockMessage', (object,), {
                'author': type('MockAuthor', (object,), {'id': user_id, 'display_name': "You (Console)"}),
                'content': command_line,
                'channel': type('MockChannel', (object,), {'id': channel_id})
            })()
            try:
                await console_interface.receive_message(mock_message)
            except Exception as e:
                print(f"ERROR: Console interface message processing failed: {e}")
            # No 'continue' needed here. The loop will naturally re-evaluate the prompt.

        elif command: # This catches any remaining non-empty commands that weren't recognized
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
