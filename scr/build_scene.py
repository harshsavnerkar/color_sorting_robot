"""
build_scene.py  — CoppeliaSim 4.10 compatible
Run with CoppeliaSim open (no scene loaded):
    python src/build_scene.py
"""

import sys, os, time, math
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


def build_scene():
    print("[Build] Connecting to CoppeliaSim ...", flush=True)
    import socket
    try:
        with socket.create_connection(('localhost', 23000), timeout=2.0):
            pass
    except (socket.timeout, ConnectionRefusedError, OSError):
        print("\n[ERROR] Could not connect to CoppeliaSim at localhost:23000.")
        print("Please ensure CoppeliaSim is open and running before running this script.")
        return

    client = RemoteAPIClient()
    sim    = client.getObject('sim')
    print("[Build] Connected.\n")

    sim.stopSimulation()
    time.sleep(0.5)

    # ── 1. Floor ──────────────────────────────────────────────────────────────
    print("[Build] Creating floor ...")
    floor = sim.createPureShape(0, 1+2, [2.0, 2.0, 0.01], 0, None)
    sim.setObjectAlias(floor, 'Floor')
    sim.setObjectPosition(floor, sim.handle_world, [0.0, 0.0, -0.005])
    sim.setShapeColor(floor, None, sim.colorcomponent_ambient_diffuse, [0.6, 0.6, 0.6])

    # ── 2. Conveyor surface ───────────────────────────────────────────────────
    print("[Build] Creating conveyor ...")
    conveyor = sim.createPureShape(0, 1+2, [1.0, 0.2, 0.02], 0, None)
    sim.setObjectPosition(conveyor, sim.handle_world, [0.0, 0.5, 0.01])
    sim.setShapeColor(conveyor, None, sim.colorcomponent_ambient_diffuse, [0.3, 0.3, 0.3])
    sim.setObjectAlias(conveyor, 'ConveyorSurface')

    # Conveyor joint — use jointmode_kinematic (mode 1) for 4.10
    conveyor_joint = sim.createJoint(
        sim.joint_prismatic_subtype, sim.jointmode_kinematic, 0
    )
    sim.setObjectAlias(conveyor_joint, 'ConveyorBelt')
    sim.setObjectPosition(conveyor_joint, sim.handle_world, [0.0, 0.5, 0.02])

    # ── 3. Proximity sensor ───────────────────────────────────────────────────
    print("[Build] Creating proximity sensor ...")
    # For 4.10: use sim.createProximitySensor with correct table sizes
    # intParams (8 values) and floatParams (15 values) for cylinder subtype
    int_params   = [0, 0, 0, 0, 0, 0, 0, 0]
    float_params = [0.0, 0.0, 0.05, 0.0, 0.0, 0.0,
                    0.05, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    prox = sim.createProximitySensor(
        sim.proximitysensor_cylinder_subtype,
        sim.objectspecialproperty_detectable_all,
        0,
        int_params,
        float_params
    )
    sim.setObjectAlias(prox, 'ProxSensor')
    sim.setObjectPosition(prox, sim.handle_world, [0.0, 0.5, 0.08])
    sim.setObjectOrientation(prox, sim.handle_world, [math.pi, 0, 0])

    # ── 4. Vision sensor ──────────────────────────────────────────────────────
    print("[Build] Creating vision sensor ...")
    # intParams (4 values), floatParams (11 values) for 4.10
    v_int    = [64, 64, 0, 0]
    v_float  = [0.01, 10.0, 60 * math.pi / 180,
                0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    vision = sim.createVisionSensor(0, v_int, v_float)
    sim.setObjectAlias(vision, 'VisionSensor')
    sim.setObjectPosition(vision, sim.handle_world, [0.0, 0.5, 0.40])
    sim.setObjectOrientation(vision, sim.handle_world, [math.pi, 0, 0])

    # ── 5. Spawn point dummy ──────────────────────────────────────────────────
    spawn = sim.createDummy(0.02, None)
    sim.setObjectAlias(spawn, 'SpawnPoint')
    sim.setObjectPosition(spawn, sim.handle_world, [-0.45, 0.5, 0.04])

    # ── 6. Colored destination bins ───────────────────────────────────────────
    print("[Build] Creating color bins ...")
    bins_config = [
        ('BinRed',    [1.0, 0.1,  0.1], [ 0.5, -0.40, 0.0]),
        ('BinGreen',  [0.1, 0.8,  0.1], [ 0.5,  0.00, 0.0]),
        ('BinBlue',   [0.1, 0.3,  1.0], [ 0.5,  0.40, 0.0]),
        ('BinYellow', [1.0, 0.85, 0.0], [ 0.5,  0.70, 0.0]),
    ]
    for name, color, pos in bins_config:
        bin_h = sim.createPureShape(0, 1+2, [0.12, 0.12, 0.08], 0, None)
        sim.setObjectAlias(bin_h, name)
        sim.setObjectPosition(bin_h, sim.handle_world, pos)
        sim.setShapeColor(bin_h, None, sim.colorcomponent_ambient_diffuse, color)

    # ── 7. IK Target dummy ────────────────────────────────────────────────────
    ik_target = sim.createDummy(0.03, None)
    sim.setObjectAlias(ik_target, 'IKTarget')
    sim.setObjectPosition(ik_target, sim.handle_world, [0.0, 0.3, 0.4])

    # ── 8. SceneManager dummy (for Lua script) ────────────────────────────────
    scene_mgr = sim.createDummy(0.01, None)
    sim.setObjectAlias(scene_mgr, 'SceneManager')
    sim.setObjectPosition(scene_mgr, sim.handle_world, [0.0, 0.0, 0.5])

    print("""
[Build] [SUCCESS] Scene built successfully!

NEXT STEPS in CoppeliaSim:
  1. Add UR5: Model browser -> robots -> non-mobile -> UR5
     Position it at [0, 0, 0]
  2. Right-click UR5 -> Add -> Associated child script
     Paste contents of: scripts/ur5_ik.lua
  3. Right-click SceneManager -> Add -> Associated child script
     Paste contents of: scripts/color_sort_scene.lua
  4. File -> Save scene as -> scenes/color_sort.ttt
  5. Press Play, then run: python src/main.py --coppelia
""")


if __name__ == '__main__':
    build_scene()
