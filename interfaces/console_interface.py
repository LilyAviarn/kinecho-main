import asyncio
from typing import Callable, List, Dict, Any
from interfaces.base_interface import KinechoInterface
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
        It sets up for input, but the main input loop will be in kinecho_main.py.
        """
        print("Console Interface: Ready for input. Type 'quit' to return to Commander.")
        self.is_running = True
        # This interface itself doesn't loop for input, it blocks and waits to be told to stop.
        # It will process messages via process_incoming_text when the commander forwards them.
        await self._quit_event.wait() # Wait until the stop() method sets this event
        print("Console Interface: Shutting down.")


    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message to the console. channel_id is not strictly used for console output,
        but kept for API consistency.
        """
        print(f"Kinecho: {message_content}")

    # This method explicitly implements the abstract method 'receive_message' from KinechoInterface.
    # It contains the core logic for processing incoming console messages.
    async def receive_message(self, message: str):
        """
        Processes an incoming message string from the console.
        This method will be called by the Kinecho Commander.
        """
        user_message = message.strip()

        if not self.is_running:
            # Should not happen if commander is correctly managing tasks
            print(f"ERROR: Message ignored: Console Interface is not flagged as running by Commander. ({user_message})")
            return

        if user_message.lower() == 'quit':
            await self.stop() # Signal graceful shutdown
            return

        print(f"You: {user_message}") # Echo user's message to confirm input

        # --- New Memory Handling for Console ---
        # Define console user ID and channel ID. These are fixed for the console.
        console_user_id = "kinecho_console_user_default"
        console_user_name = "Console User"
        console_channel_id = "kinecho_console_chat" # Still use this for channel context in events

        # Load memory and ensure the console user exists in memory
        memory = memory_manager.load_memory()
        memory_manager.create_or_get_user(memory, console_user_id, console_user_name, "console")

        # Add user's message as an event BEFORE calling the chatbot
        memory_manager.add_user_event(memory, console_user_id, "message_in", console_channel_id, user_message, "console")
        memory_manager.save_memory(memory) # Save immediately after user message event
        print("DEBUG: Console user message event added and memory saved.")

        # --- Get response from Chatbot Processor ---
        # IMPORTANT: The chatbot_processor_func signature will still match the *original*
        # one here, as kinecho_main.py is not yet updated.
        # So, we pass 'user_message', 'history' (from old memory), 'channel_id'.
        # Once kinecho_main.py is updated, you will change this call.

        print(f"DEBUG: Calling chatbot_processor with query: '{user_message}'")
        # Update this line to pass user_id, user_message, channel_id, and interface_type
        response_content = self.chatbot_processor(
            console_user_id,    # This variable should be available from earlier in the method
            user_message,
            console_channel_id, # This variable should be available from earlier in the method
            "console"           # Explicitly state the interface type
        )

        # --- Send Response and Update Memory ---
        await self.send_message(console_channel_id, response_content)
        print("Console Interface: Sent response.")

        # Add bot's response as an event
        memory_manager.add_user_event(memory, console_user_id, "message_out", console_channel_id, response_content, "console")
        memory_manager.save_memory(memory) # Save after bot response event
        print("DEBUG: Console bot response event added and memory saved.")


    async def stop(self):
        """
        Stops the console interface gracefully.
        Signals the initialize_interface task to finish.
        """
        self.is_running = False
        self._quit_event.set() # Set the event to release initialize_interface.wait()
        print(f"Console Interface: {self.__class__.__name__} closed successfully.")