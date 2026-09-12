"""Parallax 28830 --- Propeller Servo Controller (PSCU) helper

Provides `Parallax28830`, a small, practical wrapper to control the
Parallax Propeller Servo Controller USB (#28830 / "PSCU") over a serial
interface (USB or TTL). It supports a simple helper (`set_servo`) that
accepts a 0..1000 position value and the full PSCU ASCII command set
documented in the 28830 datasheet.

Key features:
- open/close serial port and raw writes (`send_raw`)
- PSCU commands: `position_command`, `get_version` (VER?),
	`set_baud_rate` (SBR), `report_servo` (RSP), `set_port_mode` (PSS),
	`disable_servo` (PSD), `enable_servo` (PSE), `set_startup_mode` (EDD),
	`set_default_position` (SCD), `clear_eeprom` (CLEAR)

Notes:
- Default serial baud is 2400 bps (PSCU default). Use `set_baud_rate`
	to switch to 38400 bps when needed.
- All PSCU ASCII commands are framed as described in the datasheet
	(preamble `!SC`, parameters, trailing carriage return `\r`).
- `pyserial` is required at runtime (install with `pip install pyserial`).

Minimal usage:
    ctrl = Parallax28830('/dev/ttyUSB0')
    with ctrl:
        # set servo with a 0..1000 position (500 ≈ mid)
        ctrl.set_servo(0, 500)

        # PSCU position command with ramp (position 0..1000)
        ctrl.position_command(0, ramp=7, position=500)
"""

from typing import Optional

try:
	import serial
except Exception:  # Keep import-time failure readable for users
	serial = None

# Default pulse width range (microseconds) used when translating a
# 0..1000 position value into an absolute pulse width for PSCU commands.
# Adjust these constants to match your servo travel if necessary.
MIN_PULSE_US = 500
MAX_PULSE_US = 2500


