"""
clean_scene.py
Creates a completely clean, pristine CoppeliaSim scene:
- Deletes any duplicate objects
- Correctly sizes and positions conveyor, sensors, and the 4 destination bins
- Configures UR5 with IK scripts and SceneManager with spawner scripts
- Saves cleanly to scenes/color_sort.ttt
"""

import os
import sys
import math
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

def reset_and_build_clean_scene():
    print("[CleanScene] Connecting to CoppeliaSim...", flush=True)
    client = RemoteAPIClient()
    sim = client.getObject('sim')
    print("[CleanScene] Connected.", flush=True)

    # Stop simulation if running
    sim.stopSimulation()
    import time
    time.sleep(0.5)

    # Delete existing custom objects to avoid duplicates
    keywords = ['Floor', 'Conveyor', 'Prox', 'Vision', 'Spawn', 'Bin', 'IKTarget', 'SceneManager', 'UR5', 'Block_', 'box']
    for h in sim.getObjectsInTree(sim.handle_scene):
        try:
            alias = sim.getObjectAlias(h)
            if any(k in alias for k in keywords):
                sim.removeObject(h)
        except Exception:
            pass

    time.sleep(0.3)
    print("[CleanScene] Removed previous objects.", flush=True)

    # 1. Floor (Static + Respondable: options = 1+2+8, mass = 0)
    floor = sim.createPureShape(0, 1+2+8, [2.0, 2.0, 0.02], 0.0, None)
    sim.setObjectAlias(floor, 'Floor')
    sim.setObjectPosition(floor, sim.handle_world, [0.0, 0.0, -0.01])
    sim.setShapeColor(floor, None, sim.colorcomponent_ambient_diffuse, [0.7, 0.7, 0.7])

    # 2. Conveyor Belt
    conveyor = sim.createPureShape(0, 1+2+8, [1.0, 0.22, 0.02], 0.0, None)
    sim.setObjectAlias(conveyor, 'ConveyorSurface')
    sim.setObjectPosition(conveyor, sim.handle_world, [0.0, 0.5, 0.01])
    sim.setShapeColor(conveyor, None, sim.colorcomponent_ambient_diffuse, [0.25, 0.25, 0.25])

    conveyor_joint = sim.createJoint(sim.joint_prismatic_subtype, sim.jointmode_kinematic, 0)
    sim.setObjectAlias(conveyor_joint, 'ConveyorBelt')
    sim.setObjectPosition(conveyor_joint, sim.handle_world, [0.0, 0.5, 0.02])

    # 3. Proximity Sensor
    int_params   = [0, 0, 0, 0, 0, 0, 0, 0]
    float_params = [0.0, 0.0, 0.05, 0.0, 0.0, 0.0, 0.05, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    prox = sim.createProximitySensor(
        sim.proximitysensor_cylinder_subtype,
        sim.objectspecialproperty_detectable_all,
        0, int_params, float_params
    )
    sim.setObjectAlias(prox, 'ProxSensor')
    sim.setObjectPosition(prox, sim.handle_world, [0.0, 0.5, 0.08])
    sim.setObjectOrientation(prox, sim.handle_world, [math.pi, 0, 0])

    # 4. Vision Sensor
    v_int   = [64, 64, 0, 0]
    v_float = [0.01, 10.0, 60 * math.pi / 180, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    vision = sim.createVisionSensor(0, v_int, v_float)
    sim.setObjectAlias(vision, 'VisionSensor')
    sim.setObjectPosition(vision, sim.handle_world, [0.0, 0.5, 0.40])
    sim.setObjectOrientation(vision, sim.handle_world, [math.pi, 0, 0])

    # 5. Spawn Point
    spawn = sim.createDummy(0.02, None)
    sim.setObjectAlias(spawn, 'SpawnPoint')
    sim.setObjectPosition(spawn, sim.handle_world, [-0.45, 0.5, 0.04])

    # 6. Destination Bins (Static + Respondable: options = 1+2+8, mass = 0)
    bins_config = [
        ('BinRed',    [1.0, 0.15, 0.15], [0.5, -0.40, 0.03]),
        ('BinGreen',  [0.15, 0.85, 0.15], [0.5,  0.00, 0.03]),
        ('BinBlue',   [0.15, 0.35, 1.0],  [0.5,  0.40, 0.03]),
        ('BinYellow', [1.0,  0.85, 0.1],  [0.5,  0.70, 0.03]),
    ]
    for name, color, pos in bins_config:
        bin_h = sim.createPureShape(0, 1+2+8, [0.14, 0.14, 0.06], 0.0, None)
        sim.setObjectAlias(bin_h, name)
        sim.setObjectPosition(bin_h, sim.handle_world, pos)
        sim.setShapeColor(bin_h, None, sim.colorcomponent_ambient_diffuse, color)

    # 7. IK Target
    ik_target = sim.createDummy(0.03, None)
    sim.setObjectAlias(ik_target, 'IKTarget')
    sim.setObjectPosition(ik_target, sim.handle_world, [0.0, 0.3, 0.4])

    # 8. SceneManager Dummy
    scene_mgr = sim.createDummy(0.01, None)
    sim.setObjectAlias(scene_mgr, 'SceneManager')
    sim.setObjectPosition(scene_mgr, sim.handle_world, [0.0, 0.0, 0.5])

    # 9. Load UR5 Robot
    app_path = sim.getStringParam(sim.stringparam_application_path)
    ur5_model_path = os.path.join(app_path, "models", "robots", "non-mobile", "UR5.ttm").replace("\\", "/")
    print(f"[CleanScene] Loading UR5 from {ur5_model_path} ...", flush=True)
    ur5 = sim.loadModel(ur5_model_path)
    sim.setObjectAlias(ur5, "UR5")
    sim.setObjectPosition(ur5, -1, [0.0, 0.0, 0.0])

    # Rename 6 joints
    joints = [h for h in sim.getObjectsInTree(ur5) if sim.getObjectType(h) == sim.object_joint_type]
    for i, j in enumerate(joints):
        sim.setObjectAlias(j, f"joint{i+1}")

    # Tip & Gripper
    connection = sim.getObject('/UR5/connection', {'noError': True})
    if connection == -1:
        connection = joints[-1]
    ik_tip = sim.createDummy(0.02, None)
    sim.setObjectAlias(ik_tip, 'ikTip')
    sim.setObjectParent(ik_tip, connection, False)
    sim.setObjectPosition(ik_tip, connection, [0.0, 0.0, 0.05])

    gripper = sim.createDummy(0.02, None)
    sim.setObjectAlias(gripper, 'gripper')
    sim.setObjectParent(gripper, ik_tip, False)
    sim.setObjectPosition(gripper, ik_tip, [0.0, 0.0, 0.0])

    # 10. Attach Lua Scripts
    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    with open(os.path.join(scripts_dir, "ur5_ik.lua"), "r", encoding="utf-8") as f:
        ur5_code = f.read()
    ur5_script = sim.getScript(sim.scripttype_childscript, ur5)
    if ur5_script != -1:
        sim.setScriptText(ur5_script, ur5_code)
    else:
        ur5_script = sim.addScript(sim.scripttype_childscript)
        sim.associateScriptWithObject(ur5_script, ur5)
        sim.setScriptText(ur5_script, ur5_code)

    with open(os.path.join(scripts_dir, "color_sort_scene.lua"), "r", encoding="utf-8") as f:
        scene_code = f.read()
    sm_script = sim.getScript(sim.scripttype_childscript, scene_mgr)
    if sm_script != -1:
        sim.setScriptText(sm_script, scene_code)
    else:
        sm_script = sim.addScript(sim.scripttype_childscript)
        sim.associateScriptWithObject(sm_script, scene_mgr)
        sim.setScriptText(sm_script, scene_code)

    # 11. Save Clean Scene
    scene_save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scenes", "color_sort.ttt")).replace("\\", "/")
    sim.saveScene(scene_save_path)
    print(f"\n[CleanScene] [SUCCESS] Clean scene created and saved to:\n  {scene_save_path}", flush=True)

if __name__ == '__main__':
    reset_and_build_clean_scene()
