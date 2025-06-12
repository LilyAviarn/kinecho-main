import os
from openai import OpenAI
import speech_recognition as sr
import pyttsx3
import configparser
import memory_manager
import traceback
import datetime
import pytz
import json # Added for parsing tool call arguments
import asyncio # Added for awaiting tool calls
from typing import Any, Callable, List, Dict # Added Dict for tool definitions
from dotenv import load_dotenv
load_dotenv() # This loads the variables from .env into your environment

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) # This line will now fetch your key
engine = pyttsx3.init() # Initialize PyTTS engine
recognizer = sr.Recognizer()
microphone = sr.Microphone()

SETTINGS_FILE = os.path.abspath("settings.ini") # Locate settings file
SYSTEM_PROMPT_FILE = os.path.abspath("system_prompt.txt")

def process_chatbot_message(message: str) -> str:
    """
    Processes a message using the chatbot's logic and returns a response.
    (This will eventually contain your main chatbot processing code)
    """
    # This function is meant for simple cases; the main tool-enabled flow
    # is now handled directly by kinecho_main.py calling get_chat_response
    # with appropriate arguments. For process_chatbot_message, we don't have
    # the interface_instances readily available, so it cannot support tools directly.
    print("WARNING: process_chatbot_message called without interface_instances. Tool calls will not be supported.")
    response = get_chat_response(prompt_text=message, history=None, channel_id="test_channel_from_app_main")
    return response

