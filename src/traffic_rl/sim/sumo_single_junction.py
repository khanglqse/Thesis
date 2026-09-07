"""Native SUMO environment for the evidence-backed Da Nang pilot junction."""

import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


DIRECTIONS = ("NW", "SE", "NE", "SW")


class _EncoderContract(object):
    max_green = 3


class SumoRoadNetAdapter(object):
    """Expose SUMO signal movements through the controller RoadNet contract."""

    def __init__(self, network_path, tls_id):
        import sumolib

        self.tls_id = tls_id
        self.network = sumolib.net.readNet(str(network_path), withPrograms=True)
        tls = self.network.getTLS(tls_id)
        programs = tls.getPrograms()
        program = programs.get("published_103s") or next(iter(programs.values()))
        phases = program.getPhases()
        connections = tls.getConnections()
        self._movements = []
        for phase_index in (0, 2, 4):
            state = phases[phase_index].state
            incoming, outgoing = [], []
            for incoming_lane, outgoing_lane, link_index in connections:
                if link_index < len(state) and state[link_index] in "Gg":
                    if incoming_lane.getID() not in incoming:
                        incoming.append(incoming_lane.getID())
                    if outgoing_lane.getID() not in outgoing:
                        outgoing.append(outgoing_lane.getID())
            self._movements.append((incoming, outgoing))

    def signalized_ids(self):
        return [self.tls_id]

    def green_phases(self, inter_id):
        return [0, 1, 2]

    def phase_movements(self, inter_id, phase_index):
        return self._movements[phase_index]