class Parallax28830:
	"""Serial helper for Parallax 28830 servo controller.

	Public methods:
	- open(), close()
	- send_raw(bytes)
	- set_servo(channel, position)
	- __enter__/__exit__ for context manager usage
	"""

	def __init__(self, port: str, baud: int = 2400, timeout: float = 1.0):
		self.port = port
		self.baud = baud
		self.timeout = timeout
		self._serial: Optional[serial.Serial] = None

	def open(self) -> None:
		"""Open the serial port if not already open.

		Raises:
			RuntimeError if `pyserial` is not installed.
		"""
		if serial is None:
			raise RuntimeError("pyserial is required: pip install pyserial")
		if self._serial and getattr(self._serial, "is_open", False):
			return
		self._serial = serial.Serial(self.port, self.baud, timeout=self.timeout)

	def close(self) -> None:
		"""Close the serial port (if open)."""
		if self._serial:
			try:
				self._serial.close()
			finally:
				self._serial = None

	def send_raw(self, data: bytes) -> None:
		"""Write raw bytes to the controller, ensuring the port is open."""
		if serial is None:
			raise RuntimeError("pyserial is required: pip install pyserial")
		if not (self._serial and getattr(self._serial, "is_open", False)):
			self.open()
		# write and flush
		self._serial.write(data)
		try:
			self._serial.flush()
		except Exception:
			# not all Serial backends implement flush
			pass

	def set_servo(self, channel: int, position: int) -> None:
		"""Set a servo channel using a 0..1000 position value.

		Parameters:
		- channel: servo channel number (0-31)
		- position: integer 0..1000 representing the servo position; this is
		  linearly mapped to the range defined by `MIN_PULSE_US`..`MAX_PULSE_US`.

		This sends a PSCU Position command with the computed pulse width and
		 a default ramp of 0. Use `position_command()` to provide a custom ramp.
		"""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		if not (0 <= position <= 1000):
			raise ValueError("position must be between 0 and 1000")
		self.position_command(channel, ramp=0, position=position)

	# --- PSCU command set (per 28830 datasheet) ---

	def _read_until_cr(self, timeout: Optional[float] = None) -> bytes:
		"""Read from serial until a carriage return is received or timeout."""
		if not (self._serial and getattr(self._serial, "is_open", False)):
			self.open()
		if timeout is not None:
			old = self._serial.timeout
			self._serial.timeout = timeout
		try:
			# pyserial provides read_until
			return self._serial.read_until(b"\r")
		finally:
			if timeout is not None:
				self._serial.timeout = old

	def _pw_to_bytes(self, pulse_us: int) -> tuple[int, int]:
		"""Convert pulse width in microseconds to (lowbyte, highbyte) in 2µs units."""
		units = int(pulse_us // 2)
		low = units & 0xFF
		high = (units >> 8) & 0xFF
		return low, high

	def _position_to_pulse(self, position: int) -> int:
		"""Map a 0..1000 position value to an absolute pulse width in µs.

		Linear mapping: MIN_PULSE_US -> 0, MAX_PULSE_US -> 1000.
		"""
		# clamp just in case
		if position <= 0:
			return MIN_PULSE_US
		if position >= 1000:
			return MAX_PULSE_US
		span = MAX_PULSE_US - MIN_PULSE_US
		pulse = MIN_PULSE_US + int((position * span) / 1000)
		return pulse

	def position_command(self, channel: int, ramp: int, position: int) -> None:
		"""Send Position Command: !SC <channel> <ramp> <lowbyte> <highbyte> <CR>

		channel: 0-31, ramp: 0-63, position: integer 0-1000 which is mapped to
		the configured `MIN_PULSE_US`..`MAX_PULSE_US` pulse width range.
		"""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		if not (0 <= ramp <= 63):
			raise ValueError("ramp must be between 0 and 63")
		if not (0 <= position <= 1000):
			raise ValueError("position must be between 0 and 1000")
		pulse_us = self._position_to_pulse(position)
		low, high = self._pw_to_bytes(pulse_us)
		packet = b"!SC" + bytes([int(channel), int(ramp), low, high]) + b"\r"
		self.send_raw(packet)

	def get_version(self) -> str:
		"""Send VER? command and return firmware version string (without CR)."""
		self.send_raw(b"!SCVER?\r")
		resp = self._read_until_cr(self.timeout)
		try:
			return resp.rstrip(b"\r\n").decode("utf-8", errors="ignore")
		except Exception:
			return resp.decode(errors="ignore")

	def set_baud_rate(self, mode: int) -> bytes:
		"""Send SBR command to set device baud. mode=0 -> 2400, mode=1 -> 38400.

		This will attempt to update the local serial port baudrate after sending
		the command so the reply (which may be sent at the new rate) can be read.
		Returns the raw reply bytes (if any).
		"""
		if mode not in (0, 1):
			raise ValueError("mode must be 0 (2400) or 1 (38400)")
		self.send_raw(b"!SCSBR" + bytes([mode]) + b"\r")
		# adjust local baud to match device
		new_baud = 38400 if mode == 1 else 2400
		if self._serial:
			try:
				self._serial.baudrate = new_baud
			except Exception:
				pass
		# try to read a short reply
		resp = self._read_until_cr(0.5)
		return resp

	def report_servo(self, channel: int) -> int:
		"""Send RSP and return the last set pulse width in microseconds."""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		self.send_raw(b"!SCRSP" + bytes([channel]) + b"\r")
		# device replies: <channel> <highbyte> <lowbyte>
		if not (self._serial and getattr(self._serial, "is_open", False)):
			self.open()
		resp = self._serial.read(3)
		if len(resp) < 3:
			raise IOError("Incomplete RSP reply")
		ch, high, low = resp[0], resp[1], resp[2]
		units = (high << 8) | low
		return units * 2

	def set_port_mode(self, mode: int) -> bytes:
		"""Send PSS to set port (0 -> channels 0-15, 1 -> 16-31). Returns reply."""
		if mode not in (0, 1):
			raise ValueError("mode must be 0 or 1")
		self.send_raw(b"!SCPSS" + bytes([mode]) + b"\r")
		return self._read_until_cr(self.timeout)

	def disable_servo(self, channel: int) -> None:
		"""Send PSD to disable a servo channel (stops pulses)."""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		self.send_raw(b"!SCPSD" + bytes([channel]) + b"\r")

	def enable_servo(self, channel: int) -> None:
		"""Send PSE to enable a previously disabled servo channel."""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		self.send_raw(b"!SCPSE" + bytes([channel]) + b"\r")

	def set_startup_mode(self, mode: int) -> bytes:
		"""Send EDD to set startup servo mode. mode=0 center, mode=1 use EEPROM defaults."""
		if mode not in (0, 1):
			raise ValueError("mode must be 0 or 1")
		self.send_raw(b"!SCEDD" + bytes([mode]) + b"\r")
		return self._read_until_cr(self.timeout)

	def set_default_position(self, channel: int, position: int) -> None:
		"""Send Default Position command (SCD) to store startup pos in EEPROM.

		Parameters:
		- channel: 0-31
		- position: 0..1000 mapped linearly to MIN_PULSE_US..MAX_PULSE_US
		"""
		if not (0 <= channel <= 31):
			raise ValueError("channel must be between 0 and 31")
		if not (0 <= position <= 1000):
			raise ValueError("position must be between 0 and 1000")
		pulse_us = self._position_to_pulse(position)
		low, high = self._pw_to_bytes(pulse_us)
		self.send_raw(b"!SCD" + bytes([channel, low, high]) + b"\r")

	def clear_eeprom(self) -> bytes:
		"""Send CLEAR command to clear upper EEPROM. Returns reply bytes."""
		self.send_raw(b"!SCLEAR\r")
		return self._read_until_cr(self.timeout)

	def __enter__(self):
		self.open()
		return self

	def __exit__(self, exc_type, exc, tb):
		self.close()


__all__ = ["Parallax28830"]

