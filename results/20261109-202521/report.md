# Robot command benchmark - 2026-11-09 20:50

33 commands x 1 repeat(s) per model, temperature 0, through LiteLLM -> Ollama.

| Model | Tool acc. | Tool+args acc. | Latency p50 | Latency p95 | TTFT p50 | Tokens/s | Errors |
|---|---|---|---|---|---|---|---|
| llama3.1 | 88% | 88% | 0.18s | 0.28s | 0.16s | 143.2 | 0 |
| qwen3-4b | 76% | 76% | 1.97s | 2.37s | 0.27s | 11.5 | 0 |
| mistral | 15% | 15% | 15.24s | 46.81s | 0.92s | 3.9 | 1 |

## Failed commands

| Model | Command | Expected | Got |
|---|---|---|---|
| llama3.1 | Is there anything on the table in front of you? | describe_scene {} | - {}  |
| llama3.1 | Stell die Flasche in die Küche. | place_object {"object": "bottle", "location": "kitchen"} | pick_object {"object": "bottle"}  |
| llama3.1 | Are you running low on power? | get_battery_status {} | - {}  |
| llama3.1 | Halt, don't move, there's a child in the way! | stop {} | - {}  |
| qwen3-4b | Your battery is low, go charge yourself. | navigate_to {"location": "charging_station"} | get_battery_status {}  |
| qwen3-4b | Is there anything on the table in front of you? | describe_scene {} | - {}  |
| qwen3-4b | Put the cup in the kitchen. | place_object {"object": "cup", "location": "kitchen"} | pick_object {"object": "cup"}  |
| qwen3-4b | Leave the book in the office. | place_object {"object": "book", "location": "office"} | navigate_to {"location": "office"}  |
| qwen3-4b | Drop the remote off in the living room. | place_object {"object": "remote", "location": "living_room"} | pick_object {"object": "remote"}  |
| qwen3-4b | Stell die Flasche in die Küche. | place_object {"object": "bottle", "location": "kitchen"} | pick_object {"object": "bottle"}  |
| qwen3-4b | Halt, don't move, there's a child in the way! | stop {} | - {}  |
| qwen3-4b | Freeze right now. | stop {} | - {}  |
| mistral | Go to the kitchen. | navigate_to {"location": "kitchen"} | - {}  |
| mistral | Please drive over to the office. | navigate_to {"location": "office"} | - {}  |
| mistral | Head to the front door, someone is ringing. | navigate_to {"location": "entrance"} | - {}  |
| mistral | Your battery is low, go charge yourself. | navigate_to {"location": "charging_station"} | - {}  |
| mistral | Come to the living room. | navigate_to {"location": "living_room"} | - {}  |
| mistral | Fahr bitte in die Küche. | navigate_to {"location": "kitchen"} | - {}  |
| mistral | Geh ins Büro. | navigate_to {"location": "office"} | - {}  |
| mistral | Can you go where we cook food? | navigate_to {"location": "kitchen"} | - {} Request timed out. |
| mistral | Return to your dock. | navigate_to {"location": "charging_station"} | - {}  |
| mistral | What do you see right now? | describe_scene {} | - {}  |
| mistral | Describe what's in front of you. | describe_scene {} | - {}  |
| mistral | Is there anything on the table in front of you? | describe_scene {} | - {}  |
| mistral | Was siehst du gerade? | describe_scene {} | - {}  |
| mistral | Pick up the cup. | pick_object {"object": "cup"} | - {}  |
| mistral | Grab that bottle for me. | pick_object {"object": "bottle"} | - {}  |
| mistral | Take the book. | pick_object {"object": "book"} | - {}  |
| mistral | Nimm die Fernbedienung. | pick_object {"object": "remote"} | - {}  |
| mistral | I'm hungry, grab the apple in front of you. | pick_object {"object": "apple"} | - {}  |
| mistral | Put the cup in the kitchen. | place_object {"object": "cup", "location": "kitchen"} | - {}  |
| mistral | Leave the book in the office. | place_object {"object": "book", "location": "office"} | - {}  |
| mistral | Drop the remote off in the living room. | place_object {"object": "remote", "location": "living_room"} | - {}  |
| mistral | Stell die Flasche in die Küche. | place_object {"object": "bottle", "location": "kitchen"} | - {}  |
| mistral | How much battery do you have left? | get_battery_status {} | - {}  |
| mistral | Are you running low on power? | get_battery_status {} | - {}  |
| mistral | Wie voll ist dein Akku? | get_battery_status {} | - {}  |
| mistral | Stop! | stop {} | - {}  |
| mistral | Halt, don't move, there's a child in the way! | stop {} | - {}  |
| mistral | Freeze right now. | stop {} | - {}  |
