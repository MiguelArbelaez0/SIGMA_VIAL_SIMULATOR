"""Motor determinista de tráfico; no importa Qt ni depende de la pantalla."""

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from sigma_vial.domain.scenario import Access, SignalState


class Phase(Enum):
    IDLE = "Todos en rojo · Esperando demanda"
    NS_GREEN = "Verde norte-sur"
    NS_YELLOW = "Amarillo norte-sur"
    EW_GREEN = "Verde oriente-occidente"
    EW_YELLOW = "Amarillo oriente-occidente"
    CLEARANCE = "Despeje del cruce"
    WALK = "Admisión peatonal"
    WALK_CLEARANCE = "Despeje peatonal"


class Scenario(Enum):
    NORTH_SOUTH = "Tráfico norte-sur"
    EAST_WEST = "Tráfico oriente-occidente"
    ALL_ACCESS = "Demanda en cuatro accesos"
    TWO_PEDESTRIANS = "Dos peatones y un vehículo"
    ONE_PEDESTRIAN = "Un peatón y tráfico continuo"
    EMPTY_ACTIVE = "Carriles vacíos y demanda incompatible"
    CONTINUOUS_PEDESTRIANS = "Llegadas peatonales continuas"
    BLOCKED_EXIT = "Salida bloqueada y liberación"


@dataclass(frozen=True)
class SimulationConfig:
    min_green: float = 8
    max_green: float = 32
    yellow: float = 3
    vehicle_clearance: float = 2
    empty_interval: float = 4
    max_vehicle_wait: float = 45
    max_pedestrian_wait: float = 35
    walk_admission: float = 8
    walk_speed: float = 48
    vehicle_speed: float = 110
    vehicle_rate: float = 0.12
    pedestrian_rate: float = 0.025
    spawn_gap: float = 30
    lane_length: float = 600
    intersection_half: float = 116
    vehicle_length: float = 24
    seed: int = 1


@dataclass
class Vehicle:
    identifier: int
    access: Access
    lane: int
    position: float = 0
    wait: float = 0
    inside: bool = False


@dataclass
class Pedestrian:
    identifier: int
    crossing: Access
    lane: float
    wait: float = 0
    position: float = 0
    walking: bool = False


