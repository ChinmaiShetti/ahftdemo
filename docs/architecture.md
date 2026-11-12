# Architecture

```mermaid
flowchart LR
  Planner[ChipCheck planner] -->|JSON command| Exec[Pi hardware executor]
  Exec --> Validate[Contract + safety validation]
  Validate --> Apply[Apply PWM + buzzer stimulus]
  Apply --> Settle[Settling interval]
  Settle --> Observe[Independent observation]
  Observe --> Result[JSON result]
  Result --> Planner
  Apply --> LEDs[LED1 / LED2 / LED3 drivers]
  Apply --> Buzzer[Buzzer driver]
  Observe --> Sensor[Mic, feedback, or ADC bridge]
```

The Pi executor is a boundary component. It owns hardware timing, reset, range validation, and measurement quality. The planner owns search strategy, duplicate avoidance, budget allocation, and failure-region inference.

