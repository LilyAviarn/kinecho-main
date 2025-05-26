import discord
import os
import re
from dotenv import load_dotenv
from typing import Any, Callable, List, Dict # Ensure List is imported for type hints

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
# CHANNEL_HISTORIES is no longer needed globally as memory_manager handles persistence.

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

        # Register on_message as an event handler directly in the init
        # This ensures the instance's on_message method is used for Discord events.
        self.event(self.receive_message)
        print("Discord Interface: Initialized.")

    # --- KinechoInterface Abstract Method Implementations ---

    # 1. Implement the abstract start method from KinechoInterface
    def start(self):
        """
        Starts the Discord bot interface.
        This method is blocking and runs the Discord client.
        """
        print("Discord Interface: Starting bot...")
        self.is_running = True
        # The client.run() call from discord.Client is blocking, so it stays here.
        try:
            super().run(TOKEN) # Call discord.Client's run method
        except discord.LoginFailure:
            print("Discord Interface Error: Failed to log in. Check your bot token.")
        except Exception as e:
            print(f"Discord Interface Error: An unexpected error occurred during startup: {e}")
        finally:
            self.is_running = False
            print("Discord Interface: Bot stopped.")

    # 2. Implement the abstract send_message method from KinechoInterface
    async def send_message(self, channel_id: int, message_content: str):
        """
        Sends a message to a specific Discord channel.
        Args:
            channel_id: The ID of the Discord channel.
            message_content: The content of the message to send.
        """
        try:
            channel = self.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.DMChannel):
                sent_message = await channel.send(message_content)
                LAST_RESPONSE_MESSAGE_ID[channel_id] = sent_message.id
            else:
                print(f"Discord Interface Error: Channel with ID {channel_id} not found or not a text/DM channel.")
        except discord.HTTPException as e:
            print(f"Discord Interface Error sending message to {channel_id}: {e}")
        except Exception as e:
            print(f"Discord Interface Unexpected error sending message: {e}")

    # 3. The KinechoInterface's 'receive_message' concept is fulfilled by discord.py's 'on_message' event.
    #    We adapt 'on_message' to perform the reception and processing.

    # --- Discord.py Event Handlers (overridden from discord.Client) ---

    async def on_ready(self):
        """
        Overrides discord.Client.on_ready.
        Called when the bot successfully connects to Discord.
        """
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------ Discord Bot Ready ------')


    async def on_message(self, message: discord.Message):
        """
        Overrides discord.Client.on_message.
        Processes incoming messages from Discord.
        """
        # Ignore messages from self to prevent infinite loops
        if message.author == self.user:
            # Update LAST_RESPONSE_MESSAGE_ID only if it's the bot's own message
            # This helps in history retrieval for future context
            LAST_RESPONSE_MESSAGE_ID[message.channel.id] = message.id
            return

        channel = message.channel
        channel_id = str(channel.id) # Convert to string for consistency with memory_manager keys

        print(f"Received message from {message.author} in {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}: {message.content}")

        # --- Handle Discord-specific commands ---
        # These are currently in on_message. For future refactoring, you might move
        # these into a separate command handler module or a more generic 'command_processor'.
        if message.content.startswith('!join'):
            if message.author.voice and message.author.voice.channel:
                voice_channel = message.author.voice.channel
                try:
                    await voice_channel.connect()
                    await self.send_message(channel.id, f"I joined {voice_channel.name}!")
                except discord.ClientException:
                    await self.send_message(channel.id, "I'm already in a voice channel or a connection error occurred.")
                except discord.InvalidArgument:
                    await self.send_message(channel.id, "I couldn't find that voice channel.")
                except Exception as e:
                    await self.send_message(channel.id, f"An error occurred while joining voice channel: {e}")
            else:
                await self.send_message(channel.id, "You need to be in a voice channel first!")
            return

        if message.content.startswith('!leave'):
            voice_client = message.guild.voice_client if message.guild else None
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
                await self.send_message(channel.id, "I left the voice channel.")
            else:
                await self.send_message(channel.id, "I'm not currently connected to a voice channel here!")
            return

        if message.content.startswith('!clear'):
            # Note: This currently clears memory_manager's stored history.
            # If memory is only within chatbot.py, this command might need to call chatbot.py's method.
            # For now, it interacts with memory_manager directly as per your previous code.
            memory = memory_manager.load_memory()
            if channel_id in memory.get("channel_memory", {}):
                memory_manager.update_channel_memory(memory, channel_id, []) # Clear by setting to empty list
                memory_manager.save_memory(memory)
                await self.send_message(channel.id, "Chat history cleared for this channel!")
            else:
                await self.send_message(channel.id, "No chat history to clear in this channel.")
            return

        if message.content.startswith('!settings'):
            await self.send_message(channel.id, "I don't have settings yet! Check back later (or yell at Lily)!")
            return
        # --- End of Discord-specific commands ---

        # Process only if bot is mentioned or in a DM
        if self.user.mentioned_in(message) or isinstance(channel, discord.DMChannel):
            # If in a DM, remove bot mention is not needed. If mentioned, remove mention.
            query = message.content.strip()
            if self.user.mentioned_in(message):
                query = re.sub(r'<@!?' + str(self.user.id) + '>', '', query).strip()

            if not query: # If only mention or empty message after mention removal
                await self.send_message(channel.id, "Yes?")
                return

            print(f"Discord Interface: Processing query '{query}' from {message.author} in {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}")

            # --- History Collection from Discord and Memory Manager ---
            history = []
            # Fetch recent messages from Discord channel (up to 10 for quick context)
            # Ensure we don't fetch before the bot's last response
            try:
                after_message_id = LAST_RESPONSE_MESSAGE_ID.get(channel_id)
                async for msg in channel.history(limit=10,
                                                after=discord.Object(id=after_message_id) if after_message_id else None):
                    # Only include user and bot messages, not commands or system messages
                    if msg.author == self.user:
                        history.append({"role": "assistant", "content": msg.content})
                    elif msg.author != self.user:
                        history.append({"role": "user", "content": msg.content})
                    # Break if we hit a message older than our last processed one, though 'after' should handle this
                    if after_message_id and msg.id == after_message_id:
                        break
                history.reverse() # History should be chronological

            except Exception as e:
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

            # --- Send Response and Update Memory ---
            await self.send_message(channel.id, response)
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