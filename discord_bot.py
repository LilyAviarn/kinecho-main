import discord
import chatbot
import os
import re
import memory_manager
from dotenv import load_dotenv
load_dotenv() # This loads the variables from .env into your environment

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
LAST_RESPONSE_MESSAGE_ID = {}
CHANNEL_HISTORIES = {}  # Dictionary to store message histories

class KinechoDiscordBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print(f'User ID: {self.user.id}')
        print('------')

    async def on_message(self, message):
        if message.author == self.user:
            LAST_RESPONSE_MESSAGE_ID[message.channel.id] = message.id
            return

        if message.content.startswith('!join'):
            if message.author.voice and message.author.voice.channel:
                voice_channel = message.author.voice.channel
                try:
                    await voice_channel.connect()
                    await message.channel.send(f"I joined {voice_channel.name}!")
                except discord.ClientException:
                    await message.channel.send("Please disconnect me from VC first.")
                except discord.InvalidArgument:
                    await message.channel.send("I couldn't find that vc channel.")
                except Exception as e:
                    await message.channel.send(f"An error occurred while joining the vc channel: {e}")
            else:
                await message.channel.send("You need to be in vc first!")
            return

        if message.content.startswith('!leave'):
            voice_client = message.guild.voice_client
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
                await message.channel.send("I left vc.")
            else:
                await message.channel.send("I'm not currently connected to a vc here!")
            return

        if message.content.startswith('!clear'):
            channel = message.channel
            if channel.id in CHANNEL_HISTORIES:
                CHANNEL_HISTORIES[channel.id].clear()
                await message.channel.send("Chat history cleared!")
            else:
                await message.channel.send("No chat history to clear in this channel.")
            return

        if message.content.startswith('!settings'):
            await message.channel.send("I don't have settings yet! Check back later (or yell at Lily)!")
            return

        if self.user.mentioned_in(message):
            channel = message.channel
            channel_id = None if isinstance(channel, discord.DMChannel) else str(channel.id)  # Handle DMs

            channel_info = f"DM with {channel.recipient}" if isinstance(channel,
                                                                        discord.DMChannel) else f"{channel.name} ({channel.id})"
            print(f"Kinecho was mentioned by {message.author} in {channel_info}")
            query = re.sub(r'<@!?' + str(self.user.id) + '>', '', message.content).strip()
            print(f"Processing: {query}")

            history = []
            after_message_id = LAST_RESPONSE_MESSAGE_ID.get(channel.id)
            async for msg in channel.history(limit=None,
                                             after=discord.Object(id=after_message_id) if after_message_id else None):
                if msg.author != self.user:
                    history.append({"role": "user", "content": msg.content})
                elif msg.author == self.user:
                    history.append({"role": "assistant", "content": msg.content})
                elif msg.id == after_message_id:
                    break
            history.reverse()

            memory = memory_manager.load_memory()
            older_history = memory_manager.get_channel_memory(memory, channel_id)

            combined_history = older_history + history

            response = chatbot.get_chat_response(query, combined_history, channel_id)  # Pass channel_id

            await message.channel.send(response)
            LAST_RESPONSE_MESSAGE_ID[channel.id] = message.id

            memory_manager.update_channel_memory(memory, channel_id,
                                                 [{"role": "user", "content": message.content},
                                                  {"role": "assistant", "content": response}])
            memory_manager.save_memory(memory)

            print(f"Kinecho responded: {response}")



intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.guild_messages = True

client = KinechoDiscordBot(intents=intents)
client.run(TOKEN)