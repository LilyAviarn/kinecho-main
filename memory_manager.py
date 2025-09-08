import json
import datetime
from typing import List, Dict, Any
import time
import logging
import asyncio

KINECHO_MEMORY_FILE = "kinecho_memory.json"
DM_KEY = "dm"  # Define a key to use for DMs

#Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    filename='kinecho_memory.log', # Logs will go to this file
    filemode='a', # Append to the file if it exists
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to track if memory is 'dirty' (needs saving)
_memory_dirty = False
_last_save_time = 0 # Unix timestamp of last save
_save_interval = 500 # Save every x seconds if dirty
_memory_lock = asyncio.Lock() # To prevent race conditions during saves

def load_memory() -> dict:
    memory = {} # Initialize to empty dict
    try:
        with open(KINECHO_MEMORY_FILE, "r") as f: # Use the new file name
            memory = json.load(f)
    except FileNotFoundError: # Start with an empty dictionary if file doesn't exist
        memory = {"users": {}, "channels": {}, "kinecho_meta": {}}
    except json.JSONDecodeError: # Handle empty or malformed JSON
        print(f"Warning: {KINECHO_MEMORY_FILE} is empty or corrupted. Starting with fresh memory.")
        memory = {"users": {}, "channels": {}, "kinecho_meta": {}}

    # Ensure the top-level "users" key exists
    if "users" not in memory:
        memory["users"] = {}
    if "channels" not in memory:
        memory["channels"] = {}
    if "kinecho_meta" not in memory:
        memory["kinecho_meta"] = {}
    
    return memory

async def save_memory(memory: dict, force: bool = False):
    """
    Saves the entire memory dictionary to the JSON file, optionally forcing a save.
    This function is now asynchronous and uses a lock.
    """
    global _memory_dirty, _last_save_time

    async with _memory_lock: # Ensure only one save operation runs at a time
        if not _memory_dirty and not force and (time.time() - _last_save_time < _save_interval):
            # No changes, not forced, and not time for an interval save
            return

        try:
            with open(KINECHO_MEMORY_FILE, "w") as f:
                json.dump(memory, f, indent=4)
            _memory_dirty = False
            _last_save_time = time.time()
            print(f"DEBUG: Memory saved to {KINECHO_MEMORY_FILE}")
        except IOError as e:
            print(f"ERROR: Could not save memory to {KINECHO_MEMORY_FILE}: {e}")

def _mark_memory_dirty():
    """Internal helper to mark memory as dirty, indicating it needs saving."""
    global _memory_dirty
    _memory_dirty = True
    pass

