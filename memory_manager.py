# memory_manager.py
import json

MEMORY_FILE = "kinecho_memory.json"
DM_KEY = "dm"  # Define a key to use for DMs

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    except FileNotFoundError:
        memory = {}
    return memory

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_channel_memory(memory, channel_id):
    channel_key = DM_KEY if channel_id is None else str(channel_id)  # Use DM_KEY for DMs
    return memory.get(channel_key, [])

def update_channel_memory(memory, channel_id, new_data):
    channel_key = DM_KEY if channel_id is None else str(channel_id)  # Use DM_KEY for DMs
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