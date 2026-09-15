# YOLOE ESP32 Real-Time Pan-Tilt Tracker

Real-time object tracking with a laptop webcam, YOLOE visual prompting, and a two-servo pan/tilt mechanism controlled by an ESP32 over USB serial.

The project includes reference images for a yellow ball and a wheel, a Windows desktop interface, serial communication with acknowledgements, adjustable tracking speed/gain, manual pan/tilt positioning, and ESP32 firmware for GPIO 18/19 servo control.

## What this build does

- Detects a selected reference target with YOLOE.
- Continuously tracks the target in the camera feed.
- Sends pan and tilt targets together to the ESP32.
- Starts tracking from the servo's current/manual position rather than forcing a centre jump.
- Holds the last position when the target is temporarily lost.
- Provides manual Pan/Tilt controls, centre control, reverse-axis options, and tracking adjustments.
- Uses a paced serial handshake to avoid ESP32 reset/boot garbage corrupting commands.

## Hardware

- ESP32 DevKit / ESP32-WROOM
- 2 positional servos: one for pan, one for tilt
- External regulated servo power supply suitable for the servos
- USB data cable from ESP32 to PC
- Laptop/USB webcam

### Wiring

| Connection | ESP32 / Supply |
|---|---|
| Pan servo signal | GPIO 18 |
| Tilt servo signal | GPIO 19 |
| Servo + | External regulated servo supply + |
| Servo GND | External supply GND |
| ESP32 GND | Same external supply GND |
| ESP32 USB | Laptop/PC |

Important: do **not** power the servos from ESP32 3.3 V. Use a suitable external servo supply and keep all grounds common.

## ESP32 firmware setup

1. Install Arduino IDE.
2. Install the Espressif ESP32 board package.
3. Install the `ESP32Servo` library.
4. Open `ESP32_Studio/ESP32_Studio.ino`.
5. Select the correct ESP32 board and COM port.
6. Upload the sketch.
7. Close Arduino Serial Monitor before opening the desktop app.

Serial settings used by both sides:

```text
115200 baud
Pan: GPIO18
Tilt: GPIO19
PWM range: 900-2100 us
Neutral: 1500 us
Servo frequency: 50 Hz
```

## Windows software setup

Recommended: Python 3.11 or 3.12.

### Easiest method

Run:

```bat
START.bat
```

The script creates/uses the project environment and installs required Python packages when needed.

### Manual method

```bash
python -m venv .venv-yolo
.venv-yolo\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python download_model.py
python studio.py
```

The first model setup requires internet access. Later launches reuse the local model.

## How to use

1. Power the two servos from the external supply.
2. Connect the ESP32 to the PC by USB.
3. Upload the included ESP32 firmware if you have not already done so.
4. Close Arduino Serial Monitor.
5. Run `START.bat`.
6. Select the ESP32 COM port and click **Connect**.
7. Wait for firmware confirmation.
8. Test `Pan -`, `Pan +`, `Tilt -`, and `Tilt +`.
9. Manually place the pan/tilt mechanism at the starting position you want.
10. Choose the target: **Ball** or **Wheel**.
11. Click **Start following**.
12. Move the target in front of the camera. A confirmed detection is shown with a green box.

Tracking begins from the current commanded servo position. It should not automatically jump back to 1500/1500 when you start following.

## Real-time tracking behaviour

- The camera capture runs separately from inference so old frames can be discarded.
- The application sends both servo targets in one packet.
- Acknowledged commands keep the software's internal servo state aligned with the ESP32.
- If the target disappears, the last commanded servo position is held.
- When the target reappears, the application reacquires it and continues tracking.
- The actual response speed depends on inference FPS, servo specifications, power supply, mechanical load, and linkage.

## Tracking controls

Start around these values before tuning:

- Tracking speed/gain: moderate (`2x-3x` where available in the UI)
- Servo centre: 1500 us
- Pan software working range: approximately 1100-1900 us
- Tilt software working range: approximately 1200-1800 us

If an axis moves the wrong way, use **Reverse pan** or **Reverse tilt** rather than rewiring the control logic.

Do not extend servo endpoints until you have verified the mechanism can move safely without binding.

## Serial protocol

PC to ESP32:

```text
HELLO
H
P,<sequence>,<pan_us>,<tilt_us>
```

Example:

```text
P,12,1475,1560
```

ESP32 acknowledgement:

```text
ACK,12,1475,1560
```

Handshake response:

```text
PTSTUDIO,1
```

The transport layer waits for ESP32 auto-reset, clears stale input, and then performs the handshake. The firmware also ignores non-printable boot/reset noise and can resynchronise on valid packets.

## Troubleshooting

### App connects but says no commands acknowledged

- Close Arduino Serial Monitor/Plotter.
- Confirm both the desktop app and ESP32 firmware use 115200 baud.
- Upload the included `ESP32_Studio.ino` again.
- Disconnect/reconnect the USB cable and retry.

### Detection works but servos do not move

- Use the manual motor buttons first.
- Check that the app is receiving `ACK,...` responses.
- Verify GPIO18 and GPIO19 signal wiring.
- Verify external servo power.
- Verify ESP32 GND and servo-supply GND are connected together.

### Servo moves in the wrong direction

Use the Reverse Pan / Reverse Tilt options in the app.

### Tracking feels delayed

- Confirm the app is processing recent frames rather than stale frames.
- Close other heavy GPU/CPU applications.
- Use NVIDIA acceleration when available.
- Reduce camera load if necessary.
- Do not set tracking gain excessively high; that can cause overshoot instead of true speed improvement.

### Camera does not open

Close software that may already be using the webcam and try another camera index.

### Target is not detected

- Make sure the selected target is visible and reasonably large in the frame.
- Avoid severe motion blur or overexposure.
- Use only one visually similar copy of the target when testing.

## Project structure

```text
ESP32_Studio/
  ESP32_Studio.ino       ESP32 servo + serial firmware
references/
  ball_front.jpg         visual prompt/reference
  ball_back.jpg          visual prompt/reference
  wheel.jpg              visual prompt/reference
  prompt.jpg/json        prepared prompt data
  targets.json           target metadata
studio.py                desktop interface and tracking control
detector.py              detector integration
vision.py                camera/vision logic
transport.py             serial transport and ESP32 handshake
download_model.py        model download/verification helper
setup_dependencies.py    dependency setup helper
CHECK_SOFTWARE.py        environment/software checks
requirements.txt         Python dependencies
START.bat                Windows launcher
START_HERE.txt           detailed original quick-start notes
VALIDATION.txt           validation notes and limitations
```

## Python dependencies

Main packages are pinned/listed in `requirements.txt`:

- Ultralytics
- OpenCV
- NumPy
- Pillow
- pyserial

## Safety and limitations

This is a prototype vision/servo control project, not a calibrated safety-critical positioning system. PWM commands represent requested servo targets; acknowledgements confirm that the ESP32 accepted the command, not that a physical shaft-position sensor verified the final angle.

Disconnect servo power before making mechanical adjustments. Never force a servo against a mechanical stop.

## References

- Ultralytics YOLOE documentation: https://docs.ultralytics.com/models/yoloe
- PyTorch installation guidance: https://pytorch.org/get-started/
- ESP32Servo: https://github.com/madhephaestus/ESP32Servo

## License

See `LICENSE` and `THIRD_PARTY.txt` for licensing and third-party notices.
