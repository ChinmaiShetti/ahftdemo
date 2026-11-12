// ChipCheck optional measurement bridge.
// Protocol: Pi sends "MEASURE\n"; bridge replies one JSON object and newline.
// A0/A1/A2 are conditioned LED sense inputs. D2 is a 3.3 V-safe buzzer feedback input.
const int LED1_SENSE = A0;
const int LED2_SENSE = A1;
const int LED3_SENSE = A2;
const int BUZZER_FEEDBACK = 2;

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_FEEDBACK, INPUT);
}

void loop() {
  if (!Serial.available()) return;
  String command = Serial.readStringUntil('\n');
  command.trim();
  if (command == "MEASURE") {
    int a0 = analogRead(LED1_SENSE);
    int a1 = analogRead(LED2_SENSE);
    int a2 = analogRead(LED3_SENSE);
    int feedback = digitalRead(BUZZER_FEEDBACK);
    Serial.print("{\"led1_adc\":"); Serial.print(a0);
    Serial.print(",\"led2_adc\":"); Serial.print(a1);
    Serial.print(",\"led3_adc\":"); Serial.print(a2);
    Serial.print(",\"buzzer_feedback\":"); Serial.print(feedback ? "true" : "false");
    Serial.println("}");
  } else if (command == "PING") {
    Serial.println("{\"ok\":true,\"device\":\"chipcheck_measurement_bridge\"}");
  }
}

