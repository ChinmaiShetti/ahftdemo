#!/usr/bin/env python3
"""ChipCheck Raspberry Pi hardware executor.

One JSON command is read from stdin and one JSON result is written to stdout.
The default real backend uses gpiozero. --dry-run performs all contract and
protocol validation without touching GPIO.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

import yaml


class HardwareExecutor:
    def __init__(self, contract: dict[str, Any], dry_run: bool = False, history: Path | None = None):
        self.contract = contract
        self.dry_run = dry_run
        self.history = history
        self.seen: set[str] = set()
        self.leds: dict[str, Any] = {}
        self.buzzer = None
        self.feedback = None
        self._load_history()
        if not dry_run:
            try:
                from gpiozero import DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
            except ImportError as exc:
                raise RuntimeError("gpiozero is required on a real Raspberry Pi; use --dry-run on a development machine") from exc
            inputs = contract["inputs"]
            for name in ("led1_value", "led2_value", "led3_value"):
                self.leds[name] = PWMOutputDevice(
                    inputs[name]["gpio_bcm"], frequency=contract["device"].get("pwm_frequency_hz", 1000), initial_value=0
                )
            output = contract["output"]
            self.buzzer = DigitalOutputDevice(
                output["control_gpio_bcm"], active_high=output.get("active_high", True), initial_value=False
            )
            if output.get("feedback_gpio_bcm") is not None:
                self.feedback = DigitalInputDevice(output["feedback_gpio_bcm"], pull_up=False)

    def _load_history(self) -> None:
        if not self.history or not self.history.exists():
            return
        for line in self.history.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if item.get("experiment_id") is not None:
                    self.seen.add(str(item["experiment_id"]))
            except json.JSONDecodeError:
                continue

    def safe_state(self) -> None:
        if self.dry_run:
            return
        for led in self.leds.values():
            led.value = 0
        if self.buzzer is not None:
            self.buzzer.off()

    def close(self) -> None:
        self.safe_state()
        for device in [*self.leds.values(), self.buzzer, self.feedback]:
            if device is not None:
                device.close()

    def _base_result(self, command: dict[str, Any]) -> dict[str, Any]:
        result = {k: command.get(k) for k in ("campaign_id", "batch_id", "experiment_id")}
        result.update({"status": "REJECTED", "requested_parameters": command.get("parameters"), "applied_parameters": None,
                       "measurements": {}, "outcome": "INVALID", "measurement_quality": "INVALID",
                       "diagnostics": {"backend": "dry_run" if self.dry_run else "digital_feedback", "error": None}})
        return result

    def _reject(self, command: dict[str, Any], reason: str) -> dict[str, Any]:
        result = self._base_result(command)
        result["diagnostics"]["error"] = reason
        return result

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        result = self._base_result(command)
        experiment_id = command.get("experiment_id")
        if command.get("command") != "RUN_INTERACTION_TEST":
            return self._reject(command, "unsupported command")
        if experiment_id is None:
            return self._reject(command, "experiment_id is required")
        experiment_id = str(experiment_id)
        if experiment_id in self.seen:
            return self._reject(command, "duplicate experiment_id")
        parameters = command.get("parameters")
        if not isinstance(parameters, dict):
            return self._reject(command, "parameters must be an object")

        values: dict[str, int] = {}
        for name in ("led1_value", "led2_value", "led3_value"):
            spec = self.contract["inputs"][name]
            value = parameters.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                return self._reject(command, f"{name} must be an integer")
            if value < spec["min"] or value > spec["max"] or (value - spec["min"]) % spec.get("step", 1):
                return self._reject(command, f"{name} is outside the approved range or step")
            values[name] = value
        if values in self.contract.get("safety", {}).get("prohibited_combinations", []):
            return self._reject(command, "prohibited input combination")

        self.seen.add(experiment_id)
        result["status"] = "COMPLETED"
        result["requested_parameters"] = values
        result["applied_parameters"] = values.copy()
        try:
            if self.dry_run:
                measurements = self._dry_run_measurement(values)
            else:
                measurements = self._run_real(values)
            result["measurements"] = measurements
            requirement = self.contract["output"].get("requirement", {})
            detected = measurements.get("buzzer_detected")
            if requirement.get("require_buzzer_detected", True) and detected is None:
                result["outcome"] = "INVALID"
                result["measurement_quality"] = "INVALID"
                result["diagnostics"]["error"] = "no buzzer observation was available"
            elif requirement.get("require_buzzer_detected", True) and not detected:
                result["outcome"] = "FAIL"
                result["measurement_quality"] = "VALID"
            else:
                result["outcome"] = "PASS"
                result["measurement_quality"] = "VALID"
        except KeyboardInterrupt:
            result["status"] = "ABORTED"
            result["outcome"] = "ABORTED"
            result["measurement_quality"] = "INVALID"
        except Exception as exc:  # hardware errors must not crash the stream
            result["status"] = "INVALID"
            result["outcome"] = "INVALID"
            result["measurement_quality"] = "INVALID"
            result["diagnostics"]["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            self.safe_state()
        self._record(result)
        return result

    def _dry_run_measurement(self, values: dict[str, int]) -> dict[str, Any]:
        # Deterministic integration behavior: dry-run always represents a known-good observation.
        return {"buzzer_detected": True, "response_time_ms": 0.0,
                "led1_voltage_v": None, "led2_voltage_v": None, "led3_voltage_v": None}

    def _run_real(self, values: dict[str, int]) -> dict[str, Any]:
        for name, value in values.items():
            self.leds[name].value = value / 255.0
        output = self.contract["output"]
        time.sleep(output.get("settle_time_ms", 100) / 1000.0)
        start = time.monotonic()
        self.buzzer.on()
        detected = None
        deadline = start + output.get("observation_window_ms", 500) / 1000.0
        if self.feedback is not None:
            detected = False
            active = bool(self.contract.get("measurement", {}).get("feedback_active_level", 1))
            while time.monotonic() < deadline:
                if bool(self.feedback.value) == active:
                    detected = True
                    break
                time.sleep(0.005)
        else:
            time.sleep(output.get("observation_window_ms", 500) / 1000.0)
        self.buzzer.off()
        return {"buzzer_detected": detected, "response_time_ms": (time.monotonic() - start) * 1000.0,
                "led1_voltage_v": None, "led2_voltage_v": None, "led3_voltage_v": None}

    def _record(self, result: dict[str, Any]) -> None:
        if self.history:
            self.history.parent.mkdir(parents=True, exist_ok=True)
            with self.history.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--history", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    executor = HardwareExecutor(contract, dry_run=args.dry_run, history=args.history)
    def stop(_sig: int, _frame: Any) -> None:
        executor.close()
        raise SystemExit(130)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                command = json.loads(line)
                result = executor.execute(command)
            except (json.JSONDecodeError, TypeError) as exc:
                result = {"status": "REJECTED", "outcome": "INVALID", "measurement_quality": "INVALID",
                          "diagnostics": {"backend": "dry_run" if args.dry_run else "digital_feedback", "error": str(exc)}}
            print(json.dumps(result, separators=(",", ":")), flush=True)
    finally:
        executor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

