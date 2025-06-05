import os
from openai import OpenAI
import speech_recognition as sr
import pyttsx3
import configparser
import memory_manager
import traceback
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
    # Call your existing get_chat_response function with the user's message
    # For now, we're passing None for history and channel_id,
    # as we'll integrate memory more properly in a later step.
    response = get_chat_response(prompt_text=message, history=None, channel_id="test_channel_from_app_main")
    return response

def load_system_prompt(user_name: str) -> str:
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            # Read the template and format it with the user_name
            # Note: The placeholder {user_name} must exist in system_prompt.txt
            prompt_template = f.read()
            return prompt_template.format(user_name=user_name)
    except FileNotFoundError:
        print(f"ERROR: System prompt file not found at {SYSTEM_PROMPT_FILE}. Using default prompt.")
        return "You are a helpful AI companion named Kinecho." # Fallback default prompt
    except KeyError as e:
        print(f"ERROR: Missing placeholder in system prompt file: {e}. Check system_prompt.txt for {{user_name}}.")
        return "You are a helpful AI companion named Kinecho." # Fallback if formatting fails (e.g., missing {user_name} placeholder)
    except Exception as e: # Catch any other unexpected errors during prompt loading
        print(f"ERROR: Unexpected error loading system prompt: {e}")
        traceback.print_exc()
        return "You are a helpful AI companion named Kinecho."

def get_chat_response(user_id: str, prompt_text: str, channel_id: str, interface_type: str):
    """
    Generates a chat response using OpenAI's API.
    For now, this function will respond without conversational memory.
    """
#    print(f"DEBUG: get_chat_response received: user_id={user_id}, prompt='{prompt_text}', channel_id={channel_id}, interface_type={interface_type}")

    memory = {}

    try:
        memory = memory_manager.load_memory() # Load the overall memory structure
#        print("DEBUG: Memory loaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to load memory: {e}")
        traceback.print_exc()
        print("WARNING: Proceeding with empty memory for this request.")

    # Retrieve the specific user's data and their events
    user_data = memory.get("users", {}).get(user_id, {})
    user_events = user_data.get("events", [])
    user_name = user_data.get("user_name", "User")

    # PERSONA CORE
    system_prompt_content = "You are a helpful AI companion named Kinecho." # Default in case of loading failure
    try:
        system_prompt_content = load_system_prompt(user_name)
#        print("DEBUG: System prompt content prepared.")
    except Exception as e:
        print(f"ERROR: Failed to prepare system prompt content: {e}")
        traceback.print_exc()
        print("WARNING: Proceeding with default system prompt.")

    messages = [
        {"role": "system",
         "content": system_prompt_content
        },
    ]

    # Build the conversation history from user_events for the current channel.
    # We iterate through events, format them, and add them to 'messages'.
    # The last 'message_in' event in memory corresponds to the 'prompt_text'
    # we're currently processing. We *don't* add it to the history list here
    # because 'prompt_text' will be added explicitly as the last message.
    # This prevents duplicating the current user message in the context.

    # Find the index of the current 'message_in' event in the user_events list.
    # This is a robust way to ensure we don't include the current message in the history.
    current_message_event_index = -1
    # Iterate backwards to find the most recent matching user message for this channel
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

    # Finally, add the current user prompt to the messages list
    messages.append({"role": "user", "content": prompt_text})

    print(f"DEBUG: Messages sent to OpenAI API: {messages}")

    try:
        selected_model = "gpt-3.5-turbo" # Will be updated to a more powerful model in the future

        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages
        )
#        print("DEBUG: Successfully received response from OpenAI API.")
        response_content = completion.choices[0].message.content
        return response_content
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
            print("No speech detected.") # In case I become Silent Sally
            return ""
        except sr.RequestError as e:
            print(f"Could not request results; {e}") # In case the API fails
            return ""
        except sr.UnknownValueError:
            print("Could not understand audio") # In case I'm too garbled
            return ""
        except Exception as e:
            print(f"Error during listening: {e}") # For literally everything else
            return ""

def transcribe_audio(audio):
    if audio:
        r = sr.Recognizer()
        try:
            text = r.recognize_google(audio) # Using Google Speech Recognition
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            print(f"Could not understand audio") # Again, in case I'm too garbled
            return None
        except sr.RequestError as e:
            print(f"Could not request results; {e}") # Again, in case the API fails
            return None
        except Exception as e:
            print(f"Error during transcription: {e}") # Again, for literally everything else
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
        print(f"Invalid {method_type} method.") # For if I fatfinger my keyboard or forget what options I set like a moron
        return None

# """
# Commented out the main loop below, moved to kinecho_main.py
# """