async def create_or_get_user(memory: dict, user_id: str, user_name: str, interface_type: str, discord_id: str = None) -> dict:
    _mark_memory_dirty()

    # --- Robustness: Ensure 'users' key in memory is a dictionary ---
    if "users" not in memory:
        logger.error(f"Memory structure error: 'users' key missing in memory. Initializing 'users'.")
        memory["users"] = {}
    elif not isinstance(memory["users"], dict):
        logger.error(f"Memory structure error: 'users' key is not a dictionary (type: {type(memory['users'])}). Overwriting 'users'.")
        memory["users"] = {}

    # --- Core Logic: Safely get or create user data ---
    # Use .get() first to check existence and type without immediately creating
    existing_user_data = memory["users"].get(user_id)

    if existing_user_data is None or not isinstance(existing_user_data, dict):
        # User does not exist, OR existing data is malformed (None or not a dict)
        if existing_user_data is not None: # Log if it was malformed, not just missing
            logger.warning(
                f"User data anomaly: Existing entry for user_id='{user_id}' is malformed "
                f"(type: {type(existing_user_data)}). Overwriting with new user structure."
            )
        else:
            logger.info(f"Creating new user: user_id='{user_id}', user_name='{user_name}'")

        # Initialize the full structure for a new or completely malformed user
        user_data = {
            "profile": {
                "name": user_name,
                "interface_type": interface_type,
                "created_at": datetime.datetime.now().isoformat()
            },
            "events": [],
            "derived_facts": []
        }
        memory["users"][user_id] = user_data # Assign the newly created dict
    else:
        # User exists and its data is a dictionary
        user_data = existing_user_data
        logger.info(f"Accessing existing user: user_id='{user_id}', current_name='{user_data.get('profile', {}).get('name', 'N/A')}'")


    # --- Robustness: Ensure 'profile' dictionary within user_data exists and is correct type ---
    # This handles cases where an EXISTING user's data might have a malformed 'profile' key
    # This check is still necessary because the 'user_data' might have existed but its 'profile' key was bad
    if "profile" not in user_data:
        logger.warning(f"User data anomaly: 'profile' key missing for user_id='{user_id}'. Initializing 'profile'.")
        user_data["profile"] = {}
    elif not isinstance(user_data["profile"], dict):
        logger.warning(f"User data anomaly: 'profile' for user_id='{user_id}' is not a dictionary (type: {type(user_data['profile'])}). Overwriting 'profile'.")
        user_data["profile"] = {}

    user_profile = user_data["profile"]

    # --- Update or re-confirm common profile details for both new and existing users ---
    # These updates apply to the 'user_profile' reference which is guaranteed to be a dict
    if user_profile.get("name") != user_name:
        logger.info(f"Updating user_id='{user_id}' name from '{user_profile.get('name', 'N/A')}' to '{user_name}'.")
    user_profile["name"] = user_name

    if user_profile.get("interface_type") != interface_type:
        logger.info(f"Updating user_id='{user_id}' interface_type from '{user_profile.get('interface_type', 'N/A')}' to '{interface_type}'.")
    user_profile["interface_type"] = interface_type

    if discord_id:
        user_profile["discord_id"] = discord_id

    return user_data

async def add_user_event(memory: dict, user_id: str, event_type: str, channel_id: str, content: str, source: str):
    """
    Adds a new event to a user's event stream.
    """
    _mark_memory_dirty()
    if user_id not in memory["users"]:
        # This should ideally not happen if create_or_get_user is called first
        logger.warning(f"Attempted to add event for non-existent user_id: {user_id}. Creating user.")
        print(f"Warning: User {user_id} not found when trying to add event. Creating temporary entry.")
        memory["users"][user_id] = {
            "profile": {"name": f"Unknown {user_id}", "interface_type": source},
            "events": [],
            "derived_facts": []
        }
    user_events = memory["users"][user_id]["events"]
    memory["users"][user_id]["events"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "type": event_type,
        "channel_id": channel_id,
        "content": content,
        "source": source
    })
    await save_memory(memory)
    # We can implement a pruning strategy for events later if the list grows too large
    # For now, let's allow it to grow.

def get_channel_memory(memory, channel_id):
    """Retrieves conversation history for a given channel from the 'channels' top-level key."""
    channel_key = DM_KEY if channel_id is None else str(channel_id)
    return memory.get("channels", {}).get(channel_key, [])

async def update_channel_memory(memory, channel_id, new_data):
    """Adds messages to a channel's conversation history within the 'channels' top-level key."""
    _mark_memory_dirty()
    channel_key = DM_KEY if channel_id is None else str(channel_id)
    if "channels" not in memory:
        memory["channels"] = {}
    if channel_key not in memory["channels"]:
        memory["channels"][channel_key] = []
    formatted_data = []
    for item in new_data:
        if item["role"] == "user":
            formatted_data.append({"role": "user", "content": item["content"]})
        elif item["role"] == "assistant":
            formatted_data.append({"role": "assistant", "content": item["content"]})
    memory["channels"][channel_key].extend(formatted_data)
    if len(memory["channels"][channel_key]) > 20:  # Keep a maximum of 20 entries
        memory["channels"][channel_key] = memory["channels"][channel_key][-20:]
    await save_memory(memory)

