import discord
import os
import re
from dotenv import load_dotenv
from typing import Any, Callable, List, Dict
from interfaces.base_interface import KinechoInterface
import memory_manager
import chatbot

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

LAST_RESPONSE_MESSAGE_ID = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.guild_messages = True
intents.dm_messages = True

class DiscordInterface(KinechoInterface, discord.Client):
    def __init__(self, *, chatbot_processor_func: Callable[[str, List[Dict[str, str]], str], str], intents: discord.Intents):
        KinechoInterface.__init__(self, chatbot_processor_func=chatbot_processor_func)
        discord.Client.__init__(self, intents=intents)
        print("Discord Interface: Initialized.")

    async def initialize_interface(self, bot_token: str):
        """
        Connects the Discord bot client to Discord using the provided token.
        This is the main entry point to start the Discord bot's event loop.
        """
        print("Discord Interface: Connecting to Discord...")
        self.is_running = True # Set the running flag
        try:
            await self.start(bot_token) # This blocks until the bot disconnects
        except discord.LoginFailure:
            print("Discord Interface Error: Failed to login. Check your bot token.")
            self.is_running = False
        except Exception as e:
            print(f"Discord Interface Error: An error occurred during startup: {e}")
            self.is_running = False
        finally:
            if self.is_running: # Only print if bot was actually running before `finally` block
                print("Discord Interface: Connection closed.")


    async def send_message(self, target_channel: Any, message_content: str):
        """
        Sends a message through the Discord interface to a specific channel.
        target_channel can be a channel ID (str) or a discord.abc.Messageable object.
        """
        try:
            # If a channel ID string is passed, try to fetch the channel object
            if isinstance(target_channel, str):
                channel_id_int = int(target_channel)
                channel = self.get_channel(channel_id_int)
                if not channel: # Fallback to fetch if not in cache
                    channel = await self.fetch_channel(channel_id_int)
            else: # Assume it's already a discord.abc.Messageable object (e.g., discord.TextChannel)
                channel = target_channel

            if channel and isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.Thread)):
                message = await channel.send(message_content)
                LAST_RESPONSE_MESSAGE_ID[str(channel.id)] = message.id
                print(f"Discord Interface: Sent response to {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}")
            else:
                print(f"Discord Interface Error: Channel with ID/object {target_channel} not found or not a text/DM/thread channel. Content: '{message_content}'")
        except discord.Forbidden:
            print(f"Discord Interface Error: Bot lacks permissions to send message in {target_channel.name if hasattr(target_channel, 'name') else 'DM'}/{target_channel.id}.")
        except Exception as e:
            print(f"Discord Interface Error sending message to {target_channel.id if hasattr(target_channel, 'id') else 'unknown'}: {e}")

    async def on_message(self, message: discord.Message):
        await self.receive_message(message)

    # This method explicitly implements the abstract method 'receive_message' from KinechoInterface.
    # It contains the core logic for processing incoming messages.
    async def receive_message(self, message: Any): # 'message' is expected to be a discord.Message object here
        """
        Processes an incoming message from Discord.
        This method is the KinechoInterface abstraction for incoming messages.
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
#           print(f"DEBUG: Message ignored: From bot itself ({self.user.name}).")
            return

        # Ensure the bot is intended to be running (controlled by Commander)
        if not self.is_running:
            print(f"ERROR: Message ignored: Discord Interface is not flagged as running by Commander. How did you manage this?")
            return

        # Determine if the message is a direct mention or a DM
        is_direct_mention = self.user.mentioned_in(message)
        is_dm = isinstance(message.channel, discord.DMChannel)
#        print(f"DEBUG: Is direct mention: {is_direct_mention}")
#        print(f"DEBUG: Is DM: {is_dm}")


        # Extract the channel object and its ID for memory management
        channel = message.channel
        channel_id = str(channel.id)

        # If it's a DM, always process it. If it's a guild message, only process if mentioned.
        if is_dm or is_direct_mention:
#            print(f"DEBUG: Message qualifies for processing (DM or Direct Mention).")

            # Remove bot mention from query for processing if it's a guild message and a direct mention
            query = message.content
            if is_direct_mention and message.guild: # Only remove mention if in a guild
                original_query_with_mention = query # For debug logging
                query = re.sub(r'<@!?%s>' % self.user.id, '', query).strip()
#                print(f"DEBUG: Original query (with mention): '{original_query_with_mention}'")
                print(f"DEBUG: Query after mention removal: '{query}'")

            # If the query is empty after mention removal (e.g., just a mention like "@Kinecho")
            if not query:
#                print("DEBUG: Query is empty after mention removal. Sending a default prompt.")
                if is_direct_mention: # Only respond to empty mention if it was a direct one
                    await self.send_message(channel, f"Hey <@{message.author.id}>, what's up?")
                return

            # --- History Collection from Memory Manager ---
            memory = memory_manager.load_memory()
            history = memory_manager.get_channel_memory(memory, channel_id)
            print(f"DEBUG: History fetched for channel {channel_id}: {history}")

            # --- Get response from Chatbot Processor ---
            print(f"DEBUG: Calling chatbot_processor with query: '{query}'")
            response = self.chatbot_processor(query, history, channel_id)

            # Prepend a mention to the original message author (only if it was a guild mention)
            response_to_send = response
            if is_direct_mention and message.guild:
                response_to_send = f"<@{message.author.id}> {response}"
            print(f"DEBUG: Final response to send: '{response_to_send}'")


            # --- Send Response and Update Memory ---
            # Pass the channel object directly to send_message
            await self.send_message(channel, response_to_send)
            print(f"Discord Interface: Sent response to {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}.")

            # Update persistent memory with the new user query (cleaned) and bot response (raw)
            memory_manager.update_channel_memory(
                memory,
                channel_id,
                [{"role": "user", "content": query}, # Store the cleaned query
                 {"role": "assistant", "content": response}] # Store the raw bot response
            )
            memory_manager.save_memory(memory)
            print("DEBUG: Memory updated and saved.")
#        else:
            # If bot not mentioned and not a DM, just ignore.
#            print(f"DEBUG: Message ignored (not DM or direct mention). Content: '{message.content}'")

    # --- Discord.py Specific Event Overrides (that don't fulfill KinechoInterface abstract methods) ---

    async def on_ready(self):
        """
        Overrides discord.Client.on_ready.
        Called when the bot successfully connects to Discord.
        """
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        # Set bot's presence
        await self.change_presence(activity=discord.Game(name="with memories"))
        print("Discord Interface: Bot is ready and presence set.")

    async def on_resumed(self):
        """
        Overrides discord.Client.on_resumed.
        Called when the bot successfully resumes a session after a disconnect.
        """
        print('Discord Interface: Bot has resumed.')

    async def close(self):
        """
        Overrides discord.Client.close.
        Stops the Discord bot client gracefully.
        """
        print("Discord Interface: Closing connection...")
        self.is_running = False # Set the running flag to False
        await super().close() # Call the parent discord.Client's close method
        print("Discord Interface: Connection closed successfully.")