class SumoSingleJunctionEnv(object):
    """One-agent safe-phase environment with explicit off-network queue accounting."""

    def __init__(self, network_path, route_path, scheduled_vehicles, seed=1,
                 action_interval=10, max_steps=3600, yellow_time=7,
                 min_green=10, count_norm=20.0, sumo_binary="sumo",
                 tls_id="danang_ntn_cmt8_29", traci_module=None,
                 control_mode="agent"):
        self.network_path = str(Path(network_path).resolve())
        self.route_path = str(Path(route_path).resolve())
        self.scheduled_vehicles = int(scheduled_vehicles)
        self.seed = int(seed)
        self.action_interval = int(action_interval)
        self.max_steps = int(max_steps)
        self.yellow_time = int(yellow_time)
        self.min_green = int(min_green)
        self.count_norm = float(count_norm)
        self.sumo_binary = sumo_binary
        self.tls_id = tls_id
        if control_mode not in ("agent", "static_program"):
            raise ValueError("control_mode must be agent or static_program")
        self.control_mode = control_mode
        self.agent_ids = [tls_id]
        self.num_actions = {tls_id: 3}
        self.encoder = _EncoderContract()
        self.obs_dim = 16
        self.reward_type = "network_plus_pending_queue"
        self.state_mode = "approach_queue_count_pending_phase"
        self.roadnet = SumoRoadNetAdapter(self.network_path, tls_id)
        self._traci_module = traci_module
        self._connection = None
        self._tempdir = None
        self._incoming_lanes = self._load_incoming_lanes()
        self.current_green = 0
        self._since_switch = 0
        self._t = 0
        self._inserted = 0
        self._arrived = 0
        self._departed_at = {}
        self._completed_travel_times = []
        self._queue_integral = 0.0
        self._collision_events = set()
        self._error_log_path = None
        self._collision_output_path = None
        self._final_safety = {"collisions": 0, "emergency_braking": 0}
        self._last_phase_index = 0
        self._phase_switches = 0

    def _load_incoming_lanes(self):
        import sumolib

        network = sumolib.net.readNet(self.network_path)
        return dict((direction, [lane.getID() for lane in
                                network.getEdge("in_" + direction).getLanes()])
                    for direction in DIRECTIONS)

    @property
    def _traci(self):
        if self._traci_module is None:
            import traci
            self._traci_module = traci
        return self._traci_module

    def action_masks(self):
        return {self.tls_id: np.ones(3, dtype=np.bool_)}

    def _pending_by_approach(self):
        pending = dict((direction, 0) for direction in DIRECTIONS)
        for vehicle_id in self._connection.simulation.getPendingVehicles():
            direction = vehicle_id.split("_", 1)[0]
            if direction in pending:
                pending[direction] += 1
        return pending

    def current_waiting_counts(self):
        counts = {}
        for lanes in self._incoming_lanes.values():
            for lane in lanes:
                counts[lane] = int(self._connection.lane.getLastStepHaltingNumber(lane))
        for direction, pending in self._pending_by_approach().items():
            counts[self._incoming_lanes[direction][0]] += pending
        return counts

    def _observations(self):
        queues, vehicles = [], []
        for direction in DIRECTIONS:
            lanes = self._incoming_lanes[direction]
            queues.append(sum(self._connection.lane.getLastStepHaltingNumber(lane)
                              for lane in lanes) / self.count_norm)
            vehicles.append(sum(self._connection.lane.getLastStepVehicleNumber(lane)
                                for lane in lanes) / self.count_norm)
        pending = self._pending_by_approach()
        pending_values = [pending[direction] / self.count_norm for direction in DIRECTIONS]
        phase = [1.0 if index == self.current_green else 0.0 for index in range(3)]
        elapsed = [min(self._since_switch, 60) / 60.0]
        value = np.asarray(queues + vehicles + pending_values + phase + elapsed,
                           dtype=np.float32)
        return {self.tls_id: value}

    def _set_phase(self, phase_index, duration=1000000):
        self._connection.trafficlight.setPhase(self.tls_id, phase_index)
        self._connection.trafficlight.setPhaseDuration(self.tls_id, duration)

    def reset(self):
        self.close()
        self._tempdir = tempfile.TemporaryDirectory(prefix="traffic-rl-sumo-")
        self._collision_output_path = Path(self._tempdir.name) / "collisions.xml"
        self._error_log_path = Path(self._tempdir.name) / "sumo-errors.log"
        command = [
            self.sumo_binary, "--net-file", self.network_path,
            "--route-files", self.route_path, "--seed", str(self.seed),
            "--no-step-log", "true", "--time-to-teleport", "-1",
            "--collision.action", "warn", "--collision.check-junctions", "true",
            "--collision-output", str(self._collision_output_path),
            "--end", str(self.max_steps + 1),
            "--error-log", str(self._error_log_path),
            "--xml-validation", "never",
        ]
        label = "traffic_rl_" + uuid.uuid4().hex
        self._traci.start(command, label=label)
        self._connection = self._traci.getConnection(label)
        self.current_green = 0
        self._since_switch = 0
        self._t = 0
        self._inserted = 0
        self._arrived = 0
        self._departed_at = {}
        self._completed_travel_times = []
        self._queue_integral = 0.0
        self._collision_events = set()
        self._last_phase_index = 0
        self._phase_switches = 0
        self._final_safety = {"collisions": 0, "emergency_braking": 0}
        self._connection.trafficlight.setPhase(self.tls_id, 0)
        if self.control_mode == "agent":
            self._connection.trafficlight.setPhaseDuration(self.tls_id, 1000000)
        return self._observations()

    def _advance(self, steps):
        for _ in range(steps):
            self._connection.simulationStep()
            self._t += 1
            phase_index = int(self._connection.trafficlight.getPhase(self.tls_id))
            if phase_index % 2 == 0 and phase_index != self._last_phase_index:
                self._phase_switches += 1
            self._last_phase_index = phase_index
            now = float(self._connection.simulation.getTime())
            departed = list(self._connection.simulation.getDepartedIDList())
            arrived = list(self._connection.simulation.getArrivedIDList())
            self._inserted += len(departed)
            self._arrived += len(arrived)
            for vehicle_id in departed:
                self._departed_at[vehicle_id] = now
            for vehicle_id in arrived:
                departed_at = self._departed_at.pop(vehicle_id, None)
                if departed_at is not None:
                    self._completed_travel_times.append(now - departed_at)
            colliding = tuple(sorted(self._connection.simulation.getCollidingVehiclesIDList()))
            if colliding:
                self._collision_events.add((now, colliding))
            network_queue = sum(
                self._connection.lane.getLastStepHaltingNumber(lane)
                for lanes in self._incoming_lanes.values() for lane in lanes)
            self._queue_integral += network_queue + len(
                self._connection.simulation.getPendingVehicles())
        self._since_switch += steps

    def step(self, actions):
        if self.control_mode == "static_program":
            self._advance(self.action_interval)
            phase_index = int(self._connection.trafficlight.getPhase(self.tls_id))
            self.current_green = min(phase_index // 2, 2)
            return self._step_result()

        choice = int(actions[self.tls_id])
        switch = (0 <= choice < 3 and choice != self.current_green and
                  self._since_switch >= self.min_green)
        if switch:
            if self.yellow_time:
                self._set_phase(2 * self.current_green + 1, self.yellow_time)
                self._advance(min(self.yellow_time, self.action_interval))
            self.current_green = choice
            self._since_switch = 0
            self._set_phase(2 * choice)
            remaining = self.action_interval - self.yellow_time
            if remaining > 0:
                self._advance(remaining)
        else:
            self._set_phase(2 * self.current_green)
            self._advance(self.action_interval)

        return self._step_result()

    def _step_result(self):
        waiting = self.current_waiting_counts()
        pending = len(self._connection.simulation.getPendingVehicles())
        network_queue = sum(
            self._connection.lane.getLastStepHaltingNumber(lane)
            for lanes in self._incoming_lanes.values() for lane in lanes)
        reward = -(network_queue + pending)
        running = int(self._connection.vehicle.getIDCount())
        info = {
            "average_travel_time": (sum(self._completed_travel_times) /
                                    len(self._completed_travel_times)
                                    if self._completed_travel_times else 0.0),
            "vehicle_count": running,
            "running": running,
            "scheduled": self.scheduled_vehicles,
            "inserted": self._inserted,
            "arrived": self._arrived,
            "pending": pending,
            "network_queue": float(network_queue),
            "total_queue": float(network_queue + pending),
            "queue_integral_vehicle_seconds": self._queue_integral,
            "collisions": len(self._collision_events),
            "emergency_braking": self._emergency_braking_count(),
            "phase_switches": self._phase_switches,
            "step": self._t,
        }
        return self._observations(), {self.tls_id: float(reward)}, \
            self._t >= self.max_steps, info

    def _emergency_braking_count(self):
        if self._error_log_path is None or not self._error_log_path.exists():
            return 0
        return self._error_log_path.read_text().count("performs emergency braking")

    def close(self):
        if self._connection is not None:
            try:
                self._connection.close(False)
            finally:
                self._connection = None
        collisions = len(self._collision_events)
        if self._collision_output_path is not None and self._collision_output_path.exists():
            try:
                collisions = len(ET.parse(self._collision_output_path).getroot().findall(
                    "collision"))
            except ET.ParseError:
                pass
        self._final_safety = {
            "collisions": collisions,
            "emergency_braking": self._emergency_braking_count(),
        }
        if self._tempdir is not None:
            self._tempdir.cleanup()
            self._tempdir = None

    def final_safety_metrics(self):
        return dict(self._final_safety)