def get_current_time(timezone_str: str = 'America/New_York') -> Dict[str, str]:
    """
    Retrieves the current date and time in a specified timezone.
    Defaults to Eastern Time (America/New_York) if no timezone is provided.
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

def load_system_prompt(user_name: str, user_id: str) -> str:
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            # Read the template and format it with the user_name
            # Note: The placeholder {user_name} must exist in system_prompt.txt
            prompt_template = f.read()
            return prompt_template.format(user_name=user_name, user_id=user_id)
    except FileNotFoundError:
        print(f"ERROR: System prompt file not found at {SYSTEM_PROMPT_FILE}. Using default prompt.")
        return "You are a helpful AI companion named Kinecho." # Fallback default prompt
    except KeyError as e:
        print(f"ERROR: Missing placeholder in system prompt file: {e}. Check system_prompt.txt for {{user_name}} or {{user_id}}.")
        return "You are a helpful AI companion named Kinecho." # Fallback if formatting fails (e.g., missing {user_name} placeholder)
    except Exception as e: # Catch any other unexpected errors during prompt loading
        print(f"ERROR: Unexpected error loading system prompt: {e}")
        traceback.print_exc()
        return "You are a helpful AI companion named Kinecho."

async def get_chat_response(user_id: str, prompt_text: str, channel_id: str, interface_type: str, available_tools: List[Dict[str, Any]] = None, interface_instances: Dict[str, Any] = None):
    """
    Generates a chat response using OpenAI's API.
    Now supports tool calling.
    """
    if available_tools is None:
        available_tools = [] # Ensure available_tools is always a list
    if interface_instances is None:
        interface_instances = {} # Ensure interface_instances is always a dictionary

    memory = {}

    try:
        memory = memory_manager.load_memory() # Load the overall memory structure
    except Exception as e:
        print(f"ERROR: Failed to load memory: {e}")
        traceback.print_exc()
        print("WARNING: Proceeding with empty memory for this request.")

    # Retrieve the specific user's data and their events
    user_data = memory.get("users", {}).get(user_id, {})
    user_events = user_data.get("events", [])
    user_name = user_data.get("profile", {}).get("name", "User")
    print (f"DEBUG: Retrieved user_name from memory: '{user_name}' for user_id: '{user_id}")

    # PERSONA CORE
    system_prompt_content = "You are a helpful AI companion named Kinecho." # Default in case of loading failure
    try:
        system_prompt_content = load_system_prompt(user_name, user_id)
    except Exception as e:
        print(f"ERROR: Failed to prepare system prompt content: {e}")
        traceback.print_exc()
        print("WARNING: Proceeding with default system prompt.")

    messages = [
        {"role": "system",
         "content": system_prompt_content
        },
    ]

    # Find the index of the current 'message_in' event in the user_events list.
    current_message_event_index = -1
    for i in range(len(user_events) - 1, -1, -1):
        event = user_events[i]
        if (event["channel_id"] == channel_id and
            event["type"] == "message_in" and
            event["content"] == prompt_text):
            current_message_event_index = i
            break

    for i, event in enumerate(user_events):
        # Skip the current incoming message if found, as it will be appended separately
        if i == current_message_event_index:
            continue

        # Only add messages from the current channel
        if event["channel_id"] == channel_id:
            if event["type"] == "message_in":
                messages.append({"role": "user", "content": event["content"]})
            elif event["type"] == "message_out":
                messages.append({"role": "assistant", "content": event["content"]})
            # Add tool_calls and tool messages if they exist in the history
            elif event["type"] == "tool_call_request":
                # Reconstruct tool_calls from the stored content
                tool_calls_list = json.loads(event["content"])
                messages.append({"role": "assistant", "tool_calls": tool_calls_list})
            elif event["type"] == "tool_output":
                # Reconstruct tool_output from the stored content
                tool_output = json.loads(event["content"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_output["tool_call_id"],
                    "content": json.dumps(tool_output["content"]) # Tool content must be a string
                })


    # Finally, add the current user prompt to the messages list
    messages.append({"role": "user", "content": prompt_text})

    print(f"DEBUG: Messages sent to OpenAI API: {messages}")
    print(f"DEBUG: Available tools to OpenAI API: {available_tools}")

    try:
        selected_model = "gpt-3.5-turbo"

        # First API call: Potentially get a tool call from the model
        response = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            tools=available_tools, # Pass the defined tools to the model
            tool_choice="auto" # Allow the model to decide whether to call a tool
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # --- Tool Calling Logic ---
        if tool_calls:
            print("DEBUG: Model requested a tool call.")
            # Add the tool_call request to memory for the current user and channel
            # Store the tool_calls as a JSON string
            tool_calls_content = json.dumps([tc.model_dump() for tc in tool_calls])
            memory_manager.add_user_event(memory, user_id, "tool_call_request", channel_id, tool_calls_content, interface_type)
            memory_manager.save_memory(memory)

            # Extend conversation with assistant's reply (tool call request)
            messages.append(response_message)

            # Iterate over tool calls and execute them
            # Iterate over tool calls and execute them
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_output = {} # Initialize tool_output for this specific tool call

                print(f"DEBUG: Attempting to call tool: {function_name} with args: {function_args}")

                # Check if the tool is get_discord_user_status
                if function_name == "get_discord_user_status":
                    # Ensure the discord interface is available
                    discord_int = interface_instances.get("discord")
                    if discord_int:
                        # Get the user_id the model *suggested* in its tool arguments
                        model_suggested_user_id = function_args.get("user_id")

                        # IMPORTANT: Define the bot's own Discord ID.
                        # This should ideally come from an environment variable or bot object,
                        # but for this specific fix, using the ID mentioned in your system prompt.
                        BOT_DISCORD_ID = "1372412067923103855" #

                        # Determine the actual user_id to use for the tool lookup.
                        # If the model suggested its own ID, or didn't suggest any ID,
                        # use the actual conversational user_id (`user_id` parameter of get_chat_response).
                        # Otherwise, use the ID the model explicitly provided (for looking up other users).
                        if model_suggested_user_id == BOT_DISCORD_ID or not model_suggested_user_id:
                            actual_lookup_id = user_id # Use the user_id from the current conversation
                            print(f"DEBUG: Model attempted to use bot's ID or no ID. Overriding with current user_id: {actual_lookup_id}")
                        else:
                            actual_lookup_id = model_suggested_user_id # Use the ID the model provided (for other users)
                            print(f"DEBUG: Model provided specific user_id for tool call: {actual_lookup_id}")

                        # Call the tool function with the determined user ID
                        tool_output["content"] = discord_int.get_discord_user_status(user_id=actual_lookup_id)
                        tool_output["tool_call_id"] = tool_call.id # Store the tool_call.id
                        print(f"DEBUG: get_discord_user_status tool output: {tool_output['content']}")
                    else:
                        tool_output["content"] = {"error": "Discord interface not active or available."}
                        tool_output["tool_call_id"] = tool_call.id
                        print("ERROR: Discord interface not available for get_discord_user_status call.")
                
                elif function_name == "get_current_time":
                    timezone_arg = function_args.get("timezone_str")
                    if timezone_arg:
                        tool_result = get_current_time(timezone_arg)
                    else:
                        tool_result = get_current_time() # Call with default timezone

                    if "error" in tool_result:
                        tool_output["content"] = tool_result # Pass the error
                    else:
                        unix_ts = tool_result["unix_timestamp"]
                        # Use Discord markdown timestamp for the response to the user.
                        # ':F' displays full date and time. Other options: :t, :T, :d, :D, :f, :R
                        discord_timestamp_markdown = f"<t:{unix_ts}:F>"

                        # Provide both a user-facing string and the raw data to the model
                        tool_output["content"] = {
                            "response_for_user": f"The time requested is: {discord_timestamp_markdown}",
                            "raw_time_data": tool_result # Provide raw data for the model's context if it needs to reason about the time itself
                        }
                    tool_output["tool_call_id"] = tool_call.id
                    print(f"DEBUG: get_current_time tool output: {tool_output['content']}")
                
                elif function_name == "get_conversation_history_for_channel":
                    channel_id_arg = function_args.get("channel_id")
                    limit_arg = function_args.get("limit", 10) # Default to 10 if not provided by model

                    if channel_id_arg:
                        # Call the function from memory_manager.
                        tool_output["content"] = memory_manager.get_conversation_history_for_channel(channel_id_arg, limit_arg)
                    else:
                        tool_output["content"] = {"error": "Channel ID is required to get conversation history."}
                    tool_output["tool_call_id"] = tool_call.id
                    print(f"DEBUG: get_conversation_history_for_channel tool output: {tool_output['content']}")

                # Add the tool output to memory
                memory_manager.add_user_event(memory, user_id, "tool_output", channel_id, json.dumps(tool_output), interface_type)
                memory_manager.save_memory(memory)

                # Add tool response to messages for the next API call
                messages.append(
                    {
                        "tool_call_id": tool_output["tool_call_id"],
                        "role": "tool",
                        "content": json.dumps(tool_output["content"]) # Tool content must be a string
                    }
                )

            # Second API call: Get the model's response after tool execution
            print("DEBUG: Making second API call with tool output...")
            second_response = client.chat.completions.create(
                model=selected_model,
                messages=messages
            )
            final_response_content = second_response.choices[0].message.content
            return final_response_content

        else:
            # If no tool call, return the direct response content
            return response_message.content

    except Exception as e:
        print(f"Error getting chat response from OpenAI: {e}")
        traceback.print_exc()
        return f"I'm sorry, I'm having trouble connecting to my brain ('{selected_model}') right now. Please try again later."

def listen_for_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Kinecho is listening...")
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=10)
            print("Audio captured.")
            return audio
        except sr.WaitTimeoutError:
            print("No speech detected.")
            return ""
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            return ""
        except sr.UnknownValueError:
            print("Could not understand audio")
            return ""
        except Exception as e:
            print(f"Error during listening: {e}")
            return ""

def transcribe_audio(audio):
    if audio:
        r = sr.Recognizer()
        try:
            text = r.recognize_google(audio)
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            print(f"Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            return None
        except Exception as e:
            print(f"Error during transcription: {e}")
            return None
    return None

def speak_response(response_text):
    if response_text:
        engine.say(response_text)
        engine.runAndWait()

def load_settings():
    config = configparser.ConfigParser()
    if os.path.exists(SETTINGS_FILE):
        config.read(SETTINGS_FILE)
    else:
        # Create default sections if the file doesn't exist
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

    Args:
        method_type (str): "input" or "output".
        valid_options (list): List of valid method options.
        settings (dict): The settings dictionary.

    Returns:
        str: The new method chosen by the user, or None if invalid.
    """
    new_method = input(f"Choose new {method_type} method ({'/'.join(valid_options)}): ").lower()
    if new_method in valid_options:
        settings[method_type]['method'] = new_method
        return new_method
    else:
        print(f"Invalid {method_type} method.")
        return None