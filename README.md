# Parallax-28830

Minimal Python driver for the **Parallax Propeller Servo Controller USB (#28830)**.

## Requirements

- Python 3.9+
- `pyserial` (for real hardware access)

## Usage

```python
from parallax_28830 import Parallax28830

driver = Parallax28830(port="/dev/ttyUSB0")
driver.set_speed(0, 10)
driver.set_position(0, 500)
print(driver.get_position(0))
print(driver.get_version())
driver.close()
```

## Run tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```
