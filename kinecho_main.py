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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
                        "description": "The Discord ID of the user whose status is to be retrieved."
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
            "description": "Retrieves the current date and time in a specified timezone. Defaults to America/Chicago if no timezone is provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_str": {
                        "type": "string",
                        "description": "The IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Defaults to 'America/Chicago'."
                    }
                },
                "required": []
            }
        }
    },
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
                        "description": "The Discord ID of the channel whose conversation history is to be retrieved."
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
    },
    {
        "type": "function",
        "function": {
            "name": "add_user_derived_fact",
            "description": "Adds a new high-level, summarized fact or insight about a specific Discord user to Kinecho's long-term memory. This should be used when Kinecho learns a significant piece of information about a user (e.g., their hobby, a personal preference, a recurring statement).",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord ID of the user to whom the fact pertains."
                    },
                    "fact_content": {
                        "type": "string",
                        "description": "The content of the derived fact to be stored."
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "Optional: The Discord ID of the channel where the fact was derived or is relevant."
                    }
                },
                "required": ["user_id", "fact_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_derived_facts",
            "description": "Retrieves high-level, summarized facts or insights about a specific Discord user that Kinecho has learned over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord ID of the user whose derived facts are to be retrieved."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of recent derived facts to retrieve (default: 10).",
                        "default": 10
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    { # NEW TOOL DEFINITION: get_discord_channel_id_by_name
        "type": "function",
        "function": {
            "name": "get_discord_channel_id_by_name",
            "description": "Retrieves the Discord numerical ID for a given channel name. Use this if the user provides a channel name (e.g., '#general', 'bot-commands') but you need the numerical ID to interact with other tools like getting conversation history. Can optionally search within a specific guild if its ID is known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The name of the Discord channel (e.g., 'general', 'bot-commands')."
                    },
                    "guild_id": {
                        "type": "string",
                        "description": "Optional: The Discord ID of the guild (server) to search within, if known. This helps when multiple guilds have channels with the same name."
                    }
                },
                "required": ["channel_name"]
            }
        }
    }
]

async def main():
    global global_discord_interface, global_console_interface

    print("Kinecho Main: Starting Kinecho Commander...")

    interface_instances: Dict[str, Any] = {}

    global_discord_interface = DiscordInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        intents=intents,
        interface_instances=interface_instances
    )
    global_console_interface = ConsoleInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        interface_instances=interface_instances
    )

    interface_instances["discord_interface"] = global_discord_interface
    interface_instances["console_interface"] = global_console_interface

    discord_task = None
    console_task = None

    while True:
        command_line = await asyncio.to_thread(input, "Kinecho Commander > ").strip()

        if command_line.lower() == 'quit':
            print("Kinecho Commander: Initiating graceful shutdown...")
            if global_discord_interface.is_running:
                global_discord_interface.stop()
            if global_console_interface.is_running:
                await global_console_interface.stop()
            break

        elif command_line.lower() == 'start discord':
            if not global_discord_interface.is_running:
                print("Kinecho Commander: Starting Discord interface...")
                discord_task = asyncio.create_task(global_discord_interface.initialize_interface(DISCORD_BOT_TOKEN))
                # Optionally wait for it to be ready, or just let it run in the background
            else:
                print("Discord interface is already running.")
        
        elif command_line.lower() == 'stop discord':
            if global_discord_interface.is_running:
                print("Kinecho Commander: Stopping Discord interface...")
                global_discord_interface.stop()
                if discord_task and not discord_task.done():
                    await discord_task # Wait for the task to finish if it's still running
            else:
                print("Discord interface is not running.")

        elif command_line.lower() == 'start console':
            if not global_console_interface.is_running:
                print("Kinecho Commander: Starting Console interface...")
                console_task = asyncio.create_task(global_console_interface.initialize_interface())
            else:
                print("Console interface is already running.")

        elif command_line.lower() == 'stop console':
            if global_console_interface.is_running:
                print("Kinecho Commander: Stopping Console interface...")
                await global_console_interface.stop()
                if console_task and not console_task.done():
                    await console_task # Wait for the task to finish
            else:
                print("Console interface is not running.")

        elif command_line.lower() == 'status':
            discord_status = "Running" if global_discord_interface.is_running else "Stopped"
            console_status = "Running" if global_console_interface.is_running else "Stopped"
            print(f"Interface Status:")
            print(f"  Discord: {discord_status}")
            print(f"  Console: {console_status}")

        elif command_line.lower() == 'help':
            print("Commands:")
            print("  quit          - Exit the Kinecho Commander.")
            print("  start discord - Start the Discord bot interface.")
            print("  stop discord  - Stop the Discord bot interface.")
            print("  start console - Start the console interface.")
            print("  stop console  - Stop the console interface.")
            print("  status        - Show the running status of interfaces.")
            print("  [your message] - Send a message to the console interface.")

        elif command_line:
            # Treat as a message for the console interface
            user_id = "console_user"
            channel_id = "kinecho_console_chat"
            mock_message = type('MockMessage', (object,), {
                'author': type('MockAuthor', (object,), {'id': user_id, 'display_name': "You (Console)"}),
                'content': command_line,
                'channel': type('MockChannel', (object,), {'id': channel_id}),
                'guild': None
            })()
            try:
                await global_console_interface.receive_message(mock_message)
            except Exception as e:
                print(f"ERROR: Console interface message processing failed: {e}")

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
