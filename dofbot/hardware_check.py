"""Stage 1 only. Inventory by default; explicit --servo-test moves one joint."""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
from pathlib import Path
import subprocess
import time

LOG = logging.getLogger("hardware_check")
DEFAULT_CONFIG = Path(__file__).parent / "common" / "config.json"


def servo_spec(config, servo_id):
    if isinstance(servo_id, bool) or servo_id not in range(1, 7):
        raise ValueError("Servo ID trebuie sa fie 1..6; broadcast interzis.")
    arm = config["arm"]
    protocol = arm["protocol"]
    return arm, protocol, protocol["servo5" if servo_id == 5 else "standard"]


def encode_angle(config, servo_id, angle):
    arm, protocol, spec = servo_spec(config, servo_id)
    low, high = arm["limits_deg"][servo_id - 1]
    if not math.isfinite(angle) or not low <= angle <= high or not 0 <= angle <= spec["degrees"]:
        raise ValueError(f"S{servo_id}: unghi {angle} in afara limitelor.")
    physical = spec["degrees"] - angle if servo_id in protocol["inverted_servos"] else angle
    return int(spec["raw_min"] + physical * (spec["raw_max"] - spec["raw_min"]) / spec["degrees"])


def read_angle(bus, config, servo_id):
    arm, protocol, spec = servo_spec(config, servo_id)
    reg = protocol["read_register_base"] + servo_id
    bus.write_byte_data(arm["address"], reg, protocol["read_request"])
    time.sleep(protocol["read_delay_s"])
    word = bus.read_word_data(arm["address"], reg)
    raw = ((word & 255) << 8) | ((word >> 8) & 255)
    if not spec["raw_min"] <= raw <= spec["raw_max"]:
        raise RuntimeError(f"S{servo_id}: feedback invalid raw={raw}; nicio miscare permisa.")
    angle = (raw - spec["raw_min"]) * spec["degrees"] / (spec["raw_max"] - spec["raw_min"])
    if servo_id in protocol["inverted_servos"]:
        angle = spec["degrees"] - angle
    encode_angle(config, servo_id, angle)
    return angle


def write_angle(bus, config, servo_id, angle, duration_ms):
    raw = encode_angle(config, servo_id, angle)
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 1 <= duration_ms <= 65535:
        raise ValueError("Durata invalida, asteptat 1..65535 ms.")
    arm, protocol, _ = servo_spec(config, servo_id)
    payload = [raw >> 8, raw & 255, duration_ms >> 8, duration_ms & 255]
    LOG.info("S%s -> %.2f grade in %s ms", servo_id, angle, duration_ms)
    if bus is not None:
        bus.write_i2c_block_data(arm["address"], protocol["write_register_base"] + servo_id, payload)
    return payload


def test_servo(bus, config):
    settings = config["servo_test"]
    servo_id = settings["servo_id"]
    duration = settings["duration_ms"]
    if duration < 2000 or not 0 < abs(settings["delta_deg"]) <= 3:
        raise ValueError("Testul initial permite maximum 3 grade si minimum 2000 ms.")
    start = settings["dry_run_start_deg"] if bus is None else read_angle(bus, config, servo_id)
    low, high = config["arm"]["limits_deg"][servo_id - 1]
    delta = settings["delta_deg"]
    target = start + delta
    if not low <= target <= high:
        target = start - delta
    encode_angle(config, servo_id, start)
    encode_angle(config, servo_id, target)
    LOG.info("Test S%s: %.2f -> %.2f -> %.2f grade", servo_id, start, target, start)
    # Validate both endpoints before any movement. Restore only the tested joint.
    try:
        write_angle(bus, config, servo_id, target, duration)
        if bus is not None:
            time.sleep(duration / 1000 + settings["settle_s"])
            observed = read_angle(bus, config, servo_id)
            LOG.info("Feedback dupa deplasare: %.2f grade", observed)
            if abs(observed - target) > settings["read_tolerance_deg"]:
                raise RuntimeError("Feedback diferit de tinta; test esuat.")
    finally:
        write_angle(bus, config, servo_id, start, duration)
        if bus is not None:
            time.sleep(duration / 1000 + settings["settle_s"])
    if bus is not None:
        observed = read_angle(bus, config, servo_id)
        LOG.info("Feedback dupa revenire: %.2f grade", observed)
        if abs(observed - start) > settings["read_tolerance_deg"]:
            raise RuntimeError("Revenirea nu este confirmata de feedback.")
    LOG.info("Test %s incheiat. Observatia fizica trebuie confirmata de operator.",
             "SIMULAT" if bus is None else "I2C")


def inventory():
    report = {"modules": {}, "commands": {}}
    for name in ("Arm_Lib", "cv2", "numpy", "smbus", "smbus2", "picamera2"):
        spec = importlib.util.find_spec(name)
        report["modules"][name] = spec.origin if spec else None
    for name, command in {
        "csi": ["rpicam-hello", "--list-cameras"],
        "video": ["v4l2-ctl", "--list-devices"],
        "usb": ["lsusb"],
    }.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            report["commands"][name] = {"returncode": result.returncode,
                                         "output": result.stdout + result.stderr}
        except (OSError, subprocess.TimeoutExpired) as exc:
            report["commands"][name] = {"error": str(exc)}
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--servo-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bus = None
    try:
        if args.servo_test:
            if not args.dry_run:
                from smbus import SMBus
                bus = SMBus(config["arm"]["bus"])
            test_servo(bus, config)
        else:
            inventory()
        return 0
    except KeyboardInterrupt:
        LOG.warning("Intrerupt. Home si gripper nu sunt calibrate; nu comand alte articulatii.")
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        LOG.error("Oprit: %s", exc)
        return 1
    finally:
        if bus is not None:
            bus.close()


if __name__ == "__main__":
    raise SystemExit(main())
