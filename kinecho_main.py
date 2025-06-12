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

# Global variable to hold active interface instances, needed for tool calling
# We initialize them as None, and they will be set in main()
global_discord_interface: DiscordInterface = None
global_console_interface: ConsoleInterface = None


# --- Define Tools Available to the Chatbot ---
# This is a list of dictionaries, where each dictionary describes a tool.
# The structure follows OpenAI's tool definition format.
AVAILABLE_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_discord_user_status",
            "description": "Retrieves the online status, custom status, display name, username, joined date, and shared guild of a Discord user by their user ID. This works only if the bot is in a shared server with the user and has the necessary permissions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The unique Discord ID of the user whose status is to be retrieved. This is a numeric string (e.g., '212343502422540288')."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Provides the current date, time, and day of the week for a specified timezone. If no timezone is provided, it defaults to 'America/New_York' (Eastern Standard Time).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_str": {
                        "type": "string",
                        "description": "The IANA timezone string (e.g., 'America/New_York', 'Europe/London'). This argument is optional."
                    }
                },
                "required": [] # timezone_str is optional
            }
        }
    }
    {
        "type": "function",
        "function": {
            "name": "get_conversation_history_for_channel",
            "description": "Retrieves recent conversation history (messages) from a specific Discord channel. Useful for recalling what was discussed in other channels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The Discord ID of the channel whose conversation history is to be retrieved. This is a numeric string (e.g., '123456789012345678')."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of recent messages to retrieve (default: 10).",
                        "default": 10
                    }
                },
                "required": ["channel_id"]
            }
        }
    }
    # Add any other tool definitions here if you have them
]

# --- Chatbot Processor Function ---
# This function now takes an additional parameter for the interface instances
async def kinecho_chatbot_processor(user_id: str, user_message: str, channel_id: str, interface_type: str, interface_instances: Dict[str, Any]) -> str:
    """
    Processes a user message using the core chatbot logic, with access to available interfaces.
    This function is passed to each interface.

    Args:
        user_id (str): The ID of the user sending the message.
        user_message (str): The content of the user's message.
        channel_id (str): The ID of the channel where the message originated.
        interface_type (str): The type of interface (e.g., "discord", "console").
        interface_instances (Dict[str, Any]): A dictionary of active interface instances (e.g., {"discord": DiscordInterface_instance}).

    Returns:
        str: The chatbot's response message.
    """
    print(f"DEBUG: kinecho_chatbot_processor received: user_id={user_id}, message='{user_message}', channel_id={channel_id}, interface_type={interface_type}")
    
    # Pass the available tools and the interface instances to the chatbot's get_chat_response
    # !!! FIX: AWAIT THE ASYNC FUNCTION CALL !!!
    response = await chatbot.get_chat_response(
        user_id=user_id,
        prompt_text=user_message,
        channel_id=channel_id,
        interface_type=interface_type,
        available_tools=AVAILABLE_TOOLS_DEFINITIONS, # Pass the defined tools
        interface_instances=interface_instances      # Pass the interface instances
    )
    return response

async def main():
    """
    Main asynchronous function to initialize Kinecho Commander and manage interfaces.
    """
    print("Kinecho Main: Initializing Kinecho Commander...")

    # Initialize interface instances (don't start them yet)
    # Assign them to the global variables
    global global_discord_interface
    global global_console_interface

    # FIX: The lambda functions must also be async if they're calling an async function
    global_discord_interface = DiscordInterface(
        chatbot_processor_func=lambda u, m, c, i: kinecho_chatbot_processor(u, m, c, i, {"discord": global_discord_interface, "console": global_console_interface}),
        intents=intents
    )
    global_console_interface = ConsoleInterface(
        chatbot_processor_func=lambda u, m, c, i: kinecho_chatbot_processor(u, m, c, i, {"discord": global_discord_interface, "console": global_console_interface})
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
        if "console" in active_interface_tasks and not active_interface_tasks["console"].done() and global_console_interface.is_running:
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
                    discord_task = asyncio.create_task(global_discord_interface.initialize_interface(DISCORD_BOT_TOKEN))
                    active_interface_tasks["discord"] = discord_task
                else:
                    print("Kinecho Commander: Discord Interface already running.")
            elif target_interface == "console":
                if "console" not in active_interface_tasks or active_interface_tasks["console"].done():
                    print("Kinecho Commander: Starting Console Interface...")
                    console_task = asyncio.create_task(global_console_interface.initialize_interface())
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
                    global_discord_interface.is_running = False # Signal to the bot to stop
                    await global_discord_interface.close() # Calls discord.Client's internal close
                    await active_interface_tasks["discord"] # Wait for the task to finish
                    del active_interface_tasks["discord"]
                else:
                    print("Kinecho Commander: Discord Interface not running.")
            elif target_interface == "console":
                if "console" in active_interface_tasks and not active_interface_tasks["console"].done():
                    print("Kinecho Commander: Stopping Console Interface...")
                    await global_console_interface.stop() # This will set is_running=False and _quit_event
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
                    if global_discord_interface:
                        # Signal discord bot to stop and add its close method to shutdown tasks
                        global_discord_interface.is_running = False
                        shutdown_tasks.append(asyncio.create_task(global_discord_interface.close()))
                elif interface_name == "console":
                    if global_console_interface:
                        # Signal console interface to stop and add its stop method to shutdown tasks
                        shutdown_tasks.append(asyncio.create_task(global_console_interface.stop()))
            
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
                # !!! FIX: AWAIT THE ASYNC FUNCTION CALL !!!
                await global_console_interface.receive_message(mock_message)
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
