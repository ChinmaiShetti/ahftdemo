# Wiring and safety

This is a reference wiring plan for a 3.3 V Raspberry Pi. Confirm the exact Pi model and header before wiring.

## LED channels

Use one independent circuit per channel:

```text
Pi PWM GPIO ---- resistor / driver input ---- LED driver ---- LED ---- current limit ---- supply return
Pi GND --------------------------------------------------------------- common ground
```

For a simple low-current demonstration, a GPIO may drive a series resistor and LED only if the LED current, GPIO source/sink current, and total bank current are within the Pi model's approved limits. For a production-like setup, use a transistor or constant-current LED driver and measure the voltage at the agreed measurement point.

Suggested default pins are BCM 18, 19, and 13 because they support hardware PWM on common Pi models, but the final contract must identify the actual model and pin mux. Never connect an external voltage above the Pi GPIO tolerance to a GPIO.

## Buzzer channel

Do not connect a high-current or inductive buzzer directly to a Pi GPIO. Use:

```text
Pi GPIO26 -- gate/base resistor --> N-MOSFET or NPN driver
External buzzer supply ---------> buzzer ---------> driver ---------> supply ground
Pi GND -------------------------- common ground
```

Add a flyback diode if the buzzer/driver is inductive, observing the buzzer manufacturer's polarity and frequency requirements. A passive piezo may need an AC/PWM drive waveform rather than a static enable. Adapt the driver and firmware to the selected part.

## Observation path

Preferred options, in order of independence:

1. Calibrated microphone or sound-level sensor sampled by a separate measurement device.
2. Arduino/ADC bridge with a conditioned digital feedback signal on Pi GPIO21 and analog LED sense channels.
3. Electrical feedback from the buzzer driver, only if it measures the intended physical behavior.

The observation input must be 3.3 V-safe. If a sensor produces 5 V logic, use a level shifter or divider designed for the signal. Do not connect a raw analog sensor output to a Pi GPIO.

## Arduino bridge

The included sketch assumes an Arduino-compatible board with A0-A2 analog inputs and a 3.3 V-safe digital buzzer feedback input on D2. The Pi and bridge share ground. If the board uses 5 V logic, level-shift the feedback line and confirm ADC reference voltage. The sketch reports raw ADC counts; calibration coefficients belong in the contract or host software.

## Safety checklist

- Power off before changing wiring.
- Confirm GPIO numbering is BCM, not physical header numbering.
- Confirm LED current limiting on all channels.
- Confirm buzzer supply current and voltage independently of the Pi.
- Confirm driver gates/bases cannot float at boot; add pull-downs as needed.
- Configure a safe default: all LEDs off and buzzer disabled.
- Validate reset after every run and on process termination.
- Define prohibited combinations and maximum run time in the contract.

