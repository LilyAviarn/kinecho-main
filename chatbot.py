import os
from openai import OpenAI
import speech_recognition as sr
import pyttsx3
import configparser
import memory_manager
import traceback
import datetime
import pytz
import json
import asyncio
from typing import Any, Callable, List, Dict
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
engine = pyttsx3.init()
recognizer = sr.Recognizer()
microphone = sr.Microphone()

SETTINGS_FILE = os.path.abspath("settings.ini")
SYSTEM_PROMPT_FILE = os.path.abspath("system_prompt.txt")

# --- Helper functions ---

def get_current_time(timezone_str: str = 'America/Chicago') -> Dict[str, Any]:
    """
    Retrieves the current date and time in a specified timezone.
    Defaults to America/Chicago if no timezone is provided.
    """
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.datetime.now(tz)
        unix_timestamp = int(now.timestamp())
        return {
            "unix_timestamp": unix_timestamp,
            "display_time_for_model": now.strftime("%I:%M:%S %p %Z%z"),
            "current_date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "timezone": timezone_str
        }
    except pytz.UnknownTimeZoneError:
        return {"error": f"Unknown timezone: {timezone_str}. Please provide a valid IANA timezone name (e.g., 'America/New_York', 'Europe/London')."}
    except Exception as e:
        return {"error": f"Failed to get current time: {e}"}

# --- Audio/Speech Functions (Re-implemented) ---

def listen_for_command(timeout=5) -> str:
    """
    Listens for a voice command from the microphone with a timeout.
    Returns the transcribed text or an empty string if no speech is detected.
    """
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening for command...")
        try:
            audio = recognizer.listen(source, timeout=timeout)
            print("Processing audio...")
            command = recognizer.recognize_google(audio)
            print(f"Heard: {command}")
            return command.lower()
        except sr.WaitTimeoutError:
            print("No speech detected within the timeout period.")
            return ""
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio.")
            return ""
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return ""
        except Exception as e:
            print(f"An unexpected error occurred during listening: {e}")
            return ""

