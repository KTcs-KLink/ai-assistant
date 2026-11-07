"""Exact secret-value scan; never prints values, headers, SDK bodies or snippets."""
import json
import re
import subprocess
import sys

from dotenv import dotenv_values
from evaluate_hr_expansion import REPO,WORKSPACE,ROOT
from expand_hr_sources import write


def main():
    values=dotenv_values(WORKSPACE/'.env')
    private=[v.encode() for k,v in values.items() if v and len(v)>=8 and re.search(r'KEY|TOKEN|SECRET|PASSWORD',k,re.I)]
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=REPO).decode().split('\0')
    git_paths=[REPO/p for p in names if p and (REPO/p).is_file()]
    artifacts=[p for p in ROOT.rglob('*') if p.is_file()]
    hits=0
    for path in git_paths+artifacts:
        content=path.read_bytes()
        hits+=any(value in content for value in private)
    env_files=[p for p in names if p and (p.rsplit('/',1)[-1]=='.env' or p.rsplit('/',1)[-1].startswith('.env.')) and not p.endswith('.env.example')]
    report=dict(git_files_checked=len(git_paths),artifact_files_checked=len(artifacts),nonempty_private_values_checked=len(private),
        exact_private_value_matches=hits,unexpected_env_files_in_git_inventory=len(env_files),values_or_matching_snippets_reported=False)
    write(ROOT/'private-value-verification.json',report)
    print(json.dumps(report),flush=True)
    if hits or env_files:raise SystemExit('Private-value check failed; do not push.')


if __name__=='__main__':main()
