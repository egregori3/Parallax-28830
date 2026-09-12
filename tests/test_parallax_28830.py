import unittest

from parallax_28830 import Parallax28830


class FakeTransport:
    def __init__(self, reads=None):
        self.writes = []
        self._reads = list(reads or [])

    def write(self, data: bytes):
        self.writes.append(data)

    def read(self, length: int) -> bytes:
        if not self._reads:
            return b""
        return self._reads.pop(0)

    def close(self):
        pass


class Parallax28830Tests(unittest.TestCase):
    def test_set_position_writes_expected_packet(self):
        transport = FakeTransport()
        driver = Parallax28830(transport=transport)

        driver.set_speed(2, 5)
        driver.set_position(2, 500)

        self.assertEqual(transport.writes[-1], b"!SC" + bytes([2, 5, 244, 1]) + b"\r")

    def test_get_position_parses_response(self):
        transport = FakeTransport(reads=[bytes([3, 1, 244])])
        driver = Parallax28830(transport=transport)

        position = driver.get_position(3)

        self.assertEqual(transport.writes[-1], b"!SCRSP" + bytes([3]) + b"\r")
        self.assertEqual(position, 500)

    def test_enable_disable_packets(self):
        transport = FakeTransport()
        driver = Parallax28830(transport=transport)

        driver.disable(7)
        driver.enable(7)

        self.assertEqual(transport.writes[0], b"!SCPSD" + bytes([7]) + b"\r")
        self.assertEqual(transport.writes[1], b"!SCPSE" + bytes([7]) + b"\r")

    def test_get_version(self):
        transport = FakeTransport(reads=[b"1.2"])
        driver = Parallax28830(transport=transport)

        version = driver.get_version()

        self.assertEqual(transport.writes[-1], b"!SCVER?\r")
        self.assertEqual(version, "1.2")

    def test_invalid_input_raises(self):
        transport = FakeTransport()
        driver = Parallax28830(transport=transport)

        with self.assertRaises(ValueError):
            driver.set_speed(0, 64)
        with self.assertRaises(ValueError):
            driver.set_position(16, 500)
        with self.assertRaises(ValueError):
            driver.set_position(0, 0)


if __name__ == "__main__":
    unittest.main()
