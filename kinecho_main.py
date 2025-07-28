import asyncio
import os
import sys
from dotenv import load_dotenv
from typing import List, Dict, Any, Callable
from interfaces.discord_bot_interface import DiscordInterface, intents
from interfaces.console_interface import ConsoleInterface
import kinecho_tools
import chatbot
import memory_manager
import logging
import traceback

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(
    level=logging.DEBUG,
    filename='kinecho_main.log', # Logs will go to this file
    filemode='a', # Append to the file if it exists
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to hold active interface instances, needed for tool calling
# We initialize them as None, and they will be set in main()
global_discord_interface: DiscordInterface = None
global_console_interface: ConsoleInterface = None
global_kinecho_memory: Dict[str, Any] = {}

async def main():
    global global_discord_interface, global_console_interface, global_kinecho_memory

    print("Kinecho Main: Starting Kinecho Commander...")

    global_kinecho_memory = memory_manager.load_memory()
    memory_manager.initialize_kinecho_start_time()
    await memory_manager.save_memory(memory_manager.load_memory(), force=True)

    interface_instances: Dict[str, Any] = {}

    global_discord_interface = DiscordInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        intents=intents,
        interface_instances=interface_instances,
        kinecho_memory=global_kinecho_memory
    )
    global_console_interface = ConsoleInterface(
        chatbot_processor_func=chatbot.get_chat_response,
        interface_instances=interface_instances,
        kinecho_memory=global_kinecho_memory
    )

    interface_instances["discord_interface"] = global_discord_interface
    interface_instances["console_interface"] = global_console_interface

    discord_task = None
    console_task = None
    save_task = asyncio.create_task(periodic_memory_saver())
    asyncio.create_task(periodic_memory_saver())

    while True:
        try:
            command_line = (await asyncio.to_thread(input, "Kinecho Commander > ")).strip()

            if command_line.lower() == 'quit':
                print("Kinecho Commander: Initiating graceful shutdown...")
                logger.info("Kinecho Commander: Initiating graceful shutdown...")
                sys.exit(0)
            
                # --- MEMORY SAVER SHUTDOWN GOES HERE ---
                logger.info("Kinecho Main: Stopping periodic memory saver...")
                save_task.cancel()
                try:
                    await save_task # Await cancellation to ensure it cleans up
                except asyncio.CancelledError:
                    logger.info("Kinecho Main: Periodic memory saver stopped.")
                except Exception as e:
                    logger.error(f"Kinecho Main: Error while stopping periodic memory saver: {e}")
                finally:
                    # Force one last save on shutdown to capture any final changes
                    logger.info("Kinecho Main: Forcing final memory save on shutdown.")
                    await memory_manager.save_memory(memory_manager.load_memory(), force=True)

                break

            elif command_line.lower() == 'start discord':
                logger.info("Start Discord command used.")
                if not global_discord_interface.is_running:
                    print("Kinecho Commander: Starting Discord interface...")
                    logger.info("Kinecho Commander: Starting Discord interface...")
                    discord_task = asyncio.create_task(global_discord_interface.initialize_interface(DISCORD_BOT_TOKEN))
                    # Optionally wait for it to be ready, or just let it run in the background
                else:
                    print("Discord interface is already running.")
                    logger.info("Discord interface is already running.")
        
            elif command_line.lower() == 'stop discord':
                logger.info("Stop Discord command used.")
                if global_discord_interface.is_running:
                    print("Kinecho Commander: Stopping Discord interface...")
                    logger.info("Kinecho Commander: Stopping Discord interface...")
                    global_discord_interface.stop()
                    if discord_task and not discord_task.done():
                        await discord_task # Wait for the task to finish if it's still running
                else:
                    print("Discord interface is not running.")
                    logger.info("Discord interface is not running.")

            elif command_line.lower() == 'start console':
                logger.info("Start Console command used.")
                if not global_console_interface.is_running:
                    print("Kinecho Commander: Starting Console interface...")
                    logger.info("Kinecho Commander: Starting Console interface...")

                    # Initialize the console interface (now non-blocking)
                    await global_console_interface.initialize_interface() 

                    if global_console_interface.is_running: # Ensure initialization was successful
                        print("Console Interface: Ready for input. Type 'quit' to exit application, 'stop console' (from commander) to exit mode.") # Clarify usage
                        # Enter a new, dedicated loop for console input
                        while True: # This loop now runs until 'quit' or 'stop console' (indirectly)
                            # Use the desired "You > " prompt here
                            console_input = (await asyncio.to_thread(input, "You > ")).strip() 

                            if console_input.lower() == "quit":
                                print("Kinecho Commander: Initiating full application shutdown.")
                                logger.info("Kinecho Commander: Initiating full application shutdown.")
                                # Calling stop() on the interface isn't strictly necessary here as we're exiting
                                sys.exit(0) # Exit the entire application from within the console loop

                            # If it's the 'stop console' command, we need to exit this inner loop
                            # and let the main loop handle the 'stop console' command.
                            # Or, more simply, if it's the 'stop console' command, we can just break from this loop.
                            # Let's make 'stop console' directly applicable from 'You >' prompt too
                            if console_input.lower() == "stop console":
                                await global_console_interface.stop() # This sets is_running to False
                                print("Kinecho Commander: Exited Console interface mode.")
                                break # Exit this inner console input loop and return to the main commander loop

                            # Create the MockMessage object with nested attributes
                            user_id_console = "console_user" 
                            channel_id_console = "kinecho_console_chat" 

                            mock_message_for_console = type('MockMessage', (object,), {
                                'author': type('MockAuthor', (object,), {'id': user_id_console, 'display_name': "You (Console)"}),
                                'content': console_input,
                                'channel': type('MockChannel', (object,), {'id': channel_id_console}),
                                'guild': None 
                            })()

                            # Call receive_message, passing only the mock_message_for_console object
                            try:
                                await global_console_interface.receive_message(mock_message_for_console) 
                            except Exception as e:
                                print(f"ERROR: Console interface message processing failed: {e}")
                                logger.error(f"Console interface message processing failed: {e}", exc_info=True)
                    else:
                        print("ERROR: Console interface failed to start properly. Check logs.")
                else:
                    print("Console interface is already running.")
                    logger.info("Console interface is already running.")

            elif command_line.lower() == 'stop console':
                logger.info("Stop Console command used.")
                if global_console_interface.is_running:
                    print("Kinecho Commander: Stopping Console interface...")
                    logger.info("Kinecho Commander: Stopping Console interface...")
                    await global_console_interface.stop()
                    if console_task and not console_task.done():
                        await console_task # Wait for the task to finish
                else:
                    print("Console interface is not running.")
                    logger.info("Console interface is not running.")

            elif command_line.lower() == 'status':
                logger.info("Status command used.")
                discord_status = "Running" if global_discord_interface.is_running else "Stopped"
                console_status = "Running" if global_console_interface.is_running else "Stopped"
                print(f"Interface Status:")
                print(f"  Discord: {discord_status}")
                print(f"  Console: {console_status}")
                logger.info(f"  Discord: {discord_status}")
                logger.info(f"  Console: {console_status}")

            elif command_line.lower() == 'help':
                logger.info("Help command used.")
                print("Commands:")
                print("  quit          - Exit the Kinecho Commander.")
                print("  start discord - Start the Discord bot interface.")
                print("  stop discord  - Stop the Discord bot interface.")
                print("  start console - Start the console interface.")
                print("  stop console  - Stop the console interface.")
                print("  status        - Show the running status of interfaces.")
                print("  [your message] - Send a message to the console interface.")

            elif command_line:
                # Treat as a message for the console interface
                user_id = "console_user"
                channel_id = "kinecho_console_chat"
                mock_message = type('MockMessage', (object,), {
                    'author': type('MockAuthor', (object,), {'id': user_id, 'display_name': "You (Console)"}),
                    'content': command_line,
                    'channel': type('MockChannel', (object,), {'id': channel_id}),
                    'guild': None
                })()
                try:
                    await global_console_interface.receive_message(mock_message)
                except Exception as e:
                    print(f"ERROR: Console interface message processing failed: {e}")
                    logger.error(f"Console interface message processing failed: {e}", exc_info=True) # exc_info=True for traceback
            
        except Exception as e:
            print(f"ERROR: An error occurred in the main loop: {e}")
            logger.error(f"An error occurred in the main loop: {e}")

    print("Kinecho Main: Kinecho Commander exited.")
    logger.info("Kinecho Main: Kinecho Commander exited.")

async def periodic_memory_saver():
    """Background task to periodically save memory if it's dirty."""
    while True:
        await asyncio.sleep(memory_manager._save_interval) # Use the defined interval
        if memory_manager._memory_dirty:
            print("DEBUG: Periodic save triggered.")
            # Load memory inside the task, as the 'memory' object passed around
            # might not be the most up-to-date global state if you move to a more
            # centralized memory object. For now, load_memory() always gets the latest.
            await memory_manager.save_memory(memory_manager.load_memory())
        else:
            print("DEBUG: Periodic save skipped (memory not dirty).")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKinecho Main: Shutdown initiated by user via KeyboardInterrupt.")
    except Exception as e:
        print(f"Kinecho Main: An unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        print("Kinecho Main: Application finished.")
