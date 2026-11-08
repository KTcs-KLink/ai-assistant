"""Launch only the checkout-owned local operations sidecar. No keys or .env reads."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def check(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def main():
    try:
        active = check("http://127.0.0.1:8848/api/control/health")
        if active.get("app") != "KLINK_LOCAL_OPERATIONS":
            raise SystemExit("Port 8848 belongs to another service; nothing was stopped.")
        print("K:LINK operations ready: http://127.0.0.1:8825/hr/admin")
        return
    except (URLError, TimeoutError):
        pass
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8848)) == 0:
            raise SystemExit("Port 8848 is already in use; nothing was stopped.")
    caps = check("http://127.0.0.1:8846/api/benefits/hr/capabilities")
    if caps.get("source_scope") != "expanded":
        raise SystemExit("Start the preserved expanded HR service on 8846 first.")
    logs = ROOT / ".demo-logs"
    logs.mkdir(exist_ok=True)
    output = (logs / "operations-8848.log").open("ab")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "operations.service:app", "--host", "127.0.0.1", "--port", "8848", "--no-access-log"],
                               cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    output.close()
    for _ in range(30):
        try:
            if check("http://127.0.0.1:8848/api/control/health").get("app") == "KLINK_LOCAL_OPERATIONS":
                (logs / "operations-8848.pid").write_text(str(process.pid), encoding="ascii")
                print("K:LINK operations ready: http://127.0.0.1:8825/hr/admin")
                return
        except (URLError, TimeoutError):
            if process.poll() is not None:
                raise SystemExit("Operations service did not start; inspect .demo-logs/operations-8848.log") from None
        time.sleep(.25)
    raise SystemExit("Operations startup is still unconfirmed; existing services were preserved.")


if __name__ == "__main__":
    main()
