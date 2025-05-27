import asyncio
from typing import Callable, List, Dict, Any

# Import the base KinechoInterface
from interfaces.base_interface import KinechoInterface

# Import memory_manager and chatbot for internal use by this interface
import memory_manager
import chatbot

class ConsoleInterface(KinechoInterface):
    def __init__(self, *, chatbot_processor_func: Callable[[str, List[Dict[str, str]], str], str]):
        super().__init__(chatbot_processor_func=chatbot_processor_func)
        self._quit_event = asyncio.Event() # Event to signal when the console interface should quit
        print("Console Interface: Initialized.")

    async def initialize_interface(self):
        """
        Initializes the console interface.
        It no longer contains the input loop directly; it just prepares the interface.
        The main loop (which calls process_incoming_text) will be in kinecho_main.py.
        """
        print("Console Interface: Ready for input. Type 'quit' to return to Commander.")
        self.is_running = True
        # This interface itself doesn't loop for input, it just waits to be told to stop.
        # It will process messages via process_incoming_text when the commander forwards them.
        await self._quit_event.wait() # Wait until the stop() method sets this event
        print("Console Interface: Shutting down.")


    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message to the console (prints it).
        For console, channel_id is not strictly used but kept for interface consistency.
        """
        print(f"Kinecho: {message_content}")

    async def receive_message(self, message: str):
        """
        Processes an incoming message string from the console.
        This method will be called by the Kinecho Commander.
        """
        if not self.is_running:
            # Should not happen if commander is correctly managing tasks
            print("Console Interface: Received message while not running.")
            return

        user_message = message.strip()

        if user_message.lower() == 'quit':
            await self.stop() # Signal graceful shutdown
            return

        print(f"You: {user_message}") # Echo user's message

        # --- History Collection from Memory Manager ---
        # Using a fixed channel ID for console interactions
        console_channel_id = "kinecho_console_chat"
        memory = memory_manager.load_memory()
        history = memory_manager.get_channel_memory(memory, console_channel_id)

        # --- Get response from Chatbot Processor ---
        response = self.chatbot_processor(user_message, history, console_channel_id)

        # --- Send Response and Update Memory ---
        await self.send_message(console_channel_id, response)

        # Update persistent memory with the new user query and bot response
        memory_manager.update_channel_memory(
            memory,
            console_channel_id,
            [{"role": "user", "content": user_message},
             {"role": "assistant", "content": response}]
        )
        memory_manager.save_memory(memory)


    async def stop(self):
        """
        Stops the console interface gracefully.
        Signals the initialize_interface task to finish.
        """
        self.is_running = False
        self._quit_event.set() # Set the event to release initialize_interface.wait()
        print("Console Interface: Received stop command.")