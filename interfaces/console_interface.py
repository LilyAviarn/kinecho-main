import asyncio
import sys
from typing import Any, Callable, Dict, List

# Import the base KinechoInterface
from interfaces.base_interface import KinechoInterface

# Import memory_manager and chatbot for internal use by this interface
import memory_manager
import chatbot # Assuming chatbot.get_chat_response for history fetching as in DiscordInterface

# ConsoleInterface will inherit from KinechoInterface
class ConsoleInterface(KinechoInterface):
    def __init__(self, *, chatbot_processor_func: Callable[[str, List[Dict[str, str]], str], str]):
        # Initialize the base KinechoInterface
        super().__init__(chatbot_processor_func=chatbot_processor_func) # Use super() for cleaner inheritance call
        self.channel_id = "console" # A fixed channel ID for the console
        print("Console Interface: Initialized.")

    async def initialize_interface(self):
        """
        Starts the console interface.
        This method will set up the console input loop.
        """
        print("Console Interface: Type your message and press Enter. Type 'exit' to quit.")
        self.is_running = True
        # Start the non-blocking input reader as a background task
        asyncio.create_task(self._read_console_input())
        print("Console Interface: Ready to receive input.")

    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message to the console.
        Args:
            channel_id: Ignored for console, as it's a single destination.
            message_content: The content to print to the console.
        """
        if self.is_running: # Only print if the interface is still active
            # Print to stdout, ensuring it doesn't interfere with future input prompts
            sys.stdout.write(f"\nKinecho (Console): {message_content}\n> ")
            sys.stdout.flush() # Ensure the output is immediately visible
        else:
            print(f"\nKinecho (Console) (Interface Stopped): {message_content}")

    async def receive_message(self, user_input: str):
        """
        Processes incoming messages (user input from console).
        This method routes input to the chatbot_processor and sends back responses.
        Args:
            user_input: The string input from the console user.
        """
        print(f"Console Interface: Processing input: {user_input}") # Debug print for console input

        # Simple exit command
        if user_input.lower() == 'exit':
            self.stop() # Stop the console interface gracefully
            return

        # For console, we'll use a fixed 'channel_id' for memory
        channel_id = self.channel_id

        # --- History Collection from Memory Manager (no Discord history for console) ---
        memory = memory_manager.load_memory()
        history = memory_manager.get_channel_memory(memory, channel_id)

        # --- Get response from Chatbot Processor ---
        response = self.chatbot_processor(user_input, history, channel_id)

        # --- Send Response and Update Memory ---
        await self.send_message(channel_id, response)

        # Update persistent memory with the new user query and bot response
        memory_manager.update_channel_memory(
            memory,
            channel_id,
            [{"role": "user", "content": user_input},
             {"role": "assistant", "content": response}]
        )
        memory_manager.save_memory(memory)

    async def _read_console_input(self):
        """
        Internal helper to read input from the console asynchronously without blocking.
        """
        while self.is_running:
            # Use asyncio.to_thread for blocking input operations in an async context
            # This prevents `input()` from blocking the entire asyncio loop
            user_input = await asyncio.to_thread(input, "> ")
            if user_input: # Only process if input is not empty
                await self.receive_message(user_input)
            # If input is empty, just reprompt