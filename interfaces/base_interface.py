from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List

class KinechoInterface(ABC):
    """
    Abstract Base Class for all Kinecho interfaces (e.g., Discord, GUI, Console).
    Defines the common methods that all interfaces must implement.
    """

    def __init__(self, chatbot_processor_func: Callable[[str, Any, Any], str]):
        """
        Initializes the interface with a function to process chatbot messages.
        Args:
            chatbot_processor_func: The function (e.g., chatbot.get_chat_response)
                                    that handles AI responses.
        """
        self.chatbot_processor = chatbot_processor_func
        self.is_running = False

    @abstractmethod
    def start(self):
        """
        Starts the interface and begins listening for input.
        This method should contain the main loop or connection logic for the interface.
        """
        pass

    @abstractmethod
    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message through this interface to a specific channel/destination.
        Args:
            channel_id: The identifier for the channel or destination.
            message_content: The content of the message to send.
        """
        pass

    @abstractmethod
    async def receive_message(self, message: Any):
        """
        Processes an incoming message from the interface.
        This method is typically an event handler that routes incoming messages
        to the chatbot_processor and sends back responses.
        Args:
            message: The raw message object from the specific interface (e.g., discord.Message).
        """
        pass

    def stop(self):
        """
        Stops the interface gracefully.
        Concrete implementations should override this if specific cleanup is needed.
        """
        self.is_running = False
        print(f"Interface {self.__class__.__name__} stopped.")