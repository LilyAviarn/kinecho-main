import discord
import os
import re
from dotenv import load_dotenv
from typing import Any, Callable, List, Dict # Ensure List and Dict are imported for type hints

# Import the base KinechoInterface
from interfaces.base_interface import KinechoInterface

# Import memory_manager and chatbot for internal use by this interface
import memory_manager
import chatbot # Needed for the old get_chat_response signature for history fetching

# Load environment variables (TOKEN)
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Global dictionaries for Discord-specific state (consider moving to class later if stateful per-instance)
LAST_RESPONSE_MESSAGE_ID = {}

# Define intents outside the class as they are client-wide and don't change per instance.
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.guild_messages = True

# Change class definition to inherit from KinechoInterface AND discord.Client
class DiscordInterface(KinechoInterface, discord.Client):
    def __init__(self, *, chatbot_processor_func: Callable[[str, List[Dict[str, str]], str], str], intents: discord.Intents):
        # Initialize both parent classes correctly
        KinechoInterface.__init__(self, chatbot_processor_func=chatbot_processor_func)
        discord.Client.__init__(self, intents=intents)
        print("Discord Interface: Initialized.")

    # Implementation of abstract methods from KinechoInterface
    def start(self):
        """
        Starts the Discord bot. This should be called in app_main.py.
        """
        print("Discord Interface: Starting bot...")
        try:
            # TOKEN is already loaded globally, but good to be explicit for clarity
            if not TOKEN:
                raise ValueError("DISCORD_BOT_TOKEN environment variable not set.")
            # discord.Client.run() is a blocking call that starts the bot
            # It will run until the bot is disconnected or stopped (e.g., via Ctrl+C)
            super().run(TOKEN)
        except Exception as e:
            print(f"Discord Interface Error: An unexpected error occurred during startup: {e}")
        finally:
            print("Discord Interface: Bot stopped.")


    async def send_message(self, channel_id: int, message_content: str):
        """
        Sends a message to a specific Discord channel.
        Args:
            channel_id (int): The ID of the channel to send the message to.
            message_content (str): The content of the message.
        """
        try:
            channel = self.get_channel(channel_id)
            if channel:
                if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.DMChannel):
                    await channel.send(message_content)
                else:
                    print(f"Discord Interface Warning: Channel {channel_id} is not a text or DM channel. Cannot send message.")
            else:
                print(f"Discord Interface Warning: Channel with ID {channel_id} not found.")
        except Exception as e:
            print(f"Discord Interface Error sending message to channel {channel_id}: {e}")

    async def receive_message(self, message: Any):
        """
        Processes an incoming message from Discord.
        This method is an event handler for on_message.
        Args:
            message (discord.Message): The raw message object from Discord.
        """
        # Ignore messages from the bot itself to prevent infinite loops
        if message.author == self.user:
            return

        # Check if the message is a DM or if the bot is mentioned
        if isinstance(message.channel, discord.DMChannel) or self.user.mentioned_in(message):
            query = message.content
            channel = message.channel
            channel_id = channel.id

            # Remove bot mention from query if it exists
            if self.user.mentioned_in(message):
                query = re.sub(r'<@!?%s>' % self.user.id, '', query).strip()

            print(f"Discord Interface: Received message from {message.author} in {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}: {query}")

            # Fetch recent message history from Discord API
            history = []
            try:
                # Fetch messages before the current one, up to a limit (e.g., 20 messages for context)
                # Ensure we only fetch messages from the user or the bot
                after_message_id = LAST_RESPONSE_MESSAGE_ID.get(channel.id)
                async for msg in channel.history(limit=20, before=message):
                    if msg.author == self.user:
                        history.append({"role": "assistant", "content": msg.content})
                    elif msg.author == message.author: # The user who sent the current message
                        history.append({"role": "user", "content": msg.content})
                    # Stop fetching if we hit a previously responded message
                    if after_message_id and msg.id == after_message_id:
                        break

                history.reverse() # History needs to be oldest first

            except discord.Forbidden:
                print(f"Discord Interface Error: Bot does not have permissions to read message history in {channel.name}.")
                history = [] # Reset history on error
            except discord.HTTPException as e:
                print(f"Discord Interface Error fetching history from Discord: {e}")
                history = [] # Reset history on error


            # Load persistent memory for this channel
            memory = memory_manager.load_memory()
            older_history = memory_manager.get_channel_memory(memory, channel_id)

            # Combine older history with current session's fetched messages (excluding the current query as it's separate)
            combined_history = older_history + history


            # --- Get response from Chatbot Processor ---
            # Pass the combined history and channel_id to the chatbot_processor
            response = self.chatbot_processor(query, combined_history, channel_id) # chatbot.get_chat_response

            # Prepend a mention to the original message author
            response_with_mention = f"<@{message.author.id}> {response}"

            # --- Send Response and Update Memory ---
            await self.send_message(channel.id, response_with_mention)
            print(f"Discord Interface: Sent response to {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}")

            # Update persistent memory with the new user query and bot response
            memory_manager.update_channel_memory(
                memory,
                channel_id,
                [{"role": "user", "content": message.content},
                 {"role": "assistant", "content": response}]
            )
            memory_manager.save_memory(memory)
        else:
            # If bot not mentioned and not a DM, just ignore.
            pass

    # --- Discord.py Specific Event Overrides (that don't fulfill KinechoInterface abstract methods) ---

    async def on_ready(self):
        """
        Overrides discord.Client.on_ready.
        Called when the bot successfully connects to Discord.
        """
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_resumed(self):
        """
        Overrides discord.Client.on_resumed.
        Called when the bot successfully resumes a session.
        """
        print('Bot session resumed.')