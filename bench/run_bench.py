"""
Robot command benchmark through the LiteLLM gateway.

Per model it measures:
  1. Speed      - time to first token (TTFT) and generation tokens/second (streaming)
  2. Robot test - for each command in commands.jsonl: latency, correct tool, correct arguments

Results: results/<timestamp>/  (raw CSV + report.md) and Prometheus Pushgateway (Grafana).

Usage:
  python bench/run_bench.py                         # all models from the gateway
  python bench/run_bench.py -m qwen2.5 -m llama3.1  # selected models
  python bench/run_bench.py --repeats 3
"""
import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from robot_tools import SYSTEM_PROMPT, TOOLS

ROOT = Path(__file__).resolve().parent.parent
SPEED_PROMPTS = [
    "Explain in about 150 words how a mobile robot uses a map to navigate an apartment.",
    "Write a short checklist (8 items) for safely testing a new robot behaviour.",
    "Describe the difference between local and global path planning in about 120 words.",
]


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    i = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return s[i]


# ---------------------------------------------------------------- speed test
def speed_test(client: OpenAI, model: str) -> list[dict]:
    rows = []
    for prompt in SPEED_PROMPTS:
        t0 = time.perf_counter()
        ttft, chunks, usage = None, 0, None
        stream = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}],
            stream=True, stream_options={"include_usage": True},
            max_tokens=300, temperature=0,
        )
        for chunk in stream:
            if chunk.usage:
                usage = chunk.usage
            if chunk.choices and chunk.choices[0].delta.content:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                chunks += 1
        total = time.perf_counter() - t0
        out_tokens = usage.completion_tokens if usage else chunks   # fallback: 1 chunk ~ 1 token
        gen_time = max(total - (ttft or 0), 1e-6)
        rows.append({"model": model, "prompt": prompt[:40], "ttft_s": round(ttft or total, 3),
                     "total_s": round(total, 3), "output_tokens": out_tokens,
                     "tokens_per_s": round(out_tokens / gen_time, 2)})
    return rows


# ---------------------------------------------------------------- robot test
def norm(v) -> str:
    return str(v).strip().lower().replace(" ", "_")


def robot_test(client: OpenAI, model: str, commands: list[dict], repeats: int) -> list[dict]:
    rows = []
    for _ in range(repeats):
        for cmd in commands:
            t0 = time.perf_counter()
            error, got_tool, got_args = "", None, {}
            try:
                resp = client.chat.completions.create(
                    model=model, temperature=0, tools=TOOLS,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": cmd["text"]}],
                )
                calls = resp.choices[0].message.tool_calls or []
                if calls:
                    got_tool = calls[0].function.name
                    try:
                        got_args = json.loads(calls[0].function.arguments or "{}")
                    except json.JSONDecodeError:
                        error = "invalid JSON arguments"
                usage = resp.usage
            except Exception as exc:  # noqa: BLE001
                error, usage = str(exc)[:200], None
            latency = time.perf_counter() - t0

            tool_ok = got_tool == cmd["tool"]
            args_ok = tool_ok and all(norm(got_args.get(k)) == norm(v) for k, v in cmd["args"].items())
            rows.append({
                "model": model, "id": cmd["id"], "command": cmd["text"],
                "expected_tool": cmd["tool"] or "-", "got_tool": got_tool or "-",
                "expected_args": json.dumps(cmd["args"], ensure_ascii=False),
                "got_args": json.dumps(got_args, ensure_ascii=False),
                "tool_ok": int(tool_ok), "args_ok": int(args_ok),
                "latency_s": round(latency, 3),
                "prompt_tokens": usage.prompt_tokens if usage else "",
                "completion_tokens": usage.completion_tokens if usage else "",
                "error": error,
            })
            mark = "OK " if args_ok else ("~  " if tool_ok else "X  ")
            print(f"  {mark}{cmd['id']:<9} {latency:5.2f}s  got={got_tool} {got_args}")
    return rows


# ---------------------------------------------------------------- reporting
def summarize(model: str, speed: list[dict], robot: list[dict]) -> dict:
    lat = [r["latency_s"] for r in robot if not r["error"]]
    ttft = [r["ttft_s"] for r in speed]
    n = len(robot) or 1
    return {
        "model": model,
        "tool_accuracy": sum(r["tool_ok"] for r in robot) / n,
        "args_accuracy": sum(r["args_ok"] for r in robot) / n,
        "errors": sum(1 for r in robot if r["error"]),
        "latency_p50": pct(lat, 0.5), "latency_p95": pct(lat, 0.95),
        "ttft_p50": pct(ttft, 0.5),
        "tokens_per_s": statistics.mean(r["tokens_per_s"] for r in speed) if speed else float("nan"),
    }


