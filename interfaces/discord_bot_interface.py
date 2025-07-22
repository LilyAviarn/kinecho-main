import discord
import os
import re
from dotenv import load_dotenv
from typing import Any, Callable, List, Dict
from interfaces.base_interface import KinechoInterface
import memory_manager
import chatbot # Keep this import
import traceback

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

LAST_RESPONSE_MESSAGE_ID = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.guild_messages = True
intents.dm_messages = True # Ensure DM messages are enabled

class DiscordInterface(KinechoInterface, discord.Client):
    def __init__(self, *,
                 chatbot_processor_func: Callable[[str, str, str, str, str, Dict[str, Any]], str],
                 intents: discord.Intents,
                 interface_instances: Dict[str, Any],
                 kinecho_memory: Dict[str, Any]):
        super().__init__(chatbot_processor_func=chatbot_processor_func, kinecho_memory=kinecho_memory)
        discord.Client.__init__(self, intents=intents)
        self.interface_instances = interface_instances
        print("Discord Interface: Initialized.")

    async def initialize_interface(self, bot_token: str):
        """
        Connects the Discord bot client to Discord using the provided token.
        This is the main entry point to start the Discord bot's event loop.
        """
        print("Discord Interface: Connecting to Discord...")
        try:
            await self.start(bot_token)
        except Exception as e:
            print(f"ERROR: Failed to connect to Discord: {e}")
            traceback.print_exc()
            self.is_running = False

    async def get_channel_id_by_name(self, channel_name: str, guild_id: str = None) -> Dict[str, str]:
        """
        Retrieves the ID of a Discord channel by its name.
        Can optionally filter by guild ID for more precise searches.
        Args:
            channel_name: The name of the channel (e.g., "general", "bot-commands").
            guild_id: Optional. The ID of the guild (server) to search within. If None, searches all shared guilds.
        Returns:
            A dictionary containing the channel ID, channel name, and guild name if found;
            otherwise, an error message.
        """
        await self.wait_until_ready()

        for guild in self.guilds:
            if guild_id and str(guild.id) != guild_id:
                continue

            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)) and channel.name.lower() == channel_name.lower():
                    return {
                        "channel_id": str(channel.id),
                        "channel_name": channel.name,
                        "guild_name": guild.name
                    }

        return {"error": f"Channel '{channel_name}' not found in any shared Discord server."}

    async def send_message(self, channel_id: str, message_content: str):
        """
        Sends a message to a specific Discord channel.
        """
        try:
            channel = self.get_channel(int(channel_id))
            if channel:
                response_message = await channel.send(message_content)
                LAST_RESPONSE_MESSAGE_ID[channel_id] = response_message.id
                print(f"Discord Interface: Sent message to {channel.name}.")
            else:
                print(f"ERROR: Discord channel with ID {channel_id} not found.")
        except Exception as e:
            print(f"ERROR sending Discord message: {e}")
            traceback.print_exc()

    async def receive_message(self, message: Any):
        if message.author == self.user:
            return # Ignore messages from the bot itself

        user_id = str(message.author.id)
        user_name = message.author.display_name
        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id) if message.guild else None
        query = message.content
        
        # --- Handle bot mentions ---
        # Get the bot's user object to check for mentions
        bot_user = self.user
        bot_mention = f"<@{bot_user.id}>"
        
        # Determine if the message is a direct mention or a DM
        is_direct_mention = self.user.mentioned_in(message)
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_direct_mention:
            clean_query = re.sub(r'<@!?%s>' % self.user.id, '', query).strip()
            # If after stripping the mention, the query is empty, ignore it (e.g., just a mention)
            if not clean_query:
                await self.send_message(channel_id, f"Hey there, <@{user_id}>! What's up?")
                return
            query = clean_query
        
        print(f"DEBUG: Message from {user_name} ({user_id}) in channel {message.channel.name} (Guild: {message.guild.name if message.guild else 'DM'}): {query}")

        try:
            memory = self.kinecho_memory # Use the instance's memory object

            # Ensure user exists in memory
            await memory_manager.create_or_get_user(memory, user_id, user_name, "discord" if guild_id else "dm", discord_id=user_id)

            # Add user's message as an event
            await memory_manager.add_user_event(memory, user_id, "message_in", channel_id, query, "discord" if guild_id else "dm")
            await memory_manager.update_channel_memory(memory, channel_id, [{"role": "user", "content": query}])

            response_for_discord = await self.chatbot_processor(
                query,
                user_id,
                user_name,
                channel_id,
                guild_id,
                self.interface_instances,
                self.kinecho_memory
            )

            if response_for_discord:
                final_response_content = response_for_discord

                # Prepend mention if it was a direct mention or a DM
                if is_direct_mention or is_dm:
                    final_response_content = f"<@{user_id}> {final_response_content}"
                
                await self.send_message(channel_id, final_response_content)

                await memory_manager.add_user_event(memory, user_id, "message_out", channel_id, final_response_content, "discord")
                await memory_manager.update_channel_memory(memory, channel_id, [{"role": "assistant", "content": final_response_content}])

        except Exception as e:
            print(f"ERROR processing message: {e}")
            traceback.print_exc()
            await self.send_message(channel_id, "Oops! I encountered an error trying to process that. My apologies!")

    async def on_ready(self):
        print(f"Discord Interface: Logged in as {self.user} (ID: {self.user.id})")
        print("Discord Interface: Ready to receive commands.")
        self.is_running = True

    async def on_message(self, message: discord.Message):
        await self.receive_message(message)

    def stop(self):
        """
        Stops the Discord bot client.
        """
        self.is_running = False
        if self.loop and not self.loop.is_closed():
            self.loop.create_task(self.close())
        print(f"Discord Interface: {self.__class__.__name__} closed successfully.")
