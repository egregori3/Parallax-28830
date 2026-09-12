#!/usr/bin/env python3
"""Example: use `position_command` from Parallax-28830.py

This script dynamically imports the library file and sends a single
`!SC` position command. It can optionally override the MIN/MAX pulse
constants in the module before sending.

Usage examples:
    python3 examples/position_example.py --port /dev/ttyUSB0 --channel 0 --position 500

"""

import argparse
import importlib.util
from pathlib import Path


def load_parallax_module(path: Path):
    spec = importlib.util.spec_from_file_location("parallax_28830", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description="Send PSCU position command example")
    p.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (or virtual COM)")
    p.add_argument("--channel", type=int, default=0, help="Servo channel 0..31")
    p.add_argument("--position", type=int, default=500, help="Position 0..1000")
    p.add_argument("--ramp", type=int, default=0, help="Ramp 0..63")
    p.add_argument("--min-pulse", type=int, help="Optional override MIN_PULSE_US")
    p.add_argument("--max-pulse", type=int, help="Optional override MAX_PULSE_US")
    args = p.parse_args()

    root = Path(__file__).resolve().parent.parent
    libpath = root / "Parallax-28830.py"
    if not libpath.exists():
        raise SystemExit(f"Library file not found: {libpath}")

    mod = load_parallax_module(libpath)

    # optionally override module-level constants
    if args.min_pulse is not None:
        setattr(mod, "MIN_PULSE_US", int(args.min_pulse))
    if args.max_pulse is not None:
        setattr(mod, "MAX_PULSE_US", int(args.max_pulse))

    ctrl = mod.Parallax28830(args.port)
    with ctrl:
        # compute mapped pulse for display
        pulse = ctrl._position_to_pulse(args.position)
        print(f"Sending channel={args.channel} position={args.position} -> pulse_us={pulse} (ramp={args.ramp})")
        ctrl.position_command(args.channel, args.ramp, args.position)
        print("Command sent.")


if __name__ == "__main__":
    main()
