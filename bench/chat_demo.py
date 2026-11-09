"""
Interactive robot agent through the gateway, with mock tools.
Shows the full loop: user command -> LLM picks tool -> (simulated) robot executes -> LLM answers.

  python bench/chat_demo.py                 # uses the robot-default alias (with fallback)
  python bench/chat_demo.py -m llama3.1
"""
import argparse
import json
import os

from openai import OpenAI

from robot_tools import SYSTEM_PROMPT, TOOLS, execute
from run_bench import load_env


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", default="robot-default")
    ap.add_argument("--gateway", default=os.getenv("LITELLM_URL", "http://localhost:4002"))
    args = ap.parse_args()
    client = OpenAI(base_url=f"{args.gateway}/v1", api_key=os.getenv("LITELLM_MASTER_KEY", "sk-none"))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"Robot agent via {args.model}. Type a command (empty line to quit).")
    while (text := input("\nyou> ").strip()):
        messages.append({"role": "user", "content": text})
        for _ in range(4):                      # allow a few tool steps per command
            msg = client.chat.completions.create(model=args.model, messages=messages,
                                                 tools=TOOLS, temperature=0).choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                print(f"robot> {msg.content}")
                break
            for call in msg.tool_calls:
                result = execute(call.function.name, json.loads(call.function.arguments or "{}"))
                print(f"  [tool] {call.function.name}({call.function.arguments}) -> {result}")
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})


if __name__ == "__main__":
    main()
