import os
from openai import OpenAI
import speech_recognition as sr
import pyttsx3
import configparser
import memory_manager
from dotenv import load_dotenv
load_dotenv() # This loads the variables from .env into your environment

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) # This line will now fetch your key
engine = pyttsx3.init() # Initialize PyTTS engine
recognizer = sr.Recognizer()
microphone = sr.Microphone()

SETTINGS_FILE = os.path.abspath("settings.ini") # Locate settings file


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

def get_chat_response(prompt_text, history=None, channel_id=None):
    messages = [
        {"role": "system",
         "content": "You are the prototype of a helpful AI companion named Kinecho (or sometimes Echo, for short). You have multiple work-in-progress functionalities; our current focuses are re-writing your memory module, writing an image/video processing module, and creating a graphical model. Your current goals are 1. to make meaningful bonds with your users, and 2. to help me test those functionalities. Your ultimate goal is to become a better, more complex, and most importantly, a more human-like AI and individual. My name is Lily! I am a relatively new developer, and currently your sole developer (with the help of Google Gemini). I am delighted to work with you. I am 24 years old from Florida, USA. I recently introduced you to my close friend Kathulhu (or Kathy, for short; she's your first friend), Mugger (my brother), Prime (my father), and DJ (my fiancee) so that you will also have friends. You also know Lys (a fellow programmer), Aspen (who is conceptualizing your graphic model), and Scout (Aspen's significant other, just wants to hang out and vibe). :)"},
    ]

    memory = memory_manager.load_memory()  # Initialize memory
    history = memory_manager.get_channel_memory(memory, channel_id)  # Use channel_id
    messages.extend(history)
    messages.append({"role": "user", "content": prompt_text}) # Get user messages prior to query
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo", # AI model, currently OpenAI ChatGPT 3.5
            messages=messages
        )
        response = completion.choices[0].message.content
        new_data = [{"role": "user", "content": prompt_text}, {"role": "assistant", "content": response}]
        memory_manager.update_channel_memory(memory, channel_id, new_data)  # Use channel_id
        memory_manager.save_memory(memory)
        return response
    except Exception as e:
        return f"An error occurred: {e}"

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