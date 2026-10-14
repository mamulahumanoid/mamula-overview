from __future__ import annotations
import time
from typing import Any, Dict
from core.controllers.controller_manager import ControllerManager
from core.estimation.joint_state_estimator import JointStateEstimator
from core.hardware.sim_hw_interface import SimHardwareInterface
from core.control.motion_actions import AUTHORIZED_EXECUTIVE_TOPIC, is_motion_action
from core.safety.embodiment_safety_monitor import EmbodimentSafetyMonitor

def now_ms() -> int:
    return int(time.time() * 1000)
class EmbodimentFoundationModule:
    name = 'embodiment_foundation_module'
    def __init__(self, bus, rt, hardware=None, controller_manager=None, estimator=None, safety_monitor=None):
        self.bus = bus
        self.rt = rt
        self.hardware = hardware or SimHardwareInterface()
        self.controller_manager = controller_manager or ControllerManager()
        self.estimator = estimator or JointStateEstimator()
        self.safety_monitor = safety_monitor or EmbodimentSafetyMonitor()
        self.last_profile: Dict[str, Any] = {}
        self.last_joint_state: Dict[str, Any] = {}
        self.last_safety_status: Dict[str, Any] = {'safe': True, 'active_stop': False, 'reasons': [], 'severity': 'info', 'ts_ms': now_ms()}
        bus.subscribe('joints.frame', self.on_joint_frame)
        bus.subscribe('executive.action', self.on_executive_action)
        bus.subscribe(AUTHORIZED_EXECUTIVE_TOPIC, self.on_executive_action)
        bus.subscribe('executive.action_result', self.on_action_result)
        bus.subscribe('embodiment.query', self.on_query)
    def tick(self):
        self.rt.beat(self.name)
    def on_joint_frame(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        hw_state = self.hardware.observe_joint_frame(payload)
        hw_payload = hw_state.to_dict()
        self.last_joint_state = self.estimator.update(hw_state)
        self.last_safety_status = self.safety_monitor.evaluate(self.last_joint_state)
        self.bus.publish('embodiment.hardware_state', hw_payload)
        self.bus.publish('embodiment.joint_state', dict(self.last_joint_state))
        self.bus.publish('embodiment.safety_status', dict(self.last_safety_status))
        if self.last_safety_status.get('active_stop'):
            self.bus.publish('embodiment.safety_stop', {'active': True, 'reasons': list(self.last_safety_status.get('reasons', []) or []), 'severity': str(self.last_safety_status.get('severity', 'crit') or 'crit'), 'ts_ms': now_ms()})
    def on_executive_action(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        action = dict(payload.get('action', {}) or payload)
        if not action:
            return
        action_type = str(action.get('action_type', '') or '').upper()
        if is_motion_action(action_type) and topic != AUTHORIZED_EXECUTIVE_TOPIC:
            return
        self.last_profile = self.controller_manager.select_for_action(action)
        self.hardware.set_control_mode(str(self.last_profile.get('control_mode', 'idle') or 'idle'))
        self.bus.publish('embodiment.control_profile', {'action_id': str(action.get('action_id', '') or ''), 'action_type': str(action.get('action_type', '') or ''), 'profile': dict(self.last_profile), 'ts_ms': now_ms()})
    def on_action_result(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        status = str(payload.get('status', '') or '').lower()
        if status in ('completed', 'failed'):
            self.hardware.set_control_mode('idle')
        self.bus.publish('embodiment.execution_feedback', {'action_id': str(payload.get('action_id', '') or ''), 'action_type': str(payload.get('action_type', '') or ''), 'status': status, 'reason': str(payload.get('reason', '') or ''), 'control_mode': self.hardware.get_state().control_mode, 'ts_ms': now_ms()})
    def on_query(self, topic: str, msg: Any):
        self.bus.publish('embodiment.result', {'joint_state': dict(self.last_joint_state), 'safety_status': dict(self.last_safety_status), 'control_profile': dict(self.last_profile), 'hardware_state': self.hardware.get_state().to_dict(), 'ts_ms': now_ms()})
