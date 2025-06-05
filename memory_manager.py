import json
import datetime

USER_MEMORY_FILE = "kinecho_user_memory.json"
DM_KEY = "dm"  # Define a key to use for DMs

def load_memory():
    try:
        with open(USER_MEMORY_FILE, "r") as f: # Use the new file name
            memory = json.load(f)
    except FileNotFoundError:
        memory = {} # Start with an empty dictionary if file doesn't exist
    except json.JSONDecodeError: # Handle empty or malformed JSON
        print(f"Warning: {USER_MEMORY_FILE} is empty or corrupted. Starting with fresh memory.")
        memory = {}

    # Ensure the top-level "users" key exists
    if "users" not in memory:
        memory["users"] = {}
    # You might also want to ensure global_system_memory exists here or load it separately
    # For now, let's keep it simple with just users in this file. 
    # I *do* intend to add it to this file, to be clear.
    return memory

def create_or_get_user(memory: dict, user_id: str, user_name: str, interface_type: str, discord_id: str = None) -> dict:
    """
    Ensures a user's profile exists in the memory and returns their profile.
    If the user doesn't exist, a new profile is created.
    """
    if "users" not in memory:
        memory["users"] = {}

    if user_id not in memory["users"]:
        user_profile = {
            "profile": {
                "name": user_name,
                "interface_type": interface_type,
                "created_at": datetime.datetime.now().isoformat()
            },
            "events": [],
            "derived_facts": []
        }
        if discord_id:
            user_profile["profile"]["discord_id"] = discord_id
        memory["users"][user_id] = user_profile
    return memory["users"][user_id]

def add_user_event(memory: dict, user_id: str, event_type: str, channel_id: str, content: str, source: str):
    """
    Adds a new event to a user's event stream.
    """
    if user_id not in memory["users"]:
        # This should ideally not happen if create_or_get_user is called first
        print(f"Warning: User {user_id} not found when trying to add event. Creating temporary entry.")
        memory["users"][user_id] = {"profile": {"name": f"Unknown {user_id}", "interface_type": source}, "events": [], "derived_facts": []}

    user_events = memory["users"][user_id]["events"]
    event = {
        "timestamp": datetime.datetime.now().isoformat(),
        "type": event_type,
        "channel_id": channel_id if channel_id is not None else DM_KEY,
        "content": content,
        "source": source
    }
    user_events.append(event)
    # We can implement a pruning strategy for events later if the list grows too large
    # For now, let's allow it to grow.

def save_memory(memory):
    with open(USER_MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_channel_memory(memory, channel_id):
    channel_key = DM_KEY if channel_id is None else str(channel_id)
    return memory.get(channel_key, [])

def update_channel_memory(memory, channel_id, new_data):
    channel_key = DM_KEY if channel_id is None else str(channel_id)
    if channel_key not in memory:
        memory[channel_key] = []
    formatted_data = []
    for item in new_data:
        if item["role"] == "user":
            formatted_data.append({"role": "user", "content": item["content"]})
        elif item["role"] == "assistant":
            formatted_data.append({"role": "assistant", "content": item["content"]})
    memory[channel_key].extend(formatted_data)
    if len(memory[channel_key]) > 20:  # Keep a maximum of 20 entries
        memory[channel_key] = memory[channel_key][-20:]
    save_memory(memory)