def push_metrics(s: dict, gateway: str) -> None:
    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
    except ImportError:
        print("prometheus_client not installed -> skipping Pushgateway")
        return
    reg = CollectorRegistry()
    Gauge("robot_bench_tool_accuracy", "Correct tool chosen", registry=reg).set(s["tool_accuracy"])
    Gauge("robot_bench_args_accuracy", "Correct tool and arguments", registry=reg).set(s["args_accuracy"])
    Gauge("robot_bench_tokens_per_second", "Generation speed", registry=reg).set(s["tokens_per_s"])
    lat = Gauge("robot_bench_latency_seconds", "Robot command latency", ["quantile"], registry=reg)
    lat.labels("p50").set(s["latency_p50"])
    lat.labels("p95").set(s["latency_p95"])
    Gauge("robot_bench_ttft_seconds", "Time to first token", ["quantile"], registry=reg) \
        .labels("p50").set(s["ttft_p50"])
    try:
        push_to_gateway(gateway, job="robot_bench", grouping_key={"model": s["model"]}, registry=reg)
    except Exception as exc:  # noqa: BLE001
        print(f"Pushgateway not reachable ({exc}) -> results only saved to disk")


def write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def write_report(path: Path, summaries: list[dict], robot_rows: list[dict], n_cmds: int, repeats: int) -> None:
    lines = [f"# Robot command benchmark - {datetime.now():%Y-%m-%d %H:%M}", "",
             f"{n_cmds} commands x {repeats} repeat(s) per model, temperature 0, through LiteLLM -> Ollama.", "",
             "| Model | Tool acc. | Tool+args acc. | Latency p50 | Latency p95 | TTFT p50 | Tokens/s | Errors |",
             "|---|---|---|---|---|---|---|---|"]
    for s in sorted(summaries, key=lambda x: -x["args_accuracy"]):
        lines.append(f"| {s['model']} | {s['tool_accuracy']:.0%} | {s['args_accuracy']:.0%} | "
                     f"{s['latency_p50']:.2f}s | {s['latency_p95']:.2f}s | {s['ttft_p50']:.2f}s | "
                     f"{s['tokens_per_s']:.1f} | {s['errors']} |")
    lines += ["", "## Failed commands", "", "| Model | Command | Expected | Got |", "|---|---|---|---|"]
    for r in robot_rows:
        if not r["args_ok"]:
            lines.append(f"| {r['model']} | {r['command']} | {r['expected_tool']} {r['expected_args']} | "
                         f"{r['got_tool']} {r['got_args']} {r['error']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", action="append", help="model name in the gateway (repeatable)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--gateway", default=os.getenv("LITELLM_URL", "http://localhost:4002"))
    ap.add_argument("--pushgateway", default=os.getenv("PUSHGATEWAY", "localhost:9091"))
    ap.add_argument("--skip-speed", action="store_true")
    args = ap.parse_args()

    client = OpenAI(base_url=f"{args.gateway}/v1", api_key=os.getenv("LITELLM_MASTER_KEY", "sk-none"),
                    timeout=180)
    models = args.model or [m.id for m in client.models.list().data if m.id != "robot-default"]
    commands = [json.loads(l) for l in (ROOT / "bench/commands.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    out = ROOT / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    all_speed, all_robot, summaries = [], [], []

    for model in models:
        print(f"\n=== {model} ===")
        print("  warm-up (loads the model into VRAM, not measured)...")
        client.chat.completions.create(model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=5)
        speed = [] if args.skip_speed else speed_test(client, model)
        robot = robot_test(client, model, commands, args.repeats)
        s = summarize(model, speed, robot)
        print(f"  -> tool {s['tool_accuracy']:.0%} | tool+args {s['args_accuracy']:.0%} | "
              f"p50 {s['latency_p50']:.2f}s | {s['tokens_per_s']:.1f} tok/s")
        push_metrics(s, args.pushgateway)
        all_speed += speed
        all_robot += robot
        summaries.append(s)

    write_csv(out / "speed.csv", all_speed)
    write_csv(out / "robot_commands.csv", all_robot)
    write_csv(out / "summary.csv", summaries)
    write_report(out / "report.md", summaries, all_robot, len(commands), args.repeats)
    print(f"\nSaved to {out}\n")
    print((out / "report.md").read_text(encoding="utf-8").split("## Failed")[0])


if __name__ == "__main__":
    main()
