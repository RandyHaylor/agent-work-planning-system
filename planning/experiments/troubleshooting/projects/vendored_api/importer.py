from pathlib import Path

from vendor import tinycsv

DATA = Path(__file__).parent / "data" / "readings.csv"


def load_readings(path=DATA):
    rows = tinycsv.read_rows(Path(path).read_text())
    return [(name, int(value)) for name, value in rows]


def total(readings):
    return sum(v for _, v in readings)
