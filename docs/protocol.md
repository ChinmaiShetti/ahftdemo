# JSON line protocol

## Command

```json
{
  "campaign_id": "CC-001",
  "batch_id": 1,
  "experiment_id": "e-0001",
  "command": "RUN_INTERACTION_TEST",
  "parameters": {"led1_value": 120, "led2_value": 180, "led3_value": 90}
}
```

All three parameters are integers in the reviewed contract range. They represent PWM duty-cycle values unless the contract explicitly says otherwise.

## Result

```json
{
  "campaign_id": "CC-001",
  "batch_id": 1,
  "experiment_id": "e-0001",
  "status": "COMPLETED",
  "requested_parameters": {"led1_value": 120, "led2_value": 180, "led3_value": 90},
  "applied_parameters": {"led1_value": 120, "led2_value": 180, "led3_value": 90},
  "measurements": {"buzzer_detected": true, "led1_voltage_v": null},
  "outcome": "PASS",
  "measurement_quality": "VALID",
  "diagnostics": {"backend": "digital_feedback", "error": null}
}
```

`FAIL` means a valid observation violated the reviewed output requirement. `INVALID` means the observation cannot support a conclusion. `ABORTED` means execution was stopped. Rejected commands have no applied parameters and must not be included as experiments.