async def add_derived_fact_to_user(user_id: str, fact_content: str, channel_id: str = None, source: str = "llm_derivation"):
    """
    Adds a new derived fact to a user's memory.
    The fact is stored as an object including timestamp, content, and source.
    Args:
        user_id: The ID of the Discord user.
        fact_content: The content of the derived fact (a string).
        channel_id: The channel ID related to the fact, if any (optional).
        source: The source of the derivation (default: "llm_derivation").
    """
    _mark_memory_dirty()
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
        await save_memory(memory) # Save memory after adding the fact
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

    history = memory.get("channels", {}).get(channel_key, [])

    # Return the last 'limit' messages (most recent)
    return history[-limit:]

async def initialize_kinecho_start_time():
    """
    Initializes Kinecho's overall start time in memory if it doesn't exist.
    Also initializes Kinecho's current session's start time, regardless if it already exists;
    This will be used to calculate uptime.
    """
    global _memory_dirty
    async with _memory_lock:
        memory = load_memory()
        if "kinecho_meta" not in memory:
            memory["kinecho_meta"] = {}
        if "kinecho_start_time" not in memory["kinecho_meta"]:
            memory["kinecho_meta"]["kinecho_start_time"] = time.time() # Store as Unix timestamp
            print(f"Kinecho Time: Initialized Kinecho's start time to {memory['kinecho_meta']['kinecho_start_time']}.")
            _memory_dirty = True

        memory["kinecho_meta"]["session_start_time"] = time.time()
        print(f"Kinecho Time: Initialized session start time to {memory['kinecho_meta']['session_start_time']}.")
        _memory_dirty = True

    return memory

def get_kinecho_uptime() -> Dict[str, Any]:
    """
    Returns Kinecho's total uptime since its first initialization.
    Returns:
        A dictionary with uptime in various formats (seconds, and human-readable string).
    """
    memory = load_memory()
    kinecho_start_time = memory.get("kinecho_meta", {}).get("kinecho_start_time")

    if kinecho_start_time is None:
        return {"error": "Kinecho start time not initialized. Please call initialize_kinecho_start_time first."}

    start_datetime_utc = datetime.datetime.fromtimestamp(kinecho_start_time, tz=datetime.timezone.utc)

    # Format into a human-readable string (convert from Unix)
    human_readable_time = start_datetime_utc.strftime("%A, %B %d, %Y at %I:%M:%S %p UTC")

    return {
        "human_readable_uptime": f"Kinecho's first initialization was {human_readable_time}.",
        "start_timestamp": kinecho_start_time,
        "current_timestamp": time.time()
    }

def get_session_uptime() -> Dict[str, Any]:
    """
    Calculates and returns Kinecho's current session's uptime.
    Returns:
        A dictionary with uptime in various formats (seconds, and human-readable string).
    """
    memory = load_memory()
    session_start_time = memory.get("kinecho_meta", {}).get("session_start_time")

    if session_start_time is None:
        return {"error": "Session start time not initialized. Please call initialize_kinecho_start_time first."}

    current_time = time.time()
    uptime_seconds = current_time - session_start_time

    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format into a human-readable string
    parts = []
    if days >= 1: # Use >=1 for days, as 0 days is not typically included in "X days Y hours"
        parts.append(f"{int(days)} day{'s' if days != 1 else ''}")
    if hours >= 1: # Use >=1 for hours
        parts.append(f"{int(hours)} hour{'s' if hours != 1 else ''}")
    if minutes >= 1: # Use >=1 for minutes
        parts.append(f"{int(minutes)} minute{'s' if minutes != 1 else ''}")

    # Include seconds if there's any, or if the total uptime is less than a minute
    if seconds > 0 or (not parts and uptime_seconds < 60):
        parts.append(f"{int(seconds)} second{'s' if seconds != 1 else ''}")

    human_readable_uptime = ", ".join(parts) if parts else "Just a moment..."

    return {
        "uptime_seconds": uptime_seconds,
        "human_readable_uptime": f"Kinecho has been 'awake' for {human_readable_uptime}.",
        "start_timestamp": session_start_time,
        "current_timestamp": current_time
    }
