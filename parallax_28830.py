"""Minimal Python driver for the Parallax Propeller Servo Controller USB (#28830)."""

from __future__ import annotations

from typing import Optional


class Parallax28830:
    """Driver for the Parallax Propeller Servo Controller USB (#28830)."""

    CHANNEL_COUNT = 16
    MIN_PULSE = 1
    MAX_PULSE = 1024
    MIN_SPEED = 0
    MAX_SPEED = 63

    def __init__(
        self,
        port: Optional[str] = None,
        *,
        baudrate: int = 2400,
        timeout: float = 1.0,
        transport=None,
    ) -> None:
        if transport is not None:
            self._transport = transport
        else:
            if port is None:
                raise ValueError("'port' is required when no transport is provided")
            try:
                import serial  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise ImportError("pyserial is required when using a real serial port") from exc
            self._transport = serial.Serial(port, baudrate=baudrate, timeout=timeout)

        self._speed = [0] * self.CHANNEL_COUNT

    def close(self) -> None:
        self._transport.close()

    def set_speed(self, channel: int, speed: int) -> None:
        self._check_channel(channel)
        if not self.MIN_SPEED <= speed <= self.MAX_SPEED:
            raise ValueError(f"speed must be in range {self.MIN_SPEED}-{self.MAX_SPEED}")
        self._speed[channel] = speed

    def set_position(self, channel: int, pulse: int) -> None:
        self._check_channel(channel)
        if not self.MIN_PULSE <= pulse <= self.MAX_PULSE:
            raise ValueError(f"pulse must be in range {self.MIN_PULSE}-{self.MAX_PULSE}")

        low = pulse & 0xFF
        high = (pulse >> 8) & 0xFF
        self._write(b"!SC" + bytes([channel, self._speed[channel], low, high]) + b"\r")

    def get_position(self, channel: int) -> int:
        """Read current pulse width for a channel."""
        self._check_channel(channel)
        self._write(b"!SCRSP" + bytes([channel]) + b"\r")
        response = self._read_exact(3)
        read_channel, first, second = response
        if read_channel != channel:
            raise RuntimeError(f"response channel mismatch: expected {channel}, got {read_channel}")

        # Position writes use low-byte then high-byte. Prefer that ordering for reads,
        # but accept the alternate ordering when it is the only valid pulse value.
        high_first = (first << 8) | second
        low_first = (second << 8) | first
        if self.MIN_PULSE <= low_first <= self.MAX_PULSE:
            return low_first
        if self.MIN_PULSE <= high_first <= self.MAX_PULSE:
            return high_first
        raise RuntimeError(f"invalid pulse value in response: {response!r}")

    def disable(self, channel: int) -> None:
        self._check_channel(channel)
        self._write(b"!SCPSD" + bytes([channel]) + b"\r")

    def enable(self, channel: int) -> None:
        self._check_channel(channel)
        self._write(b"!SCPSE" + bytes([channel]) + b"\r")

    def set_default_position(self, channel: int, pulse: int) -> None:
        self._check_channel(channel)
        if not self.MIN_PULSE <= pulse <= self.MAX_PULSE:
            raise ValueError(f"pulse must be in range {self.MIN_PULSE}-{self.MAX_PULSE}")

        low = pulse & 0xFF
        high = (pulse >> 8) & 0xFF
        self._write(b"!SCD" + bytes([channel, low, high]) + b"\r")

    def set_startup_mode(self, mode: int) -> int:
        """Set startup mode and validate 3-byte protocol ACK (DL/PM/BR + mode byte)."""
        if mode not in (0, 1):
            raise ValueError("mode must be 0 (center) or 1 (EEPROM defaults)")
        self._write(b"!SCEDD" + bytes([mode]) + b"\r")
        response = self._read_exact(3)
        # Startup mode acknowledgements observed as: b"DL", b"PM", or b"BR" + mode byte.
        if response[:2] not in (b"DL", b"PM", b"BR"):
            raise RuntimeError(f"unexpected startup mode response: {response!r}")
        if response[2] != mode:
            raise RuntimeError(f"startup mode mismatch: expected {mode}, got {response[2]}")
        return response[2]

    def get_version(self) -> str:
        self._write(b"!SCVER?\r")
        return self._read_text_response(default_length=3)

    def clear_eeprom(self) -> str:
        self._write(b"!SCLEAR\r")
        return self._read_text_response(default_length=3)

    def _check_channel(self, channel: int) -> None:
        if not 0 <= channel < self.CHANNEL_COUNT:
            raise ValueError(f"channel must be in range 0-{self.CHANNEL_COUNT - 1}")

    def _write(self, data: bytes) -> None:
        self._transport.write(data)

    def _read_exact(self, length: int) -> bytes:
        data = self._transport.read(length)
        if len(data) != length:
            raise RuntimeError(f"expected {length} bytes, got {len(data)}")
        return data

    def _read_text_response(self, default_length: int) -> str:
        if hasattr(self._transport, "read_until"):
            data = self._transport.read_until(b"\r")
            if data:
                return data.rstrip(b"\r").decode("ascii")
        return self._read_exact(default_length).decode("ascii")
