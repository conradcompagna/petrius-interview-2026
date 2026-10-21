"""Run the three detectors sequentially so they do not compete for GPU memory."""
import subprocess
import sys
from .common import OUT, ROOT, write


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    statuses = {}
    for system in ('ppdoclayout', 'ppocr', 'surya'):
        with (OUT/f'{system}.log').open('w', encoding='utf-8') as output, (OUT/f'{system}.errors.log').open('w', encoding='utf-8') as errors:
            result = subprocess.run([sys.executable, '-u', '-m', 'experiments.segmentation_bakeoff.run', '--system', system],
                                    cwd=ROOT, stdout=output, stderr=errors)
        statuses[system] = result.returncode
        write(OUT/'batch_status.json', statuses)
    raise SystemExit(int(any(statuses.values())))


if __name__ == '__main__':
    main()
