"""Reliable versioned serial link for PanTilt Studio.

The ESP32 is reset by many USB-serial adapters when a Windows COM port is opened.
This module deliberately waits for that reset to finish and resynchronises the
line-oriented protocol before sending the HELLO handshake.
"""
import time
import serial


class Link:
    BAUD = 115200
    BOOT_WAIT = 2.0
    HANDSHAKE_TIMEOUT = 6.0

    def __init__(self):
        self.port = None
        self.sequence = 0
        self.last_sent = 0.0
        self.last_ack = 0.0
        self.pending_since = None
        self.buffer = bytearray()
        self.ack = None
        self.sent = {}

    def connect(self, name):
        self.close(send_hold=False)
        if not name:
            raise RuntimeError('Select an ESP32 COM port first.')

        try:
            self.port = serial.Serial(
                port=name,
                baudrate=self.BAUD,
                timeout=0.20,
                write_timeout=0.50,
                rtscts=False,
                dsrdtr=False,
            )

            time.sleep(self.BOOT_WAIT)
            self.port.write(b'\n')
            self.port.flush()
            time.sleep(0.08)
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()

            deadline = time.monotonic() + self.HANDSHAKE_TIMEOUT
            next_hello = 0.0
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_hello:
                    self.port.write(b'HELLO\n')
                    self.port.flush()
                    next_hello = now + 0.50

                raw = self.port.readline()
                if not raw:
                    continue
                line = raw.decode('ascii', errors='ignore').strip()
                if line == 'PTSTUDIO,1':
                    self.port.timeout = 0
                    self.last_ack = time.monotonic()
                    self.sequence = 0
                    self.pending_since = None
                    self.buffer = bytearray()
                    self.sent = {}
                    self.ack = None
                    return

            raise RuntimeError(
                'ESP32 did not identify itself. Upload the included '
                'ESP32_Studio.ino, use 115200 baud, close Serial Monitor, '
                'then reconnect.'
            )
        except Exception:
            self.close(send_hold=False)
            raise

    def poll(self):
        if self.port is None:
            return
        try:
            waiting = self.port.in_waiting
            if waiting:
                self.buffer.extend(self.port.read(min(waiting, 4096)))
        except (OSError, serial.SerialException) as exc:
            raise RuntimeError('Serial connection was lost: ' + str(exc)) from exc

        if len(self.buffer) > 8192:
            raise RuntimeError('Unexpected serial data. Check the uploaded sketch.')

        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            line = line.decode('ascii', errors='ignore').strip()
            if not line:
                continue

            if line.startswith('ERR,'):
                raise RuntimeError('ESP32 rejected a command: ' + line)

            parts = line.split(',')
            if len(parts) == 4 and parts[0] == 'ACK':
                try:
                    seq, p, t = map(int, parts[1:])
                except ValueError:
                    continue
                if self.sent.get(seq) == (p, t):
                    self.ack = (p, t)
                    self.last_ack = time.monotonic()
                    for key in list(self.sent):
                        if key <= seq:
                            del self.sent[key]
                    self.pending_since = None

        if (self.pending_since is not None and
                time.monotonic() - max(self.pending_since, self.last_ack) > 1.0):
            raise RuntimeError('ESP32 stopped acknowledging commands. Reconnect before continuing.')

    def send(self, pan, tilt, force=False):
        """Send a servo target and return True only when a packet was actually written."""
        if self.port is None:
            return False
        pan, tilt = round(pan), round(tilt)
        if not (900 <= pan <= 2100 and 900 <= tilt <= 2100):
            raise ValueError('Servo pulse outside firmware limits')
        now = time.monotonic()
        if not force and now - self.last_sent < .012:
            return False
        self.sequence += 1
        try:
            self.port.write(f'P,{self.sequence},{pan},{tilt}\n'.encode('ascii'))
        except (OSError, serial.SerialException) as exc:
            raise RuntimeError('Could not send servo command: ' + str(exc)) from exc
        self.sent[self.sequence] = (pan, tilt)
        if self.pending_since is None:
            self.pending_since = now
        self.last_sent = now
        if len(self.sent) > 100:
            raise RuntimeError('ESP32 command acknowledgement backlog')
        return True

    def hold(self):
        if self.port is not None:
            try:
                self.port.write(b'H\n')
            except (OSError, serial.SerialException) as exc:
                raise RuntimeError('Could not send hold command: ' + str(exc)) from exc

    def close(self, send_hold=True):
        port = self.port
        self.port = None
        if port is not None:
            if send_hold:
                try:
                    if port.is_open:
                        port.write(b'H\n')
                        port.flush()
                except (OSError, serial.SerialException):
                    pass
            try:
                port.close()
            except (OSError, serial.SerialException):
                pass
        self.pending_since = None
        self.sent = {}
        self.buffer = bytearray()
        self.ack = None


def map_position(point, size, endpoints, reverse_pan=False, reverse_tilt=False, gain=1.0):
    x, y = point
    w, h = size
    nx = max(0, min(1, .5 + (x / max(1, w - 1) - .5) * gain))
    ny = max(0, min(1, .5 + (y / max(1, h - 1) - .5) * gain))
    if reverse_pan:
        nx = 1 - nx
    if reverse_tilt:
        ny = 1 - ny
    left, right, top, bottom = endpoints
    return round(left + (right - left) * nx), round(top + (bottom - top) * ny)


def track_relative(current, point, size, endpoints, reverse_pan=False, reverse_tilt=False, gain=1.0, speed=2.5):
    """Move from the CURRENT servo command using camera-centre error."""
    pan, tilt = current
    x, y = point
    w, h = size
    left, right, top, bottom = endpoints

    ex = (x - (w - 1) / 2) / max(1.0, (w - 1) / 2)
    ey = (y - (h - 1) / 2) / max(1.0, (h - 1) / 2)

    dead = 0.045
    if abs(ex) < dead:
        ex = 0.0
    if abs(ey) < dead:
        ey = 0.0

    if reverse_pan:
        ex = -ex
    if reverse_tilt:
        ey = -ey

    max_step = 18.0 * max(0.5, min(5.0, float(speed)))
    pan_step = ex * max_step * max(0.5, min(2.0, float(gain)))
    tilt_step = ey * max_step * max(0.5, min(2.0, float(gain)))

    lo_pan, hi_pan = sorted((left, right))
    lo_tilt, hi_tilt = sorted((top, bottom))
    pan = round(max(lo_pan, min(hi_pan, pan + pan_step)))
    tilt = round(max(lo_tilt, min(hi_tilt, tilt + tilt_step)))
    return pan, tilt
