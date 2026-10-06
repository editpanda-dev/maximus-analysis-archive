"""Capture package versions, never credentials or environment variables."""
import argparse
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,default=Path('.'))
    args=parser.parse_args()
    packages={d.metadata['Name']:d.version for d in distributions() if d.metadata.get('Name')}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'requirements-windows-py312-lock.txt').write_text(
        ''.join(f'{name}=={version}\n' for name,version in sorted(packages.items(),key=lambda x:x[0].lower())),encoding='utf-8')
    snapshot={'python':platform.python_version(),'platform':platform.platform(),'architecture':platform.machine(),
              'implementation':platform.python_implementation(),'packages':packages,
              'scope':'installed_packages_only_no_API_keys','fresh_environment_reinstall_verified':False}
    (args.output_dir/'analysis-environment.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Captured {len(packages)} package versions; no credentials read.')

if __name__=='__main__':main()
