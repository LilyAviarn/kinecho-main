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
        # IMPORTANT: The chatbot_processor_func signature will change soon,
        # but for now, we're keeping it compatible until kinecho_main.py is updated.
        super().__init__(chatbot_processor_func=chatbot_processor_func)
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
        Reverted to original flexibility for now to avoid breaking Commander before its update.
        """
        try:
            # If a channel ID string is passed, try to fetch the channel object
            if isinstance(target_channel, (str, int)):
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

            # Extract user_id and user_name for the new memory system
            user_id = str(message.author.id) # Use Discord user ID as our unique user_id
            user_name = message.author.display_name if message.author.display_name else message.author.name

            # Load memory and ensure user exists
            memory = memory_manager.load_memory()
            memory_manager.create_or_get_user(memory, user_id, user_name, "discord", discord_id=user_id)
            print(f"DEBUG: Message from {user_name} ({user_id}) in channel {channel_id}. Content: '{message.content}'")


            # Store the original message content *before* mention removal for the user event.
            original_message_content = message.content

            # Remove bot mention from query for processing if it's a guild message and a direct mention
            query = message.content # query will be the content passed to the chatbot.
            if is_direct_mention and message.guild: # Only remove mention if in a guild
                query = re.sub(r'<@!?%s>' % self.user.id, '', query).strip()
#                print(f"DEBUG: Query after mention removal: '{query}'")

            # If the query is empty after mention removal (e.g., just a mention like "@Kinecho")
            if not query:
                # print("DEBUG: Query is empty after mention removal. Sending a default prompt.")
                if is_direct_mention: # Only respond to empty mention if it was a direct one
                    await self.send_message(channel, f"Hey <@{message.author.id}>, what's up?")
                return

            # Add user's message as an event BEFORE calling the chatbot, using the *original* content
            memory_manager.add_user_event(memory, user_id, "message_in", channel_id, original_message_content, "discord")
            memory_manager.save_memory(memory) # Save immediately after user message event
#            print("DEBUG: User message event added and memory saved.")

            # --- Get response from Chatbot Processor ---
            print(f"DEBUG: Calling chatbot_processor with query: '{query}' for user {user_id} in channel {channel_id}")
            # Update this line to pass user_id, query, channel_id, and interface_type
            response_content = self.chatbot_processor(
                user_id,         # User ID from Discord
                query,    # Cleaned user message
                channel_id,      # Channel ID from Discord
                "discord"        # Explicitly state the interface type
            )
#            print(f"DEBUG: Raw response from chatbot_processor (chatbot.py): '{response_content}'")

            try: # Prepend a mention to the original message author (only if it was a guild mention)
                response_to_send = response_content
                if is_direct_mention and message.guild:
                    response_to_send = f"<@{message.author.id}> {response_content}"
                print(f"DEBUG: Final response to send: '{response_to_send}'")

                # --- Send Response and Update Memory ---
                # Pass the channel object directly to send_message
                await self.send_message(channel, response_to_send)

                # Now, add the bot's response as an event using the *new* memory system
                # Use 'message_out' type for outgoing messages from the assistant
                memory_manager.add_user_event(memory, user_id, "message_out", channel_id, response_to_send, "discord") # Store the full response sent
                memory_manager.save_memory(memory) # Save after bot response event
        #        print("DEBUG: Bot response event added and memory saved.")
       
            except Exception as e:
                print(f"ERROR: An unexpected error occured while preparing/sending Discord response or saving memory: {e}")
                return   

#       else:
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
        print('Discord Interface: Connection interrupted; Bot has resumed.')

    async def close(self):
        """
        Overrides discord.Client.close.
        Stops the Discord bot client gracefully.
        """
        print("Discord Interface: Closing connection...")
        self.is_running = False # Set the running flag to False
        await super().close() # Call the parent discord.Client's close method
        print("Discord Interface: Connection closed successfully.")