import random
import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

BASE_URL = "http://127.0.0.1:8000"


class Direction(Enum):
    UP = "ВВЕРХ"
    DOWN = "ВНИЗ"
    LEFT = "ВЛЕВО"
    RIGHT = "ВПРАВО"
    UNKNOWN = "НЕИЗВЕСТНО"


class PressureStatus(Enum):
    NORMAL = "НОРМА"
    LEAK = "УТЕЧКА"
    HIGH = "ВЫСОКОЕ"


@dataclass
class PipePoint:
    x: int
    y: int

    def __str__(self):
        return f"({self.x},{self.y})"

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return isinstance(other, PipePoint) and self.x == other.x and self.y == other.y


class PressureSensor:
    def __init__(self, leak_probability: float = 0.45):
        self.leak_probability = leak_probability
        self.calibration_data: Optional[Tuple[float, float]] = None

    def calibrate(self, normal_range: Tuple[float, float]) -> None:
        self.calibration_data = normal_range
        print(f"Датчик давления откалиброван: норма {normal_range[0]}-{normal_range[1]} бар")

    def read_pressure(self) -> float:
        if not self.calibration_data:
            raise ValueError("Датчик не откалиброван!")
        low, high = self.calibration_data
        if random.random() < self.leak_probability:
            return round(random.uniform(10.0, low - 5), 1)  # утечка
        else:
            return round(random.uniform(low, high + 30), 1)

    def get_pressure_status(self, pressure: float) -> PressureStatus:
        if not self.calibration_data:
            raise ValueError("Датчик не откалиброван!")
        low, _ = self.calibration_data
        if pressure < low - 5:
            return PressureStatus.LEAK
        elif pressure > 150:
            return PressureStatus.HIGH
        else:
            return PressureStatus.NORMAL


class Crawler:
    def __init__(self):
        self.current_position: Optional[PipePoint] = None

    def move_to(self, target: PipePoint, session_id: int) -> Direction:
        if self.current_position is None:
            direction = Direction.UNKNOWN
            self.current_position = target
        else:
            direction = self._get_direction(self.current_position, target)
            self.current_position = target

        # логируем координаты
        requests.post(f"{BASE_URL}/sessions/{session_id}/sensors",
                      json={"sensor_type": "position_x", "value": float(target.x), "unit": "cell"})
        requests.post(f"{BASE_URL}/sessions/{session_id}/sensors",
                      json={"sensor_type": "position_y", "value": float(target.y), "unit": "cell"})

        # команда движения
        requests.post(f"{BASE_URL}/sessions/{session_id}/actuators",
                      json={"actuator_type": "movement", "command": 1.0,
                            "status": f"{direction.value} → {target}"})

        if direction != Direction.UNKNOWN:
            requests.post(f"{BASE_URL}/sessions/{session_id}/actuators",
                          json={"actuator_type": f"dir_{direction.name.lower()}",
                                "command": 1.0, "status": "executed"})

        print(f"Перемещение: {direction.value} → {target}")
        return direction

    def _get_direction(self, fr: PipePoint, to: PipePoint) -> Direction:
        dx = to.x - fr.x
        dy = to.y - fr.y
        if dx == 1 and dy == 0: return Direction.RIGHT
        if dx == -1 and dy == 0: return Direction.LEFT
        if dy == 1 and dx == 0: return Direction.DOWN
        if dy == -1 and dx == 0: return Direction.UP
        return Direction.UNKNOWN


class PipeMap:
    def __init__(self, map_data: List[List[str]]):
        self.map_data = map_data
        self.width = len(map_data[0]) if map_data else 0
        self.height = len(map_data)

    def is_pipe_point(self, p: PipePoint) -> bool:
        return (0 <= p.x < self.width and 0 <= p.y < self.height and self.map_data[p.y][p.x] == 'X')

    def get_all_pipe_points(self) -> List[PipePoint]:
        return [PipePoint(x, y) for y in range(self.height) for x in range(self.width)
                if self.is_pipe_point(PipePoint(x, y))]

    def get_neighbors(self, p: PipePoint) -> List[PipePoint]:
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            np = PipePoint(p.x + dx, p.y + dy)
            if self.is_pipe_point(np):
                neighbors.append(np)
        return neighbors


