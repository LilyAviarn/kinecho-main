Welcome! If you're reading this, I've invited you to help me with Kinecho. Thank you!
Kinecho is a *very* early work-in-progress AI companion. Kinecho *currently* runs off of two scripts: `chatbot.py` for standalone communication, and `discord_bot.py` for Discord integration. These will at some point be reorganized to be initialized by a central script.
Kinecho has limited memory retention; in any given conversation (currently separated by channel ID; DMs and Console are logged under the same entry) Kinecho will remember the 20 previous turns, and sends the previous 10 as context. This memory is stored in kinecho_memory.json and managed by `memory_manager.py`.
Kinecho's `settings.ini` is very limited and currently only contains "input_method" and "output_method" for the standalone console.
As of `5/24/25`, Kinecho runs using a *basic, untrained OpenAI model*.

Kinecho will eventually be able to accurately maintain conversation, have full range of Discord features, have modular game functionality, have web search capabilities, and have an on-screen model! But that's a ways out from now, so thank you for your patience and helping me bring Kinecho to life.~
-LilyAviarn
