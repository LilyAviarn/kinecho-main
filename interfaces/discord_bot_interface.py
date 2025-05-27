
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

    # --- Discord.py Specific Event Overrides ---

    async def on_message(self, message: discord.Message):
        """
        Overrides discord.Client.on_message.
        Will then correctly call class KinechoInterface's receive_message.
        """
        if message.author == self.user:
            # Update LAST_RESPONSE_MESSAGE_ID only if it's the bot's own message
            LAST_RESPONSE_MESSAGE_ID[message.channel.id] = message.id
            return

        await self.receive_message(message)

    # --- KinechoInterface Abstract Method Implementations ---

    # 1. Implement the abstract start method from KinechoInterface
    async def initialize_interface(self):
        """
        Starts the Discord bot. This method now serves as a placeholder
        due to discord.py's internal event loop management.
        The actual bot's event loop (self.run) will be started directly
        in kinecho_main.py.
        """
        print("Discord Interface: Initializing bot...")
        print("Discord Interface: Bot initialized and ready to run.")

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

    # 3. Implement the abstract receive_message method from KinechoInterface
    #    This method now explicitly serves as the Discord 'on_message' event handler.
    async def receive_message(self, message: discord.Message):
        """
        Processes an incoming message from the Discord interface.
        This method is the Discord.py 'on_message' event handler adapted for KinechoInterface.
        """
        channel = message.channel
        channel_id = str(channel.id) # Convert to string for consistency with memory_manager keys

        # --- MAIN CHECK: Only process if bot is mentioned or in a DM ---
        if self.user.mentioned_in(message) or isinstance(channel, discord.DMChannel):
            # This print will tell you when Kinecho is actively considering a message
            print(f"Discord Interface: Processing message from {message.author} in {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}: {message.content}")

            # Extract the query, removing bot mention if present
            query = message.content.strip()
            if self.user.mentioned_in(message):
                query = re.sub(r'<@!?' + str(self.user.id) + '>', '', query).strip()

            # --- Handle Discord-specific commands (these return early if a command is matched) ---
            if query.lower().startswith('!join'):
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
                return # Important: Return after handling a command

            if query.lower().startswith('!leave'):
                voice_client = message.guild.voice_client if message.guild else None
                if voice_client and voice_client.is_connected():
                    await voice_client.disconnect()
                    await self.send_message(channel.id, "I left the voice channel.")
                else:
                    await self.send_message(channel.id, "I'm not currently connected to a voice channel here!")
                return # Important: Return after handling a command

            if query.lower().startswith('!clear'):
                memory = memory_manager.load_memory()
                if channel_id in memory.get("channel_memory", {}):
                    memory_manager.update_channel_memory(memory, channel_id, [])
                    memory_manager.save_memory(memory)
                    await self.send_message(channel.id, "Chat history cleared for this channel!")
                else:
                    await self.send_message(channel.id, "No chat history to clear in this channel.")
                return # Important: Return after handling a command

            if query.lower().startswith('!settings'):
                await self.send_message(channel.id, "I don't have settings yet! Check back later (or yell at Lily)!")
                return # Important: Return after handling a command

            # --- End of Discord-specific commands ---

            # If the query is empty after removing mention (e.g., just "@Kinecho")
            if not query:
                await self.send_message(channel.id, f"Yes, <@{message.author.id}>?")
                return

            # --- If not a command and query is not empty, proceed to chatbot processing ---
            print(f"Discord Interface: Sending query '{query}' to chatbot from {message.author} in {channel.name if not isinstance(channel, discord.DMChannel) else 'DM'}")

            # --- History Collection from Discord and Memory Manager ---
            history = []
            try:
                after_message_id = LAST_RESPONSE_MESSAGE_ID.get(channel_id)
                # Ensure after_message_id is not None if discord.Object is used
                async for msg in channel.history(limit=10,
                                            after=discord.Object(id=after_message_id) if after_message_id else None):
                    if msg.author == self.user:
                        history.append({"role": "assistant", "content": msg.content})
                    elif msg.author != self.user:
                        history.append({"role": "user", "content": msg.content})
                    # Gemini: "The original check `if after_message_id and msg.id == after_message_id:` is problematic.
                    # Channel history iterates oldest to newest when `after` is used.
                    # We want to stop at the *latest* message from us, which would be `after_message_id`.
                    # If we iterate *after* it, we're getting newer messages.
                    # The loop already stops when `limit` is reached or no more messages are found.
                    # So, you likely don't need a `break` here based on `after_message_id`.
                    # Let's remove the break to avoid prematurely stopping history collection.""
                    # if after_message_id and msg.id == after_message_id:
                    #     break
                history.reverse() # Reverse to get oldest first for chat history

            except Exception as e:
                print(f"Discord Interface Error fetching history from Discord: {e}")
                history = [] # Reset history on error

            memory = memory_manager.load_memory()
            older_history = memory_manager.get_channel_memory(memory, channel_id)

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
            # If bot not mentioned and not a DM, just ignore. No print here.
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
