import asyncio
from typing import Callable, List, Dict, Any
from interfaces.base_interface import KinechoInterface
import memory_manager
import chatbot

class ConsoleInterface(KinechoInterface):
    # Updated __init__ to accept interface_instances and match new chatbot_processor_func signature
    def __init__(self, *,
                 chatbot_processor_func: Callable[[str, str, str, str, str, Dict[str, Any]], str], # Updated Callable
                 interface_instances: Dict[str, Any]): # NEW: Add interface_instances
        super().__init__(chatbot_processor_func=chatbot_processor_func)
        self._quit_event = asyncio.Event() # Event to signal when the console interface should quit
        self.interface_instances = interface_instances # Store the reference to the dictionary
        print("Console Interface: Initialized.")

    async def initialize_interface(self):
        """
        Initializes the console interface.
        It sets up for input, but the main input loop will be in kinecho_main.py.
        """
        self._quit_event.clear()
        print("Console Interface: Ready for input. Type 'quit' to return to Commander.")
        self.is_running = True
        await self._quit_event.wait()
        print("Console Interface: Shutting down.")

    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message to the console.
        """
        print(f"Kinecho: {message_content}")

    # Renamed and updated receive_message to conform to KinechoInterface's signature (message: Any)
    # and pass new arguments to chatbot_processor
    async def receive_message(self, message: Any): # Now accepts a 'message' object
        # For console, we'll use predefined IDs/names or extract from a mock object
        user_id = message.author.id
        user_name = message.author.display_name
        channel_id = message.channel.id
        query = message.content # Extract content from the mock message

        # For console, guild_id is always None
        guild_id = None

        print(f"DEBUG: Message from {user_name} ({user_id}) in channel {channel_id} (Guild: {guild_id}): {query}")

        # Load memory for the console user and channel
        memory = memory_manager.load_memory()
        # Create or get user for console context
        memory_manager.create_or_get_user(memory, user_id, user_name, "console", discord_id=None)

        # Add user's message as an event
        memory_manager.add_user_event(memory, user_id, "message_in", channel_id, query, "console")
        memory_manager.update_channel_memory(memory, channel_id, [{"role": "user", "content": query}])
        memory_manager.save_memory(memory)

        # --- Get response from Chatbot Processor ---
        response_content = await self.chatbot_processor( # AWAIT the async function call
            query,
            user_id,
            user_name,
            channel_id,
            guild_id, # <-- Pass guild_id (None for console)
            self.interface_instances # <-- Pass the interface_instances
        )

        # --- Send Response and Update Memory ---
        await self.send_message(channel_id, response_content)

        # Add bot's response as an event
        memory_manager.add_user_event(memory, user_id, "message_out", channel_id, response_content, "console")
        memory_manager.update_channel_memory(memory, channel_id, [{"role": "assistant", "content": response_content}])
        memory_manager.save_memory(memory)

    async def stop(self):
        """
        Stops the console interface gracefully.
        Signals the initialize_interface task to finish.
        """
        self.is_running = False
        self._quit_event.set()
        print(f"Console Interface: {self.__class__.__name__} closed successfully.")