@dataclass
class Simulation:
    config: SimulationConfig = field(default_factory=SimulationConfig)
    seed: int = 1
    time: float = 0
    phase: Phase = Phase.IDLE
    phase_time: float = 0
    requested: dict[Access, int] = field(default_factory=lambda: dict.fromkeys(Access, 0))
    vehicle_rates: dict[Access, float] = field(default_factory=lambda: dict.fromkeys(Access, 3.0))
    pedestrian_rate: float = 0.75
    vehicles: list[Vehicle] = field(default_factory=list)
    pedestrians: list[Pedestrian] = field(default_factory=list)
    completed_vehicles: int = 0
    decision: str = "Sin demanda; todos los accesos en rojo."
    blocked_exit: bool = False
    blocked_exits: set[Access] = field(default_factory=set)
    running: bool = False
    _rng: random.Random = field(init=False, repr=False)
    _next_id: int = 0
    _empty_time: float = 0
    _served: deque = field(default_factory=lambda: deque(maxlen=32), repr=False)
    _arrival_due: dict[Access, float] = field(default_factory=dict)
    _pedestrian_due: float = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._arrival_due = dict.fromkeys(Access, 0.0)

    @property
    def signals(self) -> dict[Access, SignalState]:
        state = SignalState.RED
        if self.phase is Phase.NS_GREEN:
            state = SignalState.GREEN
        elif self.phase is Phase.NS_YELLOW:
            state = SignalState.YELLOW
        elif self.phase is Phase.EW_GREEN:
            state = SignalState.GREEN
        elif self.phase is Phase.EW_YELLOW:
            state = SignalState.YELLOW
        active = (
            (Access.NORTH, Access.SOUTH)
            if self.phase.name.startswith("NS_")
            else ((Access.EAST, Access.WEST) if self.phase.name.startswith("EW_") else ())
        )
        return {access: state if access in active else SignalState.RED for access in Access}

    def set_demand(self, access: Access, vehicles_per_minute: float) -> None:
        self.vehicle_rates[access] = max(0.0, min(60.0, vehicles_per_minute))

    def add_vehicle(self, access: Access) -> bool:
        for lane in range(2):
            queue = self.lane_vehicles(access, lane)
            if not queue or queue[0].position >= self.config.spawn_gap:
                self._next_id += 1
                self.vehicles.append(Vehicle(self._next_id, access, lane))
                return True
        self.requested[access] += 1
        return False

    def add_pedestrian(self, crossing: Access) -> None:
        self._next_id += 1
        self.pedestrians.append(Pedestrian(self._next_id, crossing, (self._next_id % 5) * 13))

    def set_exit_blocked(self, access: Access, blocked: bool) -> None:
        if blocked:
            self.blocked_exits.add(access)
        else:
            self.blocked_exits.discard(access)
        self.blocked_exit = bool(self.blocked_exits)
        self.decision = (
            f"Salida de {access.value} bloqueada; se impide la entrada al cruce."
            if blocked
            else f"Salida de {access.value} liberada; se recupera el servicio."
        )

    def lane_vehicles(self, access: Access, lane: int) -> list[Vehicle]:
        return sorted(
            (v for v in self.vehicles if v.access is access and v.lane == lane),
            key=lambda v: v.position,
        )

    def waiting(self, access: Access) -> int:
        return (
            sum(v.access is access and not v.inside for v in self.vehicles) + self.requested[access]
        )

    def pedestrian_waiting(self) -> int:
        return sum(not p.walking for p in self.pedestrians)

    def _demand(self, accesses: tuple[Access, ...]) -> bool:
        return any(self.waiting(a) for a in accesses)

    def _max_wait(self, accesses: tuple[Access, ...]) -> float:
        return max((v.wait for v in self.vehicles if v.access in accesses), default=0)

    def _finish_phase(self, reason: str) -> None:
        self.phase = Phase.CLEARANCE
        self.phase_time = 0
        self.decision = reason
        self._empty_time = 0

    def _choose_phase(self) -> None:
        ns, ew = (Access.NORTH, Access.SOUTH), (Access.EAST, Access.WEST)
        p_wait = max((p.wait for p in self.pedestrians if not p.walking), default=0)
        candidates = []
        for key, wait, demand in (
            ("pedestrian", p_wait, self.pedestrian_waiting() > 0),
            ("ns", self._max_wait(ns), self._demand(ns)),
            ("ew", self._max_wait(ew), self._demand(ew)),
        ):
            if demand and wait >= (
                self.config.max_pedestrian_wait
                if key == "pedestrian"
                else self.config.max_vehicle_wait
            ):
                candidates.append((wait, key))
        if candidates:
            longest = max(x[0] for x in candidates)
            tied = [x[1] for x in candidates if x[0] == longest]
            key = tied[0]
            for previous in reversed(self._served):
                if previous in tied:
                    key = tied[(tied.index(previous) + 1) % len(tied)]
                    break
            self.decision = f"Atención reservada por espera máxima: {key}."
        elif self.pedestrian_waiting() >= 2 and self._demand(ns + ew):
            key = "pedestrian"
            self.decision = "Atención peatonal por demanda de dos personas."
        else:
            key = max(("ns", "ew"), key=lambda x: self._max_wait(ns if x == "ns" else ew))
            if self.pedestrian_waiting() and not self._demand(ns + ew):
                key = "pedestrian"
                self.decision = "Atención de peatones en espera."
            else:
                self.decision = "Atención de la demanda vehicular con mayor espera."
        self.phase = {"ns": Phase.NS_GREEN, "ew": Phase.EW_GREEN, "pedestrian": Phase.WALK}.get(
            key, Phase.IDLE
        )
        self.phase_time = 0

    def advance(self, seconds: float, step: float = 0.05) -> None:
        if seconds < 0 or step <= 0:
            raise ValueError("El avance debe ser positivo y el paso mayor que cero.")
        remaining = seconds
        while remaining > 1e-9:
            dt = min(step, remaining)
            remaining -= dt
            self._tick(dt)

    def _tick(self, dt: float) -> None:
        if not self.running:
            return
        self.time += dt
        self.phase_time += dt
        for access in Access:
            self._arrival_due[access] += dt * self.vehicle_rates[access] / 60
            while self._arrival_due[access] >= 1:
                self._arrival_due[access] -= 1
                self.add_vehicle(access)
        self._pedestrian_due += dt * self.pedestrian_rate / 60
        while self._pedestrian_due >= 1:
            self._pedestrian_due -= 1
            self.add_pedestrian(tuple(Access)[self._rng.randrange(4)])
        for access in Access:
            count = self.requested[access]
            for _ in range(min(count, 8)):
                if self.add_vehicle(access):
                    self.requested[access] -= 1
                else:
                    break
        self._move_vehicles(dt)
        self._move_pedestrians(dt)
        self._control(dt)

    def _move_vehicles(self, dt: float) -> None:
        stop_position = self.config.lane_length - 2 * self.config.intersection_half
        exit_position = self.config.lane_length + self.config.vehicle_length
        for access in Access:
            for lane in range(2):
                queue = self.lane_vehicles(access, lane)
                for index in range(len(queue) - 1, -1, -1):
                    vehicle = queue[index]
                    if vehicle.inside:
                        vehicle.position += self.config.vehicle_speed * dt
                        if vehicle.position >= exit_position:
                            self.vehicles.remove(vehicle)
                            self.completed_vehicles += 1
                        continue
                    vehicle.wait += dt
                    limit = (
                        stop_position
                        if index == len(queue) - 1
                        else queue[index + 1].position - self.config.spawn_gap
                    )
                    target = min(limit, stop_position)
                    permitted = (
                        self.signals[access] is SignalState.GREEN
                        and not any(person.walking for person in self.pedestrians)
                        and access not in self.blocked_exits
                        and not (self.blocked_exit and not self.blocked_exits)
                    )
                    if permitted and vehicle.position >= stop_position:
                        vehicle.inside = True
                        vehicle.wait = 0
                        self._served.append(
                            "ns" if access in (Access.NORTH, Access.SOUTH) else "ew"
                        )
                    elif target > vehicle.position:
                        vehicle.position = min(
                            target, vehicle.position + self.config.vehicle_speed * dt
                        )

    def _move_pedestrians(self, dt: float) -> None:
        for person in self.pedestrians:
            if person.walking:
                person.position += self.config.walk_speed * dt
                if person.position >= 2 * self.config.intersection_half:
                    self.pedestrians.remove(person)
                    break
            else:
                person.wait += dt
                if self.phase is Phase.WALK and self.phase_time < self.config.walk_admission:
                    person.walking = True

    def _control(self, dt: float) -> None:
        ns, ew = (Access.NORTH, Access.SOUTH), (Access.EAST, Access.WEST)
        if self.phase is Phase.IDLE:
            if self._demand(ns + ew) or self.pedestrian_waiting():
                self._choose_phase()
            return
        if self.phase in (Phase.NS_GREEN, Phase.EW_GREEN):
            active = ns if self.phase is Phase.NS_GREEN else ew
            incompatible = ew if self.phase is Phase.NS_GREEN else ns
            empty = not any(v.access in active for v in self.vehicles)
            self._empty_time = self._empty_time + dt if empty else 0
            pedestrian_priority = (
                self.pedestrian_waiting() >= 2 and self.phase_time >= self.config.min_green
            )
            wants_change = self.phase_time >= self.config.min_green and (
                (self._empty_time >= self.config.empty_interval and self._demand(incompatible))
                or (
                    self._demand(incompatible)
                    and self._max_wait(incompatible) >= self.config.max_vehicle_wait
                )
                or pedestrian_priority
            )
            if self.phase_time >= self.config.max_green or wants_change:
                if self.phase is Phase.NS_GREEN:
                    self.phase = Phase.NS_YELLOW
                else:
                    self.phase = Phase.EW_YELLOW
                self.phase_time = 0
                self.decision = (
                    "Cambio solicitado por vacío sostenido."
                    if self._empty_time >= self.config.empty_interval
                    else "Cambio seguro solicitado por demanda y espera."
                )
            return
        if (
            self.phase in (Phase.NS_YELLOW, Phase.EW_YELLOW)
            and self.phase_time >= self.config.yellow
        ):
            self._finish_phase("Esperando despeje del cruce.")
            return
        if (
            self.phase is Phase.CLEARANCE
            and self.phase_time >= self.config.vehicle_clearance
            and not any(v.inside for v in self.vehicles)
        ):
            self._choose_phase()
            return
        if self.phase is Phase.WALK and self.phase_time >= self.config.walk_admission:
            self.phase = Phase.WALK_CLEARANCE
            self.phase_time = 0
            self.decision = "Despeje peatonal; no se admiten nuevas personas."
            return
        if (
            self.phase is Phase.WALK_CLEARANCE
            and self.phase_time >= self.config.vehicle_clearance
            and not any(p.walking for p in self.pedestrians)
        ):
            self._choose_phase()

    def load_scenario(self, scenario: Scenario) -> None:
        self.reset()
        if scenario is Scenario.NORTH_SOUTH:
            for a in (Access.NORTH, Access.SOUTH):
                self.add_vehicle(a)
        elif scenario is Scenario.EAST_WEST:
            for a in (Access.EAST, Access.WEST):
                self.add_vehicle(a)
        elif scenario is Scenario.ALL_ACCESS:
            for a in Access:
                self.add_vehicle(a)
        elif scenario is Scenario.TWO_PEDESTRIANS:
            self.add_pedestrian(Access.NORTH)
            self.add_pedestrian(Access.NORTH)
            self.add_vehicle(Access.SOUTH)
        elif scenario is Scenario.ONE_PEDESTRIAN:
            self.add_pedestrian(Access.NORTH)
            for a in Access:
                self.set_demand(a, 12)
        elif scenario is Scenario.EMPTY_ACTIVE:
            self.add_vehicle(Access.EAST)
            self.add_vehicle(Access.WEST)
            self.phase = Phase.NS_GREEN
        elif scenario is Scenario.CONTINUOUS_PEDESTRIANS:
            self.add_pedestrian(Access.NORTH)
            self.pedestrian_rate = 12
        elif scenario is Scenario.BLOCKED_EXIT:
            self.add_vehicle(Access.NORTH)
            self.set_exit_blocked(Access.NORTH, True)

    def reset(self) -> None:
        config, seed = self.config, self.seed
        rates, pedestrian_rate = self.vehicle_rates.copy(), self.pedestrian_rate
        self.__dict__.update(Simulation(config=config, seed=seed).__dict__)
        self.vehicle_rates = rates
        self.pedestrian_rate = pedestrian_rate
