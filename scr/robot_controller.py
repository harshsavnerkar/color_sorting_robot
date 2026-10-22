"""
robot_controller.py
Handles all CoppeliaSim communication: connection, IK motion, gripper, sensors.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'zmqRemoteApi'))

try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
except ImportError:
    try:
        from zmqRemoteApi import RemoteAPIClient
    except ImportError:
        raise ImportError(
            "ZMQ Remote API not found.\n"
            "Install with: pip install coppeliasim-zmqremoteapi-client\n"
            "Or copy the zmqRemoteApi folder from:\n"
            "  <CoppeliaSim>/programming/zmqRemoteApi/clients/python/src/\n"
            "into src/zmqRemoteApi/"
        )


class RobotController:
    """
    Controls a robot arm in CoppeliaSim via ZMQ Remote API.

    Object names expected in your .ttt scene:
        /UR5              — robot arm root
        /UR5/ikTarget     — IK target dummy (drives end-effector)
        /UR5/gripper      — gripper model root
        /ProxSensor       — proximity sensor at conveyor pickup zone
        /VisionSensor     — vision sensor above conveyor
        /ConveyorBelt     — conveyor joint/motor

    Adjust these names to match your actual scene hierarchy.
    """

    SCENE_OBJECTS = {
        'robot':         '/UR5',
        'ik_target':     '/UR5/ikTarget',
        'gripper':       '/UR5/gripper',
        'prox_sensor':   '/ProxSensor',
        'vision_sensor': '/VisionSensor',
        'conveyor':      '/ConveyorBelt',
    }

    HOME_JOINT_ANGLES = [0, -30, 60, -30, -90, 0]   # degrees

    def __init__(self, host='localhost', port=23000, motion_delay=1.2):
        self.host         = host
        self.port         = port
        self.motion_delay = motion_delay
        self.client       = None
        self.sim          = None
        self.handles      = {}
        self._grasped     = None

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self):
        print(f"[INFO] Connecting to CoppeliaSim at {self.host}:{self.port} ...", flush=True)
        import socket
        try:
            with socket.create_connection((self.host, self.port), timeout=2.0):
                pass
        except (socket.timeout, ConnectionRefusedError, OSError):
            raise ConnectionError(
                f"Could not connect to CoppeliaSim at {self.host}:{self.port}.\n"
                "Please verify that CoppeliaSim is running with ZMQ remote API enabled (port 23000)."
            )
        self.client = RemoteAPIClient(host=self.host, port=self.port)
        self.sim    = self.client.getObject('sim')
        print("[INFO] Connected.")
        self._get_handles()

    def disconnect(self):
        self.client = None
        self.sim    = None
        print("[INFO] Disconnected.")

    def _get_handles(self):
        candidate_paths = {
            'robot':         ['/UR5'],
            'ik_target':     ['/IKTarget', '/UR5/ikTarget'],
            'gripper':       ['/UR5/gripper', '/gripper'],
            'prox_sensor':   ['/ProxSensor'],
            'vision_sensor': ['/VisionSensor'],
            'conveyor':      ['/ConveyorBelt'],
        }
        for name, paths in candidate_paths.items():
            self.handles[name] = None
            for path in paths:
                try:
                    h = self.sim.getObject(path)
                    if h != -1:
                        self.handles[name] = h
                        print(f"  [OK] Handle: {name} -> {path}")
                        break
                except Exception:
                    pass
            if self.handles[name] is None:
                print(f"  [WARN] Object not found in scene: {paths}")

    # ── Simulation lifecycle ───────────────────────────────────────────────────

    def start_simulation(self):
        # Ensure all UR5 shapes are static in physics engine so kinematic joints don't collapse
        robot = self.handles.get('robot')
        if robot:
            for h in self.sim.getObjectsInTree(robot):
                if self.sim.getObjectType(h) == self.sim.object_shape_type:
                    self.sim.setObjectInt32Param(h, self.sim.shapeintparam_static, 1)

        state = self.sim.getSimulationState()
        if state != self.sim.simulation_stopped:
            print("[INFO] Resetting simulation for fresh start...", flush=True)
            self.sim.stopSimulation()
            time.sleep(0.5)

        self.sim.startSimulation()
        time.sleep(0.5)
        print("[INFO] Simulation started cleanly.", flush=True)

    def stop_simulation(self):
        self.sim.stopSimulation()
        print("[INFO] Simulation stopped.")

    # ── Motion ─────────────────────────────────────────────────────────────────

    def move_to(self, position, orientation=None):
        """
        Move robot end-effector to world-space XYZ by repositioning the IK target.
        CoppeliaSim IK solver handles joint angles automatically.

        Args:
            position    : [x, y, z] in meters (world frame)
            orientation : [alpha, beta, gamma] Euler angles (radians). 
                          If None, points flange downward [0, pi, 0].
        """
        target = self.handles.get('ik_target')
        if target is None:
            print("[ERROR] IK target handle not found.")
            return

        self.sim.setObjectPosition(target, self.sim.handle_world, position)

        if orientation is not None:
            self.sim.setObjectOrientation(target, self.sim.handle_world, orientation)
        else:
            import math
            self.sim.setObjectOrientation(target, self.sim.handle_world, [0, math.pi, 0])

        time.sleep(self.motion_delay)

    def go_home(self):
        """Move robot to home configuration."""
        self.move_to([0.0, 0.3, 0.4])

    # ── Gripper ────────────────────────────────────────────────────────────────

    def grasp(self, object_handle):
        """Attach an object to the gripper (kinematic attachment with centered alignment)."""
        gripper = self.handles.get('gripper')
        if gripper is None:
            print("[WARN] No gripper handle — using direct parent attachment.")
            gripper = self.handles.get('robot')

        # Make object static while carried so it moves rigidly with gripper
        try:
            self.sim.setObjectInt32Param(object_handle, self.sim.shapeintparam_static, 1)
            self.sim.resetDynamicObject(object_handle)
        except Exception:
            pass

        # Align block center directly underneath gripper flange in world frame
        try:
            grip_p = self.sim.getObjectPosition(gripper, self.sim.handle_world)
            self.sim.setObjectPosition(object_handle, self.sim.handle_world, [grip_p[0], grip_p[1], grip_p[2] - 0.025])
            self.sim.setObjectOrientation(object_handle, self.sim.handle_world, [0, 0, 0])
        except Exception:
            pass

        self.sim.setObjectParent(object_handle, gripper, True)
        self._grasped = object_handle
        print(f"  [GRIP] Grasped object handle {object_handle} (centered to gripper)")

    def release(self):
        """Detach the currently held object, leaving it in world space with physics enabled."""
        if self._grasped is not None:
            h = self._grasped
            try:
                if self.sim.isHandleValid(h):
                    self.sim.setObjectParent(h, -1, True)
                    try:
                        self.sim.setObjectInt32Param(h, self.sim.shapeintparam_static, 0)
                        self.sim.resetDynamicObject(h)
                    except Exception:
                        pass
                    print(f"  [GRIP] Released object handle {h}")
            except Exception as e:
                print(f"  [WARN] Release warning: {e}")
            self._grasped = None

    # ── Sensing ────────────────────────────────────────────────────────────────

    def wait_for_block(self, timeout=30.0):
        """
        Poll proximity sensor until a block is detected or timeout.
        Returns the detected object handle, or None on timeout.
        """
        sensor = self.handles.get('prox_sensor')
        if sensor is None:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = self.sim.readProximitySensor(sensor)
                # result = (detectionState, distance, point, objectHandle, normalVector)
                if isinstance(result, (list, tuple)) and len(result) >= 4:
                    detected = result[0]
                    obj_handle = result[3]
                    if detected == 1:
                        if obj_handle > 0 and 'Block_' in self.sim.getObjectAlias(obj_handle):
                            return obj_handle
                        # Fallback: find block located near pickup zone (0, 0.5)
                        for h in self.sim.getObjectsInTree(self.sim.handle_scene):
                            alias = self.sim.getObjectAlias(h)
                            if 'Block_' in alias:
                                pos = self.sim.getObjectPosition(h, self.sim.handle_world)
                                if abs(pos[0] - 0.0) < 0.12 and abs(pos[1] - 0.5) < 0.15:
                                    return h
            except Exception as e:
                print(f"[WARN] Sensor read error: {e}")
            time.sleep(0.05)
        return None

    def get_object_position(self, handle):
        """Return [x, y, z] world position of an object."""
        return self.sim.getObjectPosition(handle, self.sim.handle_world)

    # ── Conveyor ───────────────────────────────────────────────────────────────

    def set_conveyor_speed(self, speed=0.1):
        """Set conveyor belt velocity (m/s)."""
        conveyor = self.handles.get('conveyor')
        if conveyor is not None:
            self.sim.setJointTargetVelocity(conveyor, speed)

    def stop_conveyor(self):
        self.set_conveyor_speed(0.0)

    def resume_conveyor(self, speed=0.1):
        self.set_conveyor_speed(speed)
