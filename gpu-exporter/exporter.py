"""
GPU / RAM / Ollama exporter for Prometheus.

Works with only two things on the deep server:
  - SSH access that can run `nvidia-smi` (and optionally `free`)
  - the Ollama HTTP API

Run in Docker (see docker-compose.yml) or directly:  python exporter.py
"""
import json
import os
import subprocess
import time
import urllib.request

from prometheus_client import Gauge, start_http_server

GPU_MODE = os.getenv("GPU_MODE", "ssh")            # ssh | local | off
SSH_TARGET = os.getenv("SSH_TARGET", "")
OLLAMA = os.getenv("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
INTERVAL = float(os.getenv("SCRAPE_INTERVAL_SECONDS", "5"))
PORT = int(os.getenv("EXPORTER_PORT", "9400"))

GPU_LABELS = ["gpu", "name"]
gpu_util = Gauge("gpu_utilization_percent", "GPU utilization", GPU_LABELS)
gpu_mem_used = Gauge("gpu_memory_used_bytes", "GPU memory used", GPU_LABELS)
gpu_mem_total = Gauge("gpu_memory_total_bytes", "GPU memory total", GPU_LABELS)
gpu_temp = Gauge("gpu_temperature_celsius", "GPU temperature", GPU_LABELS)
gpu_power = Gauge("gpu_power_watts", "GPU power draw", GPU_LABELS)
host_mem_used = Gauge("host_memory_used_bytes", "Server RAM used")
host_mem_total = Gauge("host_memory_total_bytes", "Server RAM total")
ollama_up = Gauge("ollama_up", "1 if the Ollama API answered")
ollama_model_vram = Gauge("ollama_model_vram_bytes", "VRAM held by a loaded model", ["model"])
ollama_model_size = Gauge("ollama_model_size_bytes", "Total size of a loaded model", ["model"])
nvsmi_up = Gauge("nvidia_smi_up", "1 if nvidia-smi could be read")

NVSMI_QUERY = [
    "nvidia-smi",
    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
    "--format=csv,noheader,nounits",
]
MIB = 1024 * 1024


def run(cmd: list[str]) -> str:
    if GPU_MODE == "ssh":
        # BatchMode: never hang waiting for a password; ControlMaster reuses one connection
        opts = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=accept-new"]
        if os.name != "nt":     # Windows OpenSSH has no ControlMaster (connection sharing)
            opts += ["-o", "ControlMaster=auto", "-o", "ControlPath=/tmp/ssh-%r@%h:%p",
                     "-o", "ControlPersist=60"]
        cmd = ["ssh", *opts, SSH_TARGET, " ".join(cmd)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True).stdout


def num(value: str) -> float:
    try:
        return float(value)
    except ValueError:          # "[N/A]" on some GPUs
        return float("nan")


def collect_gpu() -> None:
    try:
        out = run(NVSMI_QUERY)
    except Exception as exc:  # noqa: BLE001
        nvsmi_up.set(0)
        print(f"[gpu] nvidia-smi failed: {exc}", flush=True)
        return
    nvsmi_up.set(1)
    for line in out.strip().splitlines():
        idx, name, util, used, total, temp, power = [p.strip() for p in line.split(",")]
        labels = (idx, name)
        gpu_util.labels(*labels).set(num(util))
        gpu_mem_used.labels(*labels).set(num(used) * MIB)
        gpu_mem_total.labels(*labels).set(num(total) * MIB)
        gpu_temp.labels(*labels).set(num(temp))
        gpu_power.labels(*labels).set(num(power))


def collect_ram() -> None:
    """Optional: `free -b`. Silently skipped if not allowed on the server."""
    try:
        out = run(["free", "-b"])
        mem = next(l for l in out.splitlines() if l.lower().startswith("mem:")).split()
        host_mem_total.set(float(mem[1]))
        host_mem_used.set(float(mem[2]))
    except Exception:  # noqa: BLE001
        pass


def collect_ollama() -> None:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=5) as resp:
            data = json.load(resp)
    except Exception as exc:  # noqa: BLE001
        ollama_up.set(0)
        print(f"[ollama] /api/ps failed: {exc}", flush=True)
        return
    ollama_up.set(1)
    ollama_model_vram.clear()
    ollama_model_size.clear()
    for m in data.get("models", []):
        ollama_model_vram.labels(m["name"]).set(m.get("size_vram", 0))
        ollama_model_size.labels(m["name"]).set(m.get("size", 0))


def main() -> None:
    start_http_server(PORT)
    print(f"exporter on :{PORT}  mode={GPU_MODE}  ollama={OLLAMA}", flush=True)
    while True:
        if GPU_MODE != "off":
            collect_gpu()
            collect_ram()
        collect_ollama()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
