"""Read-only local classification viewer. The static server receives no credentials."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent/'outputs/klink_domain_workflow_20261109'
APP_ID = 'klink-domain-workflow-view-20261109'


def marker(origin):
    try:
        with urlopen(origin+'/view-manifest.json', timeout=2) as response:
            value = json.load(response)
        return value.get('app_id') == APP_ID and value.get('source_units') == 10205
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=8852)
    parser.add_argument('--no-open', action='store_true'); args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not (OUT/'view-manifest.json').is_file():
        raise SystemExit('분류 보고서 준비와 포트 범위를 확인해 주세요.')
    origin = f'http://127.0.0.1:{args.port}'
    try:
        with socket.create_connection(('127.0.0.1', args.port), timeout=.3):
            running = True
    except OSError:
        running = False
    if running:
        if not marker(origin):
            raise SystemExit('다른 프로그램이 사용 중인 포트입니다. 기존 프로그램은 유지했습니다.')
    else:
        logs = ROOT/'.demo-logs/domain-workflow'; logs.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not any(t in k.upper() for t in
            ('OPENAI', 'SUPABASE', 'SECRET', 'TOKEN', 'PASSWORD', 'KEY', 'KLINK_ENV_FILE'))}
        env['PYTHONIOENCODING'] = 'utf-8'
        interpreter = ROOT/'server/.venv/Scripts/python.exe'
        if not interpreter.is_file():
            interpreter = Path(sys.executable)
        with (logs/'view.log').open('a', encoding='utf-8') as log:
            proc = subprocess.Popen([str(interpreter), '-m', 'http.server', str(args.port), '--bind', '127.0.0.1', '--directory', str(OUT)],
                cwd=ROOT, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        (logs/f'process-{args.port}.json').write_text(json.dumps(dict(pid=proc.pid, port=args.port, app_id=APP_ID)), encoding='utf-8')
        deadline = time.monotonic()+15
        while not marker(origin):
            if proc.poll() is not None or time.monotonic() > deadline:
                raise SystemExit('분류 보고서 화면을 시작하지 못했습니다.')
            time.sleep(.2)
    print(origin+'/')
    if not args.no_open:
        webbrowser.open(origin+'/')


if __name__ == '__main__':
    main()
