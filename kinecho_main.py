import chatbot
# Import the DiscordInterface from the interfaces package
from interfaces.discord_bot_interface import DiscordInterface, intents

print(f"Executing app_main.py from: {__file__}")

# This will contain the instance of the selected interface
# interface_instance = None # Not strictly needed if logic is conditional

# Choose which interface to run (for now, hardcoded to Discord)
interface_to_run = "discord" # Or "console" for testing without Discord

if interface_to_run == "discord":
    print("DiscordInterface module:", DiscordInterface.__module__)
    print("DiscordInterface start method defined in:", DiscordInterface.start.__code__.co_filename)
    print("Discord Interface: Initialized.")
    discord_interface_instance = DiscordInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        intents=intents
    )
    # Call the start method on the instance
    discord_interface_instance.start()
    # Note: The code below this line will only execute after the bot stops (e.g., Ctrl+C)
    print("Discord Interface: Bot stopped.")
    print("If you see this message, the bot started without the 'reconnect' error.")

elif interface_to_run == "console":
    # This is a basic console loop for testing the chatbot directly
    print("Starting Kinecho in console mode (type 'quit' to exit).")
    while True:
        user_message = input("You: ")
        if user_message.lower() == 'quit':
            break
        response = chatbot.get_chat_response(user_message, history=[], channel_id="console_test")
        print(f"Kinecho: {response}")