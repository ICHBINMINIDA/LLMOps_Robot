# Robot LLMOps — a self-hosted LLM gateway and benchmark for robot agents

Which local LLM should drive a robot? This project serves open models from a GPU server through a
unified, OpenAI-compatible gateway, monitors the hardware, and benchmarks every model on
**real robot commands**: does it pick the right tool, with the right arguments, fast enough?

No robot required — the robot's ROS 2 skills are exposed as mock tools with the same interface.

## Architecture

```
            your laptop (Docker)                                   GPU server
 ┌───────────────────────────────────────────────┐        ┌──────────────────────┐
 │  bench/run_bench.py ─┐                        │        │                      │
 │  bench/chat_demo.py ─┼─▶ LiteLLM :4000 ───────┼──HTTP──▶  Ollama :11434      │
 │  robot_agent.py ─────┘   routing, fallback,   │        │  llama3.1 / qwen2.5  │
 │          │               API keys             │        │  mistral  (GPU)      │
 │          ▼                                    │        │                      │
 │   Pushgateway :9091 ◀── benchmark results     │        │                      │
 │          │                                    │        │                      │
 │   Prometheus :9090 ◀── gpu-exporter :9400 ────┼──SSH───▶  nvidia-smi, free    │
 │          │                       └────────────┼──HTTP──▶  /api/ps (VRAM/model)│
 │   Grafana :3000  (dashboard)                  │        │                      │
 └───────────────────────────────────────────────┘        └──────────────────────┘
```

| Component | Role |
|---|---|
| **Ollama** | Local inference on the GPU server |
| **LiteLLM** | One OpenAI-compatible REST API for all models, a stable `robot-default` alias, automatic fallback, key auth |
| **gpu-exporter** | Reads `nvidia-smi` and `free` over SSH and Ollama `/api/ps`, exposes Prometheus metrics. Needs no root and no Docker on the server |
| **Benchmark** | 33 robot commands (English + German) across navigation, vision, grasping, placing, battery, emergency stop, and small talk where *no* tool must be called |
| **Prometheus + Grafana** | GPU utilisation, VRAM per model, RAM, temperature, power, and benchmark results per model |

## Quick start

```bash
cp .env.example .env            # set OLLAMA_API_BASE and SSH_TARGET
# edit litellm/config.yaml so the ollama_chat/<tag> names match `ollama list` on the server

docker compose up -d --build
curl http://localhost:4002/health/liveliness
```

Check that the gateway serves the models (REST API):

```bash
curl http://localhost:4002/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"model": "robot-default", "messages": [{"role": "user", "content": "Go to the kitchen"}]}'
```

Run the benchmark (Python 3.10+):

```bash
pip install -r requirements.txt
python bench/run_bench.py --repeats 3          # all models in the gateway
python bench/chat_demo.py                      # talk to the agent interactively
```

Open Grafana at http://localhost:3000 (admin / your password). The **Robot LLMOps** dashboard is the home page.

### Reaching the server

* **Direct** (VPN / campus network): `OLLAMA_API_BASE=http://<server>:11434`
* **SSH tunnel**: `ssh -N -L 11434:localhost:11434 user@server`, then `OLLAMA_API_BASE=http://host.docker.internal:11434`
* **Local Ollama** (no server): same as the tunnel value; set `GPU_MODE=local` or `off`

### GPU exporter

By default the exporter runs **on the host**, and Prometheus scrapes `host.docker.internal:9400`. On Windows the
Docker VM usually cannot reach a server behind a VPN, and mounted SSH keys get `0777` permissions that `ssh` refuses.
It needs key login to `SSH_TARGET` (`BatchMode`, never a password prompt):

```powershell
pip install prometheus-client
powershell -ExecutionPolicy Bypass -File start-exporter.ps1   # reads SSH_TARGET etc. from .env
```

On Linux/macOS you can run it as a container instead: `docker compose --profile docker-exporter up -d`
and set the Prometheus target back to `gpu-exporter:9400`.

## What is measured

| Metric | How |
|---|---|
| Tool accuracy | the first tool call names the expected tool (or no tool for small talk) |
| Tool + argument accuracy | tool correct **and** every expected argument matches |
| Command latency p50 / p95 | wall time for one robot command through the gateway |
| TTFT | time to first streamed token |
| Tokens / s | completion tokens ÷ generation time (after first token) |
| GPU / VRAM / RAM | live from the server, with VRAM attributed per loaded model |

Each run writes `results/<timestamp>/` with `report.md`, `summary.csv`, `robot_commands.csv` (every answer) and `speed.csv`.
The first request per model is a warm-up and is not measured, so model load time does not distort latency.

## Results

33 robot commands × 1 repeat, temperature 0, through LiteLLM → Ollama 0.40.6 on a multi-GPU server
(RTX 6000 Ada, TITAN RTX, RTX 2080 Ti). Full run: [`results/20261109-202521`](results/20261109-202521/report.md).

| Model | Tool acc. | Tool+args acc. | Latency p50 | Latency p95 | TTFT p50 | Tokens/s | Errors |
|---|---|---|---|---|---|---|---|
| **llama3.1:8b** | **88%** | **88%** | **0.18s** | **0.28s** | **0.16s** | **143.2** | 0 |
| qwen3:4b-instruct | 76% | 76% | 1.97s | 2.37s | 0.27s | 11.5 | 0 |
| mistral:7b | 15% | 15% | 15.24s | 46.81s | 0.92s | 3.9 | 1 |

**Takeaways**

* **llama3.1:8b** is the clear winner and backs the `robot-default` alias: most accurate and sub-second.
* Even the best model missed an emergency stop phrased indirectly (*"Halt, don't move, there's a child in the way!"*).
  Safety-critical commands like `stop` should not rely on the LLM alone. Use a keyword/rule pre-filter before the agent.
* **mistral** was largely offloaded to CPU on the server (≈0.4 GB of 8.9 GB in VRAM), so its latency is not representative.
  Its low accuracy is consistent with weak tool-calling support through Ollama's chat template.
* qwen3 is a thinking model. Its reasoning tokens make it slower than its size suggests.

## Using it from a ROS 2 agent

The robot code only needs an OpenAI-compatible client pointed at the gateway. Swapping or falling back between
models is configuration, not code:

```python
from openai import OpenAI
llm = OpenAI(base_url="http://localhost:4002/v1", api_key=LITELLM_MASTER_KEY)
resp = llm.chat.completions.create(model="robot-default", messages=msgs, tools=ROBOT_TOOLS)
```

## Extending

* Add commands to `bench/commands.jsonl` (`tool: null` means the model must answer without a tool).
* Add a model: one block in `litellm/config.yaml`, restart `litellm`, rerun the benchmark.
* Replace the mock tools in `bench/robot_tools.py` with ROS 2 action clients to run in Gazebo or on a real robot.
