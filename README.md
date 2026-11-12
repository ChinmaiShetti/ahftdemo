# ChipCheck hardware reference implementation

This directory is the hardware-side reference implementation for ChipCheck. It gives the experiment-selection software a small, deterministic JSON-over-stdin/stdout interface while keeping the physical wiring and safety checks outside the optimizer.

The package is intentionally a reference design, not an electrical approval. A hardware owner must review the pin mapping, supply voltage, current limits, driver components, and buzzer pass/fail criterion before connecting power.

## What is included

- `pi/chipcheck_hw.py` — Raspberry Pi executor. It reads one JSON command per line, applies the three LED PWM values, drives the buzzer for a defined observation window, and emits one JSON result per command.
- `pi/requirements.txt` — Raspberry Pi Python dependencies.
- `config/contract.yaml` — versioned experiment contract and conservative default limits.
- `arduino/measurement_bridge/measurement_bridge.ino` — optional Arduino-compatible bridge for three analog voltage measurements and a digital buzzer feedback input. It speaks a simple line protocol over USB serial.
- `docs/wiring.md` — wiring, pin table, component guidance, bring-up and safety procedure.
- `docs/protocol.md` — command/result protocol and field semantics.
- `docs/architecture.md` — system and data-flow diagrams.
- `examples/` — valid commands and representative results.

## Reference architecture

```text
Algorithm host / operator
          |
          | JSON lines over SSH, USB serial, or local pipe
          v
Raspberry Pi ---------------------- USB serial -------------------- Arduino/ADC bridge (optional)
  GPIO18 PWM -> LED1 driver -> LED1       A0 <- LED1 sense
  GPIO19 PWM -> LED2 driver -> LED2       A1 <- LED2 sense
  GPIO13 PWM -> LED3 driver -> LED3       A2 <- LED3 sense
  GPIO26     -> buzzer transistor -> buzzer
  GPIO21     <- optional digital observation input
```

The Pi's GPIO acknowledgement is not a buzzer measurement. For a real campaign, use either the bridge's feedback input or a calibrated microphone/sound-level backend. If no observation backend is configured, the executor returns `INVALID` rather than guessing `PASS`.

## Recommended wiring

The default logical-to-physical mapping is:

| Signal | BCM GPIO / Arduino | Purpose |
|---|---:|---|
| LED1 PWM | GPIO18 / A0 sense | LED1 control and optional measured voltage |
| LED2 PWM | GPIO19 / A1 sense | LED2 control and optional measured voltage |
| LED3 PWM | GPIO13 / A2 sense | LED3 control and optional measured voltage |
| BUZZER_EN | GPIO26 | Drives a transistor or MOSFET gate; never drive a large buzzer directly |
| BUZZER_FB | GPIO21 | Optional conditioned digital observation signal |
| Pi ground | GND | Common logic reference |

Each LED channel needs its own current-limiting resistor or a constant-current driver. A buzzer that exceeds Pi GPIO current limits needs a transistor/MOSFET, flyback protection for inductive devices, and a suitable external supply. See `docs/wiring.md` before assembly.

## Quick start on the Pi

```bash
cd pi
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 chipcheck_hw.py --contract ../config/contract.yaml --dry-run
```

`--dry-run` validates commands and returns deterministic simulated observations; it does not touch GPIO. It is useful for integration with the algorithm before hardware arrives.

For a real Pi, install the dependencies, connect the reviewed circuit, and run:

```bash
python3 chipcheck_hw.py --contract ../config/contract.yaml
```

Then send one JSON command per line. For example:

```json
{"campaign_id":"CC-001","batch_id":1,"experiment_id":"e-0001","command":"RUN_INTERACTION_TEST","parameters":{"led1_value":120,"led2_value":180,"led3_value":90}}
```

The process emits exactly one JSON result per input command. It never treats a missing or unreliable observation as a functional failure.

## Integration contract

The optimizer should submit `RUN_INTERACTION_TEST` commands and preserve `campaign_id`, `batch_id`, and `experiment_id`. The executor returns:

- `outcome`: `PASS`, `FAIL`, `INVALID`, or `ABORTED`;
- `status`: `COMPLETED`, `REJECTED`, `INVALID`, or `ABORTED`;
- `requested_parameters` and `applied_parameters`;
- measured LED values when available;
- observation quality and diagnostic details.

Out-of-range, malformed, duplicate, or unsafe commands are rejected before GPIO changes. Invalid observations are excluded from failure-region learning by the optimizer.

## Bring-up sequence

1. Hardware owner reviews and edits `config/contract.yaml`.
2. Test continuity and common ground with power removed.
3. Test one LED channel at a time at value `0`, then a low value such as `16`.
4. Confirm measured LED voltage/current is within the approved limits.
5. Test the buzzer driver with LEDs disconnected or disabled.
6. Verify the observation path using a known-good buzzer event.
7. Run the supplied dry-run protocol tests.
8. Run a small real campaign with manually inspected results.
9. Only then connect the adaptive planner.

## Important limitations

The three values are PWM duty-cycle commands by default, not analog voltages. Actual LED voltages depend on the driver, LED, load, supply, and measurement point. The bridge's ADC readings are optional measurements and must be calibrated. A campaign result is only as meaningful as the approved pass/fail criterion and repeatable reset procedure.

No finite experiment budget can prove that all disconnected failure regions have been found. Reports must say “not discovered within tested conditions and budget” when appropriate.

