"""Motor determinista de tráfico; no importa Qt ni depende de la pantalla."""

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from sigma_vial.domain.catalog import CATALOG, VehicleType
from sigma_vial.domain.perception import ObservationSource, SensorStatus, SimulatedObservationSource
from sigma_vial.domain.plates import PlateService
from sigma_vial.domain.registration import COLORS, RegisteredVehicle, VehicleRegistry
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
    BALANCED = "Tráfico equilibrado"
    NORTH_SOUTH = "Mayor tráfico Norte–Sur"
    EAST_WEST = "Mayor tráfico Oriente–Occidente"
    PEDESTRIANS = "Más peatones"
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
    vehicle_acceleration: float = 38
    vehicle_braking: float = 110
    vehicle_rate: float = 0.20
    pedestrian_rate: float = 0.05
    approach_extent: float = 430
    stop_line_distance: float = 186
    stop_margin: float = 4
    spawn_gap: float = 36
    lane_length: float = 860
    intersection_half: float = 186
    pedestrian_crossing_length: float = 232
    body_gap: float = 8
    vehicle_length: float = 28
    demand_switch_margin: int = 1
    demand_persistence: float = 1
    seed: int = 1

    @property
    def stop_position(self) -> float:
        """Vehicle-center position before the line, accounting for its full body."""
        return (
            self.approach_extent
            - self.stop_line_distance
            - self.vehicle_length / 2
            - self.stop_margin
        )

    @property
    def conflict_exit(self) -> float:
        """Center travel position after the rear clears the far edge of the conflict zone."""
        return self.approach_extent + self.intersection_half + self.vehicle_length / 2


