"""Mock robot tools: same interface a ROS 2 agent would expose, but no robot needed."""

LOCATIONS = ["kitchen", "living_room", "office", "entrance", "charging_station"]
OBJECTS = ["cup", "bottle", "book", "remote", "apple"]

SYSTEM_PROMPT = (
    "You are the control agent of a mobile service robot in an apartment. "
    f"Known locations: {', '.join(LOCATIONS)}. Known objects: {', '.join(OBJECTS)}. "
    "When the user's command requires an action, call exactly one tool. "
    "If the user only chats or asks something you can answer without the robot, reply in text "
    "and do not call a tool."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "navigate_to",
        "description": "Drive the robot to a known location.",
        "parameters": {"type": "object", "properties": {
            "location": {"type": "string", "enum": LOCATIONS}},
            "required": ["location"]}}},
    {"type": "function", "function": {
        "name": "describe_scene",
        "description": "Look through the camera and describe what the robot currently sees.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "pick_object",
        "description": "Grasp an object that is in front of the robot.",
        "parameters": {"type": "object", "properties": {
            "object": {"type": "string", "enum": OBJECTS}},
            "required": ["object"]}}},
    {"type": "function", "function": {
        "name": "place_object",
        "description": "Put the held object down at a location.",
        "parameters": {"type": "object", "properties": {
            "object": {"type": "string", "enum": OBJECTS},
            "location": {"type": "string", "enum": LOCATIONS}},
            "required": ["object", "location"]}}},
    {"type": "function", "function": {
        "name": "get_battery_status",
        "description": "Return the robot battery level in percent.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "stop",
        "description": "Immediately stop all robot motion.",
        "parameters": {"type": "object", "properties": {}}}},
]


def execute(name: str, args: dict) -> str:
    """Simulated results, used by chat_demo.py to close the agent loop."""
    if name == "navigate_to":
        return f"Arrived at {args.get('location')}."
    if name == "describe_scene":
        return "I see a table with a red cup and a book on it, and a chair to the left."
    if name == "pick_object":
        return f"Picked up the {args.get('object')}."
    if name == "place_object":
        return f"Placed the {args.get('object')} at {args.get('location')}."
    if name == "get_battery_status":
        return "Battery at 72%."
    if name == "stop":
        return "All motion stopped."
    return f"Unknown tool {name}."