class InspectionController:
    def __init__(self, sensor: PressureSensor, crawler: Crawler, pipe_map: PipeMap):
        self.sensor = sensor
        self.crawler = crawler
        self.pipe_map = pipe_map
        self.inspected = set()
        self.leaks = []

    def inspect_point(self, point: PipePoint, session_id: int):
        if point in self.inspected:
            return
        self.inspected.add(point)

        self.crawler.move_to(point, session_id)
        pressure = self.sensor.read_pressure()
        status = self.sensor.get_pressure_status(pressure)

        requests.post(f"{BASE_URL}/sessions/{session_id}/sensors",
                      json={"sensor_type": "pressure", "value": pressure, "unit": "bar"})

        requests.post(f"{BASE_URL}/sessions/{session_id}/actuators",
                      json={"actuator_type": "pressure_status",
                            "command": 1.0 if status == PressureStatus.NORMAL else 0.0,
                            "status": status.value})

        if status == PressureStatus.LEAK:
            self.leaks.append((point, pressure))
            requests.post(f"{BASE_URL}/sessions/{session_id}/events", json={
                "event_type": "leak_detected",
                "severity": "error",
                "message": f"УТЕЧКА в точке {point}: {pressure} бар (норма 50–120)"
            })
        elif status == PressureStatus.HIGH:
            requests.post(f"{BASE_URL}/sessions/{session_id}/events", json={
                "event_type": "high_pressure",
                "severity": "warning",
                "message": f"ВЫСОКОЕ ДАВЛЕНИЕ в {point}: {pressure} бар"
            })

        print(f"Проверка {point} → {pressure} бар → {status.value}")

    def auto_inspect(self, session_id: int):
        start = min(self.pipe_map.get_all_pipe_points(), key=lambda p: (p.y, p.x))
        print("\nЗАПУСК ИНСПЕКЦИИ ТРУБОПРОВОДА")
        print("=" * 50)
        self.inspect_point(start, session_id)

        stack = self.pipe_map.get_neighbors(start)
        visited = self.inspected.copy()

        while stack:
            nxt = stack.pop()
            if nxt not in visited:
                visited.add(nxt)
                self.inspect_point(nxt, session_id)
                for nb in self.pipe_map.get_neighbors(nxt):
                    if nb not in visited:
                        stack.append(nb)

    def report(self):
        total = len(self.pipe_map.get_all_pipe_points())
        print("\n" + "=" * 50)
        print("ИНСПЕКЦИЯ ЗАВЕРШЕНА")
        print(f"Проверено точек: {len(self.inspected)}/{total}")
        print(f"Обнаружено утечек: {len(self.leaks)}")
        if self.leaks:
            print("\nКРИТИЧЕСКИЕ УЧАСТКИ:")
            for p, pr in self.leaks:
                print(f"  • {p}: {pr} бар → УТЕЧКА")
        print("=" * 50)


def print_map(pipe_map: PipeMap):
    print("КАРТА ТРУБОПРОВОДА:")
    for y, row in enumerate(pipe_map.map_data):
        print("  " + "  ".join(row) + f"  ← y={y}")
    print()


def main():
    map_data = [
        ['X', 'X', 'X', 'X', 'X'],
        ['.', 'X', '.', 'X', '.'],
        ['.', 'X', 'X', 'X', '.'],
        ['.', 'X', '.', '.', '.'],
        ['X', 'X', 'X', 'X', 'X'],
    ]

    pipe_map = PipeMap(map_data)
    sensor = PressureSensor(leak_probability=0.45)
    crawler = Crawler()
    sensor.calibrate((50.0, 120.0))
    controller = InspectionController(sensor, crawler, pipe_map)

    resp = requests.post(f"{BASE_URL}/sessions", json={})
    session_id = resp.json()["id"]
    print(f"Сессия #{session_id} создана\n")

    print_map(pipe_map)
    controller.auto_inspect(session_id)
    controller.report()

    requests.post(f"{BASE_URL}/sessions/{session_id}/end", json={"status": "completed"})


if __name__ == "__main__":
    main()