import asyncio
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Callable

# Import both interfaces
from interfaces.discord_bot_interface import DiscordInterface, intents
from interfaces.console_interface import ConsoleInterface

# Import chatbot and memory_manager (used by the chatbot_processor_func)
import chatbot
import memory_manager

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Ensure this is loaded if your chatbot needs it directly here

# --- Chatbot Processor Function ---
# This function acts as the central brain. Both Discord and Console interfaces will call this.
def kinecho_chatbot_processor(query: str, history: List[Dict[str, str]], channel_id: str) -> str:
    """
    Processes a user query using the core chatbot logic.
    This function is passed to each interface.
    """
    # Call your existing get_chat_response from chatbot.py
    response = chatbot.get_chat_response(
        prompt_text=query,
        history=history,
        channel_id=channel_id # Pass channel_id for memory management within chatbot.py if it uses it
    )
    return response

async def main():
    """
    Main asynchronous function to initialize and run Kinecho interfaces.
    """
    print("Kinecho Main: Starting Kinecho...")

    # 1. Initialize Discord Interface
    # Use the global intents defined in discord_bot_interface.py
    discord_interface = DiscordInterface(
        chatbot_processor_func=kinecho_chatbot_processor,
        intents=intents
    )
    print("Kinecho Main: Discord Interface initialized.")

    # 2. Initialize Console Interface
    console_interface = ConsoleInterface(
        chatbot_processor_func=kinecho_chatbot_processor
    )
    print("Kinecho Main: Console Interface initialized.")

    # 3. Start both interfaces concurrently using asyncio.gather
    # discord_interface.start() is an async method of discord.Client
    # console_interface.initialize_interface() is the async startup for the console
    discord_task = asyncio.create_task(discord_interface.start(DISCORD_BOT_TOKEN))
    console_task = asyncio.create_task(console_interface.initialize_interface())


    # Keep the main loop running until all tasks are done (or one of them exits)
    print("Kinecho Main: Running Discord and Console interfaces concurrently...")
    await asyncio.gather(discord_task, console_task)
    print("Kinecho Main: All interfaces stopped.")

if __name__ == "__main__":
    # Ensure memory is loaded at startup
    # memory_manager.load_memory() # This can be loaded within the chatbot_processor or interfaces as needed.
                                # Calling it here might be redundant if interfaces load it on first use.
                                # For simplicity, we can let interfaces manage their own memory loading.

    # Run the main asynchronous function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKinecho Main: Shutting down Kinecho...")
    finally:
        # Any final cleanup could go here
        pass