#!/usr/bin/env python3
"""Send a sequence of PSCU position commands from a CSV file.

- CSV columns: delay, channel, position, ramp
- delay: milliseconds to wait AFTER sending the command (int or float)
- channel: integer 0..31
- position: integer 0..1000 (mapped to MIN_PULSE_US..MAX_PULSE_US)
- ramp: integer 0..63

Example CSV:
    delay,channel,position,ramp
    0.5,0,500,0
    1.0,1,750,5

Usage:
    python3 examples/sequence_from_csv.py --port /dev/ttyUSB0 --csv myseq.csv

"""

import csv
import time
import argparse
import importlib.util
from pathlib import Path


def load_parallax_module(path: Path):
    spec = importlib.util.spec_from_file_location("parallax_28830", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_row(row, line_no):
    try:
        # delay is provided in milliseconds in the CSV
        delay = float(row.get("delay", "0") or 0)
        channel = int(row["channel"])
        position = int(row["position"])
        ramp = int(row.get("ramp", "0") or 0)
    except KeyError as e:
        raise ValueError(f"Missing column in CSV on line {line_no}: {e}")
    except Exception as e:
        raise ValueError(f"Invalid data on line {line_no}: {e}")
    return delay, channel, position, ramp


def main():
    p = argparse.ArgumentParser(description="Send PSCU sequence from CSV")
    p.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    p.add_argument("csv", help="Path to CSV file")
    p.add_argument("--min-pulse", type=int, help="Optional override MIN_PULSE_US")
    p.add_argument("--max-pulse", type=int, help="Optional override MAX_PULSE_US")
    p.add_argument("--lib", default="../Parallax-28830.py", help="Path to library file")
    args = p.parse_args()

    libpath = Path(args.lib)
    if not libpath.exists():
        raise SystemExit(f"Library file not found: {libpath}")

    mod = load_parallax_module(libpath.resolve())

    # optionally override module-level constants
    if args.min_pulse is not None:
        setattr(mod, "MIN_PULSE_US", int(args.min_pulse))
    if args.max_pulse is not None:
        setattr(mod, "MAX_PULSE_US", int(args.max_pulse))

    csvpath = Path(args.csv)
    if not csvpath.exists():
        raise SystemExit(f"CSV file not found: {csvpath}")

    ctrl = mod.Parallax28830(args.port)

    with ctrl:
        with csvpath.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if not {"delay", "channel", "position", "ramp"}.issubset(reader.fieldnames or []):
                raise SystemExit("CSV must contain columns: delay, channel, position, ramp")
            for i, row in enumerate(reader, start=2):
                try:
                    delay_ms, channel, position, ramp = parse_row(row, i)
                except ValueError as e:
                    print(f"Skipping row {i}: {e}")
                    continue
                print(f"Line {i}: sending channel={channel} position={position} ramp={ramp} (then delay {delay_ms} ms)")
                try:
                    ctrl.position_command(channel, ramp, position)
                except Exception as e:
                    print(f"Error sending command on line {i}: {e}")
                if delay_ms > 0:
                    try:
                        time.sleep(delay_ms / 1000.0)
                    except KeyboardInterrupt:
                        print("Interrupted during sleep; exiting")
                        return


if __name__ == "__main__":
    main()
