import chatbot
# Import the new DiscordInterface from the interfaces package
from interfaces.discord_interface import DiscordInterface, intents # We also need intents from discord_interface

print("Kinecho application starting up...")

# Choose which interface to run (for now, hardcoded to Discord)
# In the future, this will run both console AND Discord interlinkedly.
interface_to_run = "discord" # Or "console" for testing without Discord

if interface_to_run == "discord":
    print("Starting Kinecho Discord Bot...")
    # Create an instance of the new DiscordInterface class
    # Pass the chatbot.get_chat_response function as the chatbot_processor_func
    # and the intents defined in discord_interface.py
    discord_interface_instance = DiscordInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        intents=intents
    )
    # Call the start method on the instance
    discord_interface_instance.start()
    # Note: The code below this line will only execute after the bot stops (e.g., Ctrl+C)
    print("Kinecho Discord Bot started.")
elif interface_to_run == "console":
    # This is a basic console loop for testing the chatbot directly
    print("Starting Kinecho in console mode (type 'quit' to exit).")
    while True:
        user_message = input("You: ")
        if user_message.lower() == 'quit':
            break
        # Note: For console mode, history and channel_id are simplistically handled.
        # In a full console interface, these would be managed more robustly.
        response = chatbot.get_chat_response(user_message, history=None, channel_id="console_test")
        print(f"Kinecho: {response}")
else:
    print(f"Unknown interface: {interface_to_run}. Exiting.")


print("\nApplication finished for now.")