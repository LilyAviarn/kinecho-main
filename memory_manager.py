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
    If the user doesn't exist, a new profile is created with the nested 'profile' structure.
    If the user exists, their 'profile.name' is updated to the latest provided.
    """
    if "users" not in memory:
        memory["users"] = {}

    if user_id not in memory["users"]:
        memory["users"][user_id] = {
            "profile": {
                "name": user_name,
                "interface_type": interface_type,
                "created_at": datetime.datetime.now().isoformat()
            },
            "events": [],
            "derived_facts": []
        }
    else:
        # User exists, ensure 'profile' dictionary exists and update the 'name'
        user_profile = memory["users"][user_id].get("profile", {})
        if not user_profile: # If 'profile' key didn't exist or was empty
            memory["users"][user_id]["profile"] = {}
            user_profile = memory["users"][user_id]["profile"]

        user_profile["name"] = user_name
        # Also update other profile details in case they changed or were missing
        user_profile["interface_type"] = interface_type
        if discord_id:
            user_profile["discord_id"] = discord_id

    return memory["users"][user_id]

def add_user_event(memory: dict, user_id: str, event_type: str, channel_id: str, content: str, source: str):
    """
    Adds a new event to a user's event stream.
    """
    if user_id not in memory["users"]:
        # This should ideally not happen if create_or_get_user is called first
        print(f"Warning: User {user_id} not found when trying to add event. Creating temporary entry.")
        memory["users"][user_id] = {
            "profile": {"name": f"Unknown {user_id}", "interface_type": source},
            "events": [],
            "derived_facts": []
        }
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

def add_derived_fact_to_user(user_id: str, fact_content: str, channel_id: str = None, source: str = "llm_derivation"):
    """
    Adds a new derived fact to a user's memory.
    The fact is stored as an object including timestamp, content, and source.
    Args:
        user_id: The ID of the Discord user.
        fact_content: The content of the derived fact (a string).
        channel_id: The channel ID related to the fact, if any (optional).
        source: The source of the derivation (default: "llm_derivation").
    """
    memory = load_memory()
    user_data = memory.get("users", {}).get(user_id)
    if user_data:
        if "derived_facts" not in user_data:
            user_data["derived_facts"] = []

        fact_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "content": fact_content,
            "channel_id": channel_id,
            "source": source
        }
        user_data["derived_facts"].append(fact_entry)
        save_memory(memory) # Save memory after adding the fact
    else:
        print(f"WARNING: Attempted to add derived fact for non-existent user ID: {user_id}")

def get_derived_facts_for_user(user_id: str, limit: int = 10) -> List[str]:
    """
    Retrieves a limited number of recent derived facts associated with a specific user.
    Returns only the 'content' string of each fact for easy consumption by the LLM.
    Args:
        user_id: The ID of the Discord user.
        limit: The maximum number of recent facts to retrieve.
    Returns:
        A list of strings, each representing the content of a derived fact.
    """
    memory = load_memory()
    user_data = memory.get("users", {}).get(user_id, {})
    facts = user_data.get("derived_facts", [])

    # Return only the 'content' string from the last 'limit' fact entries
    return [fact["content"] for fact in facts[-limit:]]

def get_conversation_history_for_channel(channel_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Retrieves a limited number of recent messages from a specific channel's memory.
    Args:
        channel_id: The Discord ID of the channel whose conversation history is to be retrieved.
        limit: The maximum number of recent messages to retrieve.
    Returns:
        A list of dictionaries, each representing a message (role, content).
    """
    memory = load_memory() # Load the full memory
    
    # Ensure channel_id is treated as a string key, as it's stored in memory.
    # Handles both direct channel IDs and the DM_KEY if applicable.
    channel_key = str(channel_id) if channel_id is not None else DM_KEY

    history = memory.get(channel_key, [])

    # Return the last 'limit' messages (most recent)
    return history[-limit:]