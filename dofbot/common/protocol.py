"""Direct I2C subset, checked against Arm_Lib V0.0.5. No writes on import."""
import logging
import math
import time

LOG = logging.getLogger(__name__)


def servo_spec(config, servo_id):
    if isinstance(servo_id, bool) or not isinstance(servo_id, int) or servo_id not in range(1, 7):
        raise ValueError("Servo ID trebuie sa fie 1..6; broadcast interzis.")
    arm = config["arm"]
    protocol = arm["protocol"]
    return arm, protocol, protocol["servo5" if servo_id == 5 else "standard"]


def encode_angle(config, servo_id, angle):
    arm, protocol, spec = servo_spec(config, servo_id)
    low, high = arm["limits_deg"][servo_id - 1]
    if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not low <= angle <= high or not 0 <= angle <= spec["degrees"]:
        raise ValueError(f"S{servo_id}: unghi {angle} in afara limitelor.")
    physical = spec["degrees"] - angle if servo_id in protocol["inverted_servos"] else angle
    return int(spec["raw_min"] + physical * (spec["raw_max"] - spec["raw_min"]) / spec["degrees"])


def read_angle(bus, config, servo_id):
    arm, protocol, spec = servo_spec(config, servo_id)
    reg = protocol["read_register_base"] + servo_id
    if isinstance(protocol['read_attempts'], bool) or not isinstance(protocol['read_attempts'], int) or not 1 <= protocol['read_attempts'] <= 5:
        raise ValueError('Numar invalid de incercari pentru feedback.')
    for attempt in range(protocol["read_attempts"]):
        bus.write_byte_data(arm["address"], reg, protocol["read_request"])
        time.sleep(protocol["read_delay_s"])
        word = bus.read_word_data(arm["address"], reg)
        raw = ((word & 255) << 8) | ((word >> 8) & 255)
        if raw != 0:
            break
        if attempt + 1 < protocol["read_attempts"]:
            LOG.warning("S%s: feedback gol, reiau citirea (%s/%s).", servo_id, attempt + 1, protocol["read_attempts"])
            time.sleep(protocol["read_retry_s"])
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