@dataclass
class Vehicle:
    identifier: int
    access: Access
    lane: int
    position: float = 0
    wait: float = 0
    inside: bool = False
    exiting: bool = False
    committed: bool = False
    speed: float = 0
    kind: VehicleType = VehicleType.COMPACT
    plate: str = ""
    model_id: str = ""
    brand: str = "SIGMA ficticia"
    model: str = ""
    color: str = COLORS[0]

    @property
    def length(self) -> float:
        return self.kind.value[1]

    @property
    def width(self) -> float:
        return self.kind.value[2]


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
    vehicle_rates: dict[Access, float] = field(default_factory=lambda: dict.fromkeys(Access, 12.0))
    pedestrian_rate: float = 2.4
    vehicles: list[Vehicle] = field(default_factory=list)
    pedestrians: list[Pedestrian] = field(default_factory=list)
    completed_vehicles: int = 0
    decision: str = "Sin demanda; todos los accesos en rojo."
    blocked_exit: bool = False
    blocked_exits: set[Access] = field(default_factory=set)
    automatic_generation: bool = True
    running: bool = False
    _rng: random.Random = field(init=False, repr=False)
    vehicle_mix: tuple[float, ...] = (12, 30, 25, 15, 8, 4, 4, 2)
    selected_vehicle_type: VehicleType | None = VehicleType.COMPACT
    observation_source: ObservationSource = field(default_factory=SimulatedObservationSource)
    sensor_timeout: float = 1.0
    registry: VehicleRegistry | None = None
    _requested_types: dict[Access, deque] = field(
        default_factory=lambda: {a: deque() for a in Access}
    )
    _next_id: int = 0
    _empty_time: float = 0
    _opposing_advantage_time: float = 0
    _pending_phase: Phase | None = None
    _last_green_elapsed: float = 0
    _last_axis: str | None = None
    _served: deque = field(default_factory=lambda: deque(maxlen=32), repr=False)
    _arrival_due: dict[Access, float] = field(default_factory=dict)
    _pedestrian_due: float = 0

    def __post_init__(self) -> None:
        self.plates = PlateService(self.seed)
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

    def _choose_vehicle_type(self) -> VehicleType:
        return (
            self.selected_vehicle_type
            or self._rng.choices(tuple(VehicleType), weights=self.vehicle_mix, k=1)[0]
        )

    def add_vehicle(self, access: Access) -> bool:
        kind = self._choose_vehicle_type()
        if self._try_add_vehicle(access, kind):
            return True
        self.requested[access] += 1
        self._requested_types[access].append(kind)
        return False

    def _try_add_vehicle(self, access: Access, kind: VehicleType | None = None) -> bool:
        kind = kind or self._choose_vehicle_type()
        length = kind.value[1]
        for lane in range(2):
            queue = self.lane_vehicles(access, lane)
            if (
                not queue
                or queue[0].position >= (queue[0].length + length) / 2 + self.config.body_gap
            ):
                self._next_id += 1
                vehicle = Vehicle(
                    self._next_id,
                    access,
                    lane,
                    kind=kind,
                    plate=self.plates.issue(kind is VehicleType.MOTORCYCLE),
                    color=COLORS[self._next_id % len(COLORS)],
                    model_id=CATALOG[kind].model_id,
                    brand=CATALOG[kind].brand,
                    model=CATALOG[kind].model,
                )
                if self.registry is not None:
                    while not self.registry.reserve(
                        RegisteredVehicle(
                            vehicle.plate,
                            kind.name,
                            vehicle.brand,
                            vehicle.model,
                            vehicle.color,
                            vehicle.length,
                            vehicle.width,
                        )
                    ):
                        vehicle.plate = self.plates.issue(kind is VehicleType.MOTORCYCLE)
                self.vehicles.append(vehicle)
                return True
        return False

    def add_pedestrian(self, crossing: Access) -> None:
        self._next_id += 1
        self.pedestrians.append(Pedestrian(self._next_id, crossing, (self._next_id % 5) * 7))

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
        return self.pending_demand((access,))

    def pending_demand(self, accesses: tuple[Access, ...]) -> int:
        return sum(
            v.access in accesses and not v.inside and not v.exiting for v in self.vehicles
        ) + sum(self.requested[a] for a in accesses)

    def stopped_vehicles(self, accesses: tuple[Access, ...]) -> int:
        return sum(
            v.access in accesses and not v.inside and not v.exiting and v.speed <= 0.5
            for v in self.vehicles
        )

    def approaching_vehicles(self, accesses: tuple[Access, ...]) -> int:
        return sum(
            v.access in accesses and not v.inside and not v.exiting and v.speed > 0.5
            for v in self.vehicles
        )

    def exiting_vehicles(self, accesses: tuple[Access, ...]) -> int:
        return sum(v.access in accesses and v.exiting for v in self.vehicles)

    @property
    def green_elapsed(self) -> float:
        if self.phase in (Phase.NS_GREEN, Phase.EW_GREEN):
            return self.phase_time
        return self._last_green_elapsed

    def observations(self):
        return self.observation_source.read(self.time, self.vehicles, self.pedestrians)

    def axis_demand(self, axis: str) -> int:
        batch = self.observations()
        return sum(
            summary.demand
            for access, summary in batch.traffic.items()
            if access in self._axis_accesses(axis)
        )

    def axis_wait(self, axis: str) -> float:
        batch = self.observations()
        return max(
            (
                summary.max_wait
                for access, summary in batch.traffic.items()
                if access in self._axis_accesses(axis)
            ),
            default=0,
        )

    @staticmethod
    def _axis_accesses(axis: str) -> tuple[Access, ...]:
        return (Access.NORTH, Access.SOUTH) if axis == "ns" else (Access.EAST, Access.WEST)

    def pedestrian_waiting(self) -> int:
        return len(self.observations().pedestrian_waits)

    def _demand(self, accesses: tuple[Access, ...]) -> bool:
        return any(self.waiting(a) for a in accesses)

    def _max_wait(self, accesses: tuple[Access, ...]) -> float:
        return max(
            (
                v.wait
                for v in self.vehicles
                if v.access in accesses and not v.inside and not v.exiting
            ),
            default=0,
        )

    def _finish_phase(self, reason: str) -> None:
        self.phase = Phase.CLEARANCE
        self.phase_time = 0
        self.decision = reason
        self._empty_time = 0
        self._opposing_advantage_time = 0

    def _choose_phase(self) -> None:
        ns_demand, ew_demand = self.axis_demand("ns"), self.axis_demand("ew")
        p_wait = max(self.observations().pedestrian_waits, default=0)
        ns_wait, ew_wait = self.axis_wait("ns"), self.axis_wait("ew")
        pedestrian_waiting = self.pedestrian_waiting() > 0
        if pedestrian_waiting and p_wait >= self.config.max_pedestrian_wait:
            key = "pedestrian"
            reason = "Atención peatonal por espera máxima."
        elif ns_demand and ns_wait >= self.config.max_vehicle_wait and ns_wait >= ew_wait:
            key = "ns"
            reason = "Atención Norte–Sur por espera máxima."
        elif ew_demand and ew_wait >= self.config.max_vehicle_wait and ew_wait >= ns_wait:
            key = "ew"
            reason = "Atención Oriente–Occidente por espera máxima."
        elif self.pedestrian_waiting() >= 2 and (ns_demand or ew_demand):
            key = "pedestrian"
            reason = "Atención peatonal por demanda de dos personas."
        elif pedestrian_waiting and not ns_demand and not ew_demand:
            key = "pedestrian"
            reason = "Atención de peatones en espera."
        else:
            if ns_demand and not ew_demand:
                key, reason = "ns", "Atención de la demanda Norte–Sur."
            elif ew_demand and not ns_demand:
                key, reason = "ew", "Atención de la demanda Oriente–Occidente."
            elif not ns_demand and not ew_demand and pedestrian_waiting:
                key, reason = "pedestrian", "Atención de peatones en espera."
            elif not ns_demand and not ew_demand:
                key, reason = "ns", "Sin demanda; inicio Norte–Sur en espera de llegadas."
            elif ns_demand > ew_demand:
                key, reason = "ns", "Atención por mayor demanda Norte–Sur."
            elif ew_demand > ns_demand:
                key, reason = "ew", "Atención por mayor demanda Oriente–Occidente."
            elif ns_wait > ew_wait:
                key, reason = "ns", "Atención Norte–Sur por mayor espera."
            elif ew_wait > ns_wait:
                key, reason = "ew", "Atención Oriente–Occidente por mayor espera."
            else:
                key = "ew" if self._last_axis == "ns" else "ns"
                reason = "Demanda similar; alternancia Norte–Sur / Oriente–Occidente."
        self._activate_phase(key, reason)

    def _activate_phase(self, key: str, reason: str) -> None:
        phase = {"ns": Phase.NS_GREEN, "ew": Phase.EW_GREEN, "pedestrian": Phase.WALK}.get(
            key, Phase.IDLE
        )
        self.phase = phase
        self.phase_time = 0
        self._pending_phase = None
        self._opposing_advantage_time = 0
        if key in ("ns", "ew"):
            self._last_axis = key
        self.decision = reason

    def _request_phase_change(self, key: str, reason: str) -> None:
        self._pending_phase = {
            "ns": Phase.NS_GREEN,
            "ew": Phase.EW_GREEN,
            "pedestrian": Phase.WALK,
        }[key]
        self._last_green_elapsed = self.phase_time
        self.phase = Phase.NS_YELLOW if self.phase is Phase.NS_GREEN else Phase.EW_YELLOW
        self.phase_time = 0
        self._empty_time = 0
        self._opposing_advantage_time = 0
        self.decision = reason

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
        if self.automatic_generation:
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
                pending = self._requested_types[access]
                if self._try_add_vehicle(access, pending[0] if pending else None):
                    self.requested[access] -= 1
                    if pending:
                        pending.popleft()
                else:
                    break
        self._move_vehicles(dt)
        self._move_pedestrians(dt)
        self._control(dt)

    def _move_vehicles(self, dt: float) -> None:
        for access in Access:
            for lane in range(2):
                queue = self.lane_vehicles(access, lane)
                for index in range(len(queue) - 1, -1, -1):
                    vehicle = queue[index]
                    stop_position = (
                        self.config.stop_position
                        + (self.config.vehicle_length - vehicle.length) / 2
                    )
                    conflict_exit = (
                        self.config.conflict_exit
                        + (vehicle.length - self.config.vehicle_length) / 2
                    )
                    exit_position = self.config.lane_length + vehicle.length / 2
                    vmax = min(self.config.vehicle_speed, vehicle.kind.value[3])
                    acceleration = min(self.config.vehicle_acceleration, vehicle.kind.value[4])
                    braking = min(self.config.vehicle_braking, vehicle.kind.value[5])
                    leader_limit = (
                        queue[index + 1].position
                        - (queue[index + 1].length + vehicle.length) / 2
                        - self.config.body_gap
                        if index < len(queue) - 1
                        else float("inf")
                    )
                    if vehicle.inside or vehicle.exiting:
                        vehicle.speed = min(
                            vmax,
                            vehicle.speed + acceleration * dt,
                        )
                        vehicle.position = min(leader_limit, vehicle.position + vehicle.speed * dt)
                        if vehicle.inside and vehicle.position >= conflict_exit:
                            vehicle.inside = False
                            vehicle.exiting = True
                        if vehicle.position >= exit_position:
                            self.vehicles.remove(vehicle)
                            self.completed_vehicles += 1
                        continue
                    vehicle.wait += dt
                    limit = (
                        stop_position
                        if index == len(queue) - 1
                        else queue[index + 1].position
                        - (queue[index + 1].length + vehicle.length) / 2
                        - self.config.body_gap
                    )
                    target = max(vehicle.position, min(limit, stop_position))
                    signal = self.signals[access]
                    yellow_committed = (
                        signal is SignalState.YELLOW
                        and vehicle.speed > 0.5
                        and vehicle.position >= stop_position - vehicle.speed**2 / (2 * braking)
                    )
                    vehicle.committed = vehicle.committed or yellow_committed
                    permitted = (
                        (signal is SignalState.GREEN or vehicle.committed)
                        and not any(person.walking for person in self.pedestrians)
                        and access not in self.blocked_exits
                        and not (self.blocked_exit and not self.blocked_exits)
                    )
                    exit_capacity = self.config.lane_length - (
                        self.config.approach_extent + self.config.intersection_half
                    )
                    permitted = permitted and exit_capacity >= vehicle.length + self.config.body_gap
                    if (
                        permitted
                        and vehicle.position >= stop_position
                        and leader_limit > vehicle.position
                    ):
                        vehicle.inside = True
                        vehicle.committed = False
                        vehicle.wait = 0
                        self._served.append(
                            "ns" if access in (Access.NORTH, Access.SOUTH) else "ew"
                        )
                    else:
                        target_speed = vmax
                        if not permitted:
                            distance = max(0.0, target - vehicle.position)
                            target_speed = min(
                                target_speed,
                                (2 * braking * distance) ** 0.5,
                            )
                        if index < len(queue) - 1:
                            leader = queue[index + 1]
                            gap = (
                                leader.position
                                - vehicle.position
                                - (leader.length + vehicle.length) / 2
                                - self.config.body_gap
                            )
                            if gap <= 0:
                                target_speed = 0
                            else:
                                target_speed = min(target_speed, leader.speed + gap / dt)
                        rate = acceleration if target_speed > vehicle.speed else braking
                        if vehicle.speed < target_speed:
                            vehicle.speed = min(target_speed, vehicle.speed + rate * dt)
                        else:
                            vehicle.speed = max(target_speed, vehicle.speed - rate * dt)
                        vehicle.position = min(target, vehicle.position + vehicle.speed * dt)

    def _move_pedestrians(self, dt: float) -> None:
        for person in self.pedestrians:
            if person.walking:
                person.position += self.config.walk_speed * dt
                if person.position >= self.config.pedestrian_crossing_length:
                    self.pedestrians.remove(person)
                    break
            else:
                person.wait += dt
                if self.phase is Phase.WALK and self.phase_time < self.config.walk_admission:
                    person.walking = True

    def _control(self, dt: float) -> None:
        batch = self.observations()
        healthy = (
            all(
                s.status is SensorStatus.AVAILABLE
                and self.time - s.observed_at <= self.sensor_timeout
                for s in batch.traffic.values()
            )
            and set(batch.traffic) == set(Access)
            and self.time - batch.observed_at <= self.sensor_timeout
        )
        if not healthy:
            if self.phase in (Phase.NS_GREEN, Phase.EW_GREEN):
                self._request_phase_change("ns", "Sensor sin datos; cierre preventivo.")
                self._pending_phase = None
            elif (
                self.phase in (Phase.NS_YELLOW, Phase.EW_YELLOW)
                and self.phase_time >= self.config.yellow
            ):
                self._finish_phase("Sensores no disponibles; todos en rojo.")
            self.decision = (
                "Respaldo: observación ausente o vencida; se retienen nuevas admisiones."
            )
            return
        if self.phase is Phase.IDLE:
            if self.axis_demand("ns") or self.axis_demand("ew") or self.pedestrian_waiting():
                self._choose_phase()
            return
        if self.phase in (Phase.NS_GREEN, Phase.EW_GREEN):
            active_axis = "ns" if self.phase is Phase.NS_GREEN else "ew"
            opposite_axis = "ew" if active_axis == "ns" else "ns"
            active_demand = self.axis_demand(active_axis)
            opposing_demand = self.axis_demand(opposite_axis)
            empty = active_demand == 0
            self._empty_time = self._empty_time + dt if empty else 0
            if self.phase_time < self.config.min_green:
                self.decision = f"Verde {self._axis_name(active_axis)}; mínimo de verde en curso."
                self._opposing_advantage_time = 0
                return

            waiting_pedestrians = self.pedestrian_waiting()
            oldest_pedestrian_wait = max(self.observations().pedestrian_waits, default=0)
            pedestrian_priority = waiting_pedestrians >= 2 or (
                waiting_pedestrians > 0
                and oldest_pedestrian_wait >= self.config.max_pedestrian_wait
            )
            if pedestrian_priority:
                self._request_phase_change("pedestrian", "Cambio por prioridad peatonal.")
                return

            if (
                waiting_pedestrians
                and active_demand == 0
                and self._empty_time >= self.config.empty_interval
            ):
                self._request_phase_change(
                    "pedestrian", "Cambio por peatones y carril vehicular sin demanda."
                )
                return

            if opposing_demand == 0:
                self._opposing_advantage_time = 0
                self.decision = (
                    f"Verde {self._axis_name(active_axis)} mantenido; sin demanda incompatible."
                )
                return

            opposing_wait = self.axis_wait(opposite_axis)
            active_wait = self.axis_wait(active_axis)
            if opposing_wait >= self.config.max_vehicle_wait:
                self._request_phase_change(
                    opposite_axis,
                    f"Cambio por espera máxima hacia {self._axis_name(opposite_axis)}.",
                )
                return

            if self.phase_time >= self.config.max_green:
                self._request_phase_change(
                    opposite_axis,
                    f"Verde máximo alcanzado; turno de {self._axis_name(opposite_axis)}.",
                )
                return

            if active_demand == 0 and self._empty_time >= self.config.empty_interval:
                self._request_phase_change(
                    opposite_axis,
                    f"Cambio por carril activo sin demanda durante {self._empty_time:.1f} s.",
                )
                return

            count_advantage = opposing_demand > active_demand + self.config.demand_switch_margin
            wait_advantage = opposing_wait > active_wait
            balanced = (
                active_demand > 0
                and abs(opposing_demand - active_demand) <= self.config.demand_switch_margin
            )
            should_consider_change = count_advantage or wait_advantage or balanced
            if should_consider_change:
                self._opposing_advantage_time += dt
            else:
                self._opposing_advantage_time = 0
            if self._opposing_advantage_time >= self.config.demand_persistence:
                if count_advantage:
                    reason = f"Cambio por mayor demanda {self._axis_name(opposite_axis)}."
                elif wait_advantage:
                    reason = f"Cambio por mayor espera en {self._axis_name(opposite_axis)}."
                else:
                    reason = "Demanda similar; cambio para alternar los ejes."
                self._request_phase_change(opposite_axis, reason)
            elif should_consider_change:
                self.decision = (
                    f"Demanda pendiente {self._axis_name(active_axis)}: {active_demand}; "
                    f"{self._axis_name(opposite_axis)}: {opposing_demand}. "
                    f"Evaluando el relevo ({self._opposing_advantage_time:.1f}/"
                    f"{self.config.demand_persistence:.1f} s de persistencia)."
                )
            else:
                self.decision = (
                    f"Verde {self._axis_name(active_axis)} mantenido por demanda y espera; "
                    f"incompatible {opposing_demand}, activa {active_demand}."
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
            and not any(v.inside or v.committed for v in self.vehicles)
        ):
            if self._pending_phase is not None:
                target = self._pending_phase
                if target is Phase.WALK:
                    self._activate_phase("pedestrian", "Admisión peatonal tras despeje del cruce.")
                elif target is Phase.NS_GREEN:
                    self._activate_phase("ns", "Fase Norte–Sur habilitada tras despeje.")
                else:
                    self._activate_phase("ew", "Fase Oriente–Occidente habilitada tras despeje.")
            else:
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

    @staticmethod
    def _axis_name(axis: str) -> str:
        return "Norte–Sur" if axis == "ns" else "Oriente–Occidente"

    def load_scenario(self, scenario: Scenario) -> None:
        self.reset()
        self.vehicle_rates = dict.fromkeys(Access, 0.0)
        self.pedestrian_rate = 0
        self.automatic_generation = True
        self.selected_vehicle_type = VehicleType.COMPACT
        self.vehicle_mix = (12, 30, 25, 15, 8, 4, 4, 2)
        if scenario is Scenario.BALANCED:
            self.vehicle_rates = dict.fromkeys(Access, 12.0)
            self.pedestrian_rate = 2.4
        elif scenario is Scenario.PEDESTRIANS:
            self.vehicle_rates = dict.fromkeys(Access, 4.0)
            self.pedestrian_rate = 12.0
        elif scenario is Scenario.NORTH_SOUTH:
            self.vehicle_rates = dict.fromkeys(Access, 3.0)
            self.vehicle_rates[Access.NORTH] = self.vehicle_rates[Access.SOUTH] = 18.0
            for a in (Access.NORTH, Access.SOUTH):
                self.add_vehicle(a)
        elif scenario is Scenario.EAST_WEST:
            self.vehicle_rates = dict.fromkeys(Access, 3.0)
            self.vehicle_rates[Access.EAST] = self.vehicle_rates[Access.WEST] = 18.0
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
        automatic_generation = self.automatic_generation
        selected_type = self.selected_vehicle_type
        vehicle_mix = self.vehicle_mix
        config, seed = self.config, self.seed
        rates, pedestrian_rate = self.vehicle_rates.copy(), self.pedestrian_rate
        self.__dict__.update(Simulation(config=config, seed=seed, registry=self.registry).__dict__)
        self.vehicle_rates = rates
        self.pedestrian_rate = pedestrian_rate
        self.automatic_generation = automatic_generation
        self.selected_vehicle_type = selected_type
        self.vehicle_mix = vehicle_mix