def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribes an audio file into text using OpenAI's Whisper model.
    """
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
            return transcript.text
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return ""

def speak_response(text: str):
    """
    Converts text to speech and plays it.
    """
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"Error speaking response: {e}")

# --- Main chatbot response function ---

async def get_chat_response(
    query: str,
    user_id: str,
    user_name: str,
    channel_id: str,
    guild_id: str,
    interface_instances: Dict[str, Any]
) -> str:
    """
    Processes a user query using the OpenAI API, supporting tool calls.
    """
    system_prompt_content = ""
    try:
        with open(SYSTEM_PROMPT_FILE, "r") as f:
            system_prompt_content = f.read()
            system_prompt_content = system_prompt_content.replace("{user_name}", user_name)
            system_prompt_content = system_prompt_content.replace("{user_id}", user_id)
    except FileNotFoundError:
        print(f"ERROR: System prompt file not found at {SYSTEM_PROMPT_FILE}. Using default prompt.")
        system_prompt_content = "You are a helpful AI assistant."

    memory = memory_manager.load_memory()
    memory_manager.create_or_get_user(memory, user_id, user_name, "discord" if guild_id else "console", discord_id=user_id if guild_id else None)

    current_channel_history = memory_manager.get_channel_memory(memory, channel_id)[-10:]

    messages = [
        {"role": "system", "content": system_prompt_content}
    ]

    for msg in current_channel_history:
        if msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    from kinecho_main import AVAILABLE_TOOLS_DEFINITIONS

    response_message = None
    tool_calls = []
    max_tool_iterations = 5

    for _ in range(max_tool_iterations):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=AVAILABLE_TOOLS_DEFINITIONS,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

        except Exception as e:
            error_message = f"Failed to get response from OpenAI: {e}\n{traceback.format_exc()}"
            print(f"ERROR: {error_message}")
            return f"I'm sorry, I encountered an error and couldn't process that: {e}"

        if not tool_calls:
            break

        messages.append(response_message)

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            tool_output = {"role": "tool", "tool_call_id": tool_call.id, "content": ""}

            print(f"DEBUG: Tool called: {function_name} with args: {function_args}")

            if function_name == "get_current_time":
                timezone_arg = function_args.get("timezone_str")
                if timezone_arg:
                    tool_result = get_current_time(timezone_arg)
                else:
                    tool_result = get_current_time()

                if "error" in tool_result:
                    tool_output["content"] = tool_result
                else:
                    unix_ts = tool_result["unix_timestamp"]
                    discord_timestamp_markdown = f"<t:{unix_ts}:F>"
                    tool_output["content"] = {
                        "response_for_user": f"The time for {tool_result['timezone']} is: {discord_timestamp_markdown}",
                        "raw_time_data": tool_result
                    }

            elif function_name == "get_discord_user_status":
                user_id_arg = function_args.get("user_id")
                if user_id_arg:
                    discord_interface = interface_instances.get("discord_interface")
                    if discord_interface:
                        tool_result = await discord_interface.get_discord_user_status(user_id_arg)
                    else:
                        tool_result = {"error": "Discord interface not available to get user status. Make sure the Discord bot is running."}
                else:
                    tool_result = {"error": "User ID is required to get Discord user status."}
                tool_output["content"] = tool_result

            elif function_name == "get_conversation_history_for_channel":
                channel_id_arg = function_args.get("channel_id")
                limit_arg = function_args.get("limit", 10)
                if channel_id_arg:
                    tool_result = memory_manager.get_conversation_history_for_channel(channel_id_arg, limit_arg)
                else:
                    tool_result = {"error": "Channel ID is required to get conversation history."}
                tool_output["content"] = tool_result

            elif function_name == "add_user_derived_fact":
                user_id_arg = function_args.get("user_id")
                fact_content_arg = function_args.get("fact_content")
                channel_id_arg = function_args.get("channel_id")
                if user_id_arg and fact_content_arg:
                    memory_manager.add_derived_fact_to_user(user_id_arg, fact_content_arg, channel_id_arg)
                    tool_result = {"status": "success", "message": "Derived fact added."}
                else:
                    tool_result = {"error": "User ID and fact content are required to add a derived fact."}
                tool_output["content"] = tool_result

            elif function_name == "get_user_derived_facts":
                user_id_arg = function_args.get("user_id")
                limit_arg = function_args.get("limit", 10)
                if user_id_arg:
                    tool_result = memory_manager.get_derived_facts_for_user(user_id_arg, limit_arg)
                else:
                    tool_result = {"error": "User ID is required to retrieve derived facts."}
                tool_output["content"] = tool_result

            elif function_name == "get_discord_channel_id_by_name":
                channel_name_arg = function_args.get("channel_name")
                guild_id_arg = function_args.get("guild_id", guild_id)

                if channel_name_arg:
                    discord_interface = interface_instances.get("discord_interface")
                    if discord_interface:
                        tool_result = await discord_interface.get_channel_id_by_name(channel_name_arg, guild_id_arg)
                    else:
                        tool_result = {"error": "Discord interface not available to resolve channel name. Make sure the Discord bot is running."}
                else:
                    tool_result = {"error": "Channel name is required to get channel ID."}
                tool_output["content"] = tool_result

            else:
                tool_output["content"] = {"error": f"Unknown tool: {function_name}"}

            messages.append(tool_output)

    if response_message and response_message.content:
        memory_manager.update_channel_memory(
            memory, channel_id, [{"role": "assistant", "content": response_message.content}]
        )
        memory_manager.save_memory(memory)
        return response_message.content
    elif tool_calls:
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=AVAILABLE_TOOLS_DEFINITIONS,
                tool_choice="auto"
            )
            final_response_message = response.choices[0].message
            if final_response_message.content:
                memory_manager.update_channel_memory(
                    memory, channel_id, [{"role": "assistant", "content": final_response_message.content}]
                )
                memory_manager.save_memory(memory)
                return final_response_message.content
        except Exception as e:
            print(f"ERROR: Failed to get final response after tool calls: {e}")
            return "I finished my task, but I couldn't formulate a final response."
    else:
        print("DEBUG: No direct response message content, returning generic fallback.")
        return "I'm not sure how to respond to that."

# --- Configuration functions ---

def load_settings():
    config = configparser.ConfigParser()
    if os.path.exists(SETTINGS_FILE):
        config.read(SETTINGS_FILE)
    else:
        config['input'] = {'method': 'text'}
        config['output'] = {'method': 'text'}

    settings = {
        'input': {'method': config.get('input', 'method', fallback='text')},
        'output': {'method': config.get('output', 'method', fallback='text')},
    }
    return settings

def save_settings(settings):
    config = configparser.ConfigParser()
    config['input'] = {'method': settings['input']['method']}
    config['output'] = {'method': settings['output']['method']}
    with open(SETTINGS_FILE, 'w') as configfile:
        config.write(configfile)

def switch_method(method_type, valid_options, settings):
    """
    Prompts the user to choose a new input or output method.
    """
    new_method = input(f"Choose new {method_type} method ({'/'.join(valid_options)}): ").lower()
    if new_method in valid_options:
        settings[method_type]['method'] = new_method
        save_settings(settings)
        print(f"{method_type.capitalize()} method switched to {new_method}.")
        return new_method
    else:
        print("Invalid option.")
        return None