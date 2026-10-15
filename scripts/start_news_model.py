import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import ProxyHandler, build_opener


def safe_failure(path: Path) -> str:
    text = path.read_text(errors="replace")[-12000:].lower() if path.exists() else ""
    for needle, message in (
        ("no space left", "runner disk space exhausted"),
        ("requires more system memory", "model exceeds available runner memory"),
        ("not enough memory", "model exceeds available runner memory"),
        ("address already in use", "local model port is occupied"),
        ("connection refused", "local model server is unavailable"),
        ("checksum", "download integrity check failed"),
        ("manifest", "model manifest download failed"),
        ("tls handshake", "download TLS connection failed"),
    ):
        if needle in text:
            return message
    status = re.search(r"\b(?:401|403|404|408|429|500|502|503|504)\b", text)
    return "model download returned HTTP " + status[0] if status else "model startup or download did not complete"


def main() -> None:
    temporary = Path(os.environ["RUNNER_TEMP"])
    log = temporary / "presence-ai.log"
    pull_log = temporary / "presence-pull.log"
    model = os.environ.get("NEWS_LOCAL_MODEL", "qwen2.5:7b")
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    print(f"::notice title=Local AI resources::{os.cpu_count()} CPUs; {memory:.1f} GiB memory; {model}", flush=True)
    with log.open("wb") as output:
        process = subprocess.Popen(["ollama", "serve"], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    opener = build_opener(ProxyHandler({}))
    for attempt in range(60):
        if process.poll() is not None:
            raise RuntimeError(safe_failure(log))
        try:
            with opener.open("http://127.0.0.1:11434/api/version", timeout=2) as response:
                json.load(response)
            break
        except OSError:
            time.sleep(1)
    else:
        raise RuntimeError(safe_failure(log))
    for attempt in range(3):
        with pull_log.open("wb") as output:
            try:
                result = subprocess.run(["ollama", "pull", model], stdout=output, stderr=subprocess.STDOUT, timeout=100)
                success = result.returncode == 0
            except subprocess.TimeoutExpired:
                success = False
        if success:
            print("::notice title=Local AI ready::Model download verified; editorial worker can start.", flush=True)
            return
        print(f"::warning title=Model download retry::Attempt {attempt + 1}: {safe_failure(pull_log)}", flush=True)
        if attempt < 2:
            time.sleep(5)
    raise RuntimeError(safe_failure(pull_log))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error title=Local AI startup::{type(error).__name__}: {error}", flush=True)
        raise SystemExit(1)