# if __name__ == "__main__": # INITIALIZE! RISE MY MINION!!
#     print("Kinecho v0.0.0.2: Welcome, Lily! Hello!")

#     settings = load_settings()
#     input_method = settings['input']['method']
#     output_method = settings['output']['method']
#     print(f"Current input method: {input_method}")
#     print(f"Current output method: {output_method}")

#     audio_data = None  # Initialize audio_data outside the loop

#     while True:
#         if input_method == "text":
#             user_message = input("You: ")
#             if user_message.lower() == 'switch input':
#                 new_input_method = input("Choose new input method (text/voice/settings): ").lower()
#                 if new_input_method in ["text", "voice", "settings"]:
#                     input_method = new_input_method
#                     settings['input']['method'] = input_method
#                 else:
#                     print("Invalid input method.")
#                 continue
#             elif user_message.lower() == 'switch output':
#                 new_output_method = input("Choose new output method (text/tts): ").lower()
#                 if new_output_method in ["text", "tts"]:
#                     output_method = new_output_method
#                     settings['output']['method'] = output_method
#                 else:
#                     print("Invalid output method.")
#                 continue
#             elif user_message.lower() == 'settings':
#                 input_method = 'settings'
#                 continue
#             elif user_message.lower() == 'reload settings':  # Add reload settings here
#                 settings = load_settings()
#                 input_method = settings['input']['method']
#                 output_method = settings['output']['method']
#                 print("Settings reloaded.")
#                 continue
#             response = get_chat_response(user_message)
#             print(f"Kinecho: {response}")
#             if settings['output']['method'] == 'tts':
#                 speak_response(response)
#         elif input_method == "voice":
#             audio_data = listen_for_command()
#             if audio_data:
#                 voice_input = transcribe_audio(audio_data)
#                 if voice_input:
#                     print(f"You (voice): {voice_input}")
#                     if voice_input.lower() == 'switch input':
#                         new_input_method = input("Choose new input method (text/voice/settings): ").lower()
#                         if new_input_method in ["text", "voice", "settings"]:
#                             input_method = new_input_method
#                             settings['input']['method'] = input_method
#                         else:
#                             print("Invalid input method.")
#                         continue
#                     elif voice_input.lower() == 'switch output':
#                         new_output_method = input("Choose new output method (text/tts): ").lower()
#                         if new_output_method in ["text", "tts"]:
#                             output_method = new_output_method
#                             settings['output']['method'] = output_method
#                         else:
#                             print("Invalid output method.")
#                         continue
#                     elif voice_input.lower() == 'settings':
#                         input_method = 'settings'
#                         continue
#                     elif voice_input.lower() == 'reload settings':  # Add reload settings here
#                         settings = load_settings()
#                         input_method = settings['input']['method']
#                         output_method = settings['output']['method']
#                         print("Settings reloaded.")
#                         continue
#                     response = get_chat_response(voice_input)
#                     print(f"Kinecho: {response}")
#                     if settings['output']['method'] == 'tts':
#                         speak_response(response)
#                 else:
#                     print("No voice detected, or was incomprehensible.")
#             else:
#                 print("No input.")
#         elif input_method == "settings":
#             print("--- Settings ---")
#             print(f"Input Method: {settings['input']['method']}")
#             print(f"Output Method: {settings['output']['method']}")
#             setting_to_change = input("Enter setting to change (input_method/output_method/reload_settings/quit): ").lower()
#             if setting_to_change == "input_method":
#                 new_input_method = input("Choose new input method (text/voice): ").lower()
#                 if new_input_method in ["text", "voice"]:
#                     settings["input"]["method"] = new_input_method
#                     input_method = new_input_method # Update input_method immediately
#                 else:
#                     print("Invalid input method.")
#                 continue
#             elif setting_to_change == "output_method":
#                 new_output_method = input("Choose new output method (text/tts): ").lower()
#                 if new_output_method in ["text", "tts"]:
#                     settings["output"]["method"] = new_output_method
#                 else:
#                     print("Invalid output method.")
#                     continue
#             elif setting_to_change == "quit":
#                 save_settings(settings)
#                 input_method = settings['input']['method']  # Ensure input_method is updated
#                 continue
#             elif setting_to_change == "reload_settings":
#                 settings = load_settings()
#                 input_method = settings['input']['method']
#                 output_method = settings['output']['method']
#                 print("Settings reloaded.")
#                 continue
#             else:
#                 print("Invalid setting.")
#             save_settings(settings) # Save settings after any valid change
#         else:
#             print("Invalid: please type 'text', 'voice', 'settings', or 'quit'.")
#             input_method = input("Choose input method (text/voice): ").lower()  # Ask again if invalid