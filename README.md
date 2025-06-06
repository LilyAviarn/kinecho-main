Welcome! If you're reading this, I've invited you to help me with Kinecho. Thank you!
Kinecho is a *very* early work-in-progress AI companion. Kinecho runs off of a centralized script (`kinecho_main.py`), through which either a console or the discord interfaces (or both) may be launched. [KNOWN ISSUE: both interfaces run through the same terminal]
Kinecho has limited memory retention; in any given conversation Kinecho will remember the 20 previous turns. This memory is stored in kinecho_user_memory.json and managed by `memory_manager.py`.
Kinecho's `settings.ini` is very limited and currently only contains "input_method" and "output_method" for the console interface.
As of `5/24/25`, Kinecho runs using a *basic, untrained OpenAI model (3.5 turbo)*.

Kinecho will eventually be able to accurately maintain conversation, have full range of Discord features, have modular game functionality, have web search capabilities, and have an on-screen model! But that's a ways out from now, so thank you for your patience and helping me bring Kinecho to life.~
-LilyAviarn
