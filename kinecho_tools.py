# --- Define Tools Available to the Chatbot ---
# This is a list of dictionaries, where each dictionary describes a tool.
# The structure follows OpenAI's tool definition format.
AVAILABLE_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_discord_user_status",
            "description": "Retrieves the online status, custom status, display name, username, joined date, and shared guild of a Discord user by their user ID. This works only if the bot is in a shared server with the user and has the necessary permissions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord ID of the user whose status is to be retrieved."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Retrieves the current date and time in a specified timezone. Defaults to America/New_York (Eastern Standard Time).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_str": {
                        "type": "string",
                        "description": "The IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Defaults to 'America/New_York'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversation_history_for_channel",
            "description": "Retrieves recent conversation history (messages) from a specific Discord channel. Useful for recalling what was discussed in other channels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The Discord ID of the channel whose conversation history is to be retrieved."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of recent messages to retrieve (default: 10).",
                        "default": 10
                    }
                },
                "required": ["channel_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_user_derived_fact",
            "description": "Adds a new high-level, summarized fact or insight about a specific Discord user to Kinecho's long-term memory. This should be used when Kinecho learns a significant piece of information about a user (e.g., their hobby, a personal preference, a recurring statement).",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord ID of the user to whom the fact pertains."
                    },
                    "fact_content": {
                        "type": "string",
                        "description": "The content of the derived fact to be stored."
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "Optional: The Discord ID of the channel where the fact was derived or is relevant."
                    }
                },
                "required": ["user_id", "fact_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_derived_facts",
            "description": "Retrieves high-level, summarized facts or insights about a specific Discord user that Kinecho has learned over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord ID of the user whose derived facts are to be retrieved."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of recent derived facts to retrieve (default: 10).",
                        "default": 10
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_discord_channel_id_by_name",
            "description": "Retrieves the Discord numerical ID for a given channel name. Use this if the user provides a channel name (e.g., '#general', 'bot-commands') but you need the numerical ID to interact with other tools like getting conversation history. Can optionally search within a specific guild if its ID is known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The name of the Discord channel (e.g., 'general', 'bot-commands')."
                    },
                    "guild_id": {
                        "type": "string",
                        "description": "Optional: The Discord ID of the guild (server) to search within, if known. This helps when multiple guilds have channels with the same name."
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    {
    "type": "function",
        "function": {
            "name": "get_kinecho_uptime",
            "description": "Retrieves how long Kinecho has been running. Can be used to fetch either session uptime or uptime overall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "The scope of uptime to retrieve. Choose between 'all' or 'session'."
                    }
                },
                "required": ["scope"]
            }
        }
    },
    {
    "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Sets a timer for the specified duration. Optionally, a reason can be set, which will be included in the timerEnd message to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "integer",
                        "description": "The duration of the timer in 'hh:mm:ss'."
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason the user is requesting the timer, such as '', '' or ''."
                    }
                },
                "required": ["duration"]
            }
        }
    },
    {
    "DO NOT USE ANYTHING BELOW THIS LINE, KINECHO! It WILL NOT work if you try! -Lily"
    },
    {
    "type": "function",
        "function": {
            "name": "get_time_elapsed",
            "description": "Retrieves the amount of time that has elapsed since a specified message or event.",
            # I plan for this function to be able to get the timestamp of either a message (for discord probably via message link), 
            # or an event from Kinecho's memory, and then calculate how much time has passed from then til "now" 
            # (probably fetched via `get_current_time`).
            "parameters": {
                "type": "object",
                "properties": {
                    "argument": {
                        "type": "",
                        "description": ""
                    },
                    "argument2": {
                        "type": "",
                        "description": ""
                    }
                }
            }
        }
    }
    # New tools go here
]