"""
fix_coppelia_scene.py
Fixes and perfects the complete CoppeliaSim scene:
1. Stops simulation.
2. Removes duplicate loose robot parts, stray blocks, and script dummies.
3. Anchors Floor, Conveyor, all 4 Bins (as hollow open boxes), and UR5 shapes as static.
4. Resizes VisionSensor to realistic small camera (0.04m, eliminates giant blue block).
5. Configures ProxSensor with proper range (0.20m) and radius (0.08m).
6. Sets up optimized ur5_ik.lua on UR5 and fast color_sort_scene.lua on SceneManager.
7. Sets initial home joint angles and target pose.
8. Saves scene to scenes/color_sort.ttt.
"""

import math
import os
import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

def fix():
    print("[Fix] Connecting to CoppeliaSim...", flush=True)
    client = RemoteAPIClient()
    sim = client.getObject('sim')

    # 1. Stop simulation
    sim.stopSimulation()
    time.sleep(0.5)
    print("[Fix] Simulation stopped.", flush=True)

    # 2. Remove duplicate loose arm parts (/joint1, /link1_visible) if outside UR5
    for name in ['/joint1', '/link1_visible']:
        h = sim.getObject(name, {'noError': True})
        if h != -1:
            parent = sim.getObjectParent(h)
            if parent == -1 or parent == sim.handle_scene:
                print(f"[Fix] Removing duplicate loose arm root: {name} (handle {h})", flush=True)
                sim.removeObject(h)

    # 3. Remove all spawned temporary blocks & duplicate script dummies
    removed_blocks = 0
    for h in sim.getObjectsInTree(sim.handle_scene):
        try:
            alias = sim.getObjectAlias(h)
            if 'Block_' in alias or 'cuboid' in alias.lower():
                sim.removeObject(h)
                removed_blocks += 1
            elif alias.lower() == 'script' and h != sim.getObject('/UR5', {'noError': True}):
                print(f"[Fix] Removed duplicate dummy: {alias} (handle {h})", flush=True)
                sim.removeObject(h)
        except Exception:
            pass
    print(f"[Fix] Removed {removed_blocks} spawned blocks/cuboids.", flush=True)

    # 4. Fix Floor
    floor = sim.getObject('/Floor', {'noError': True})
    if floor != -1:
        sim.setObjectPosition(floor, sim.handle_world, [0.0, 0.0, -0.01])
        sim.setObjectInt32Param(floor, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(floor, sim.shapeintparam_respondable, 1)
        print("[Fix] Floor anchored at Z=-0.01", flush=True)

    # 5. Fix Conveyor Surface
    conveyor = sim.getObject('/ConveyorSurface', {'noError': True})
    if conveyor != -1:
        sim.setObjectPosition(conveyor, sim.handle_world, [0.0, 0.5, 0.01])
        sim.setObjectInt32Param(conveyor, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(conveyor, sim.shapeintparam_respondable, 1)
        print("[Fix] ConveyorSurface anchored at Z=0.01", flush=True)

    # 6. Fix all 4 Bins as hollow open containers with Dummy roots for exact positioning
    bins_config = {
        'BinRed':    ([0.40, -0.35, 0.0], [1.0, 0.15, 0.15]),
        'BinGreen':  ([0.45, -0.12, 0.0], [0.15, 0.85, 0.15]),
        'BinBlue':   ([0.45,  0.12, 0.0], [0.15, 0.35, 1.0]),
        'BinYellow': ([0.35,  0.32, 0.0], [1.0,  0.85, 0.1]),
    }

    for name, (pos, col) in bins_config.items():
        old = sim.getObject('/' + name, {'noError': True})
        if old != -1:
            sim.removeObject(old)
        x, y, z_base = pos

        # Create root Dummy so getObjectPosition('/' + name) returns the exact center of opening
        root_dummy = sim.createDummy(0.04)
        sim.setObjectAlias(root_dummy, name)
        sim.setObjectPosition(root_dummy, sim.handle_world, [x, y, z_base])

        parts = []
        # Bottom plate (0.16 x 0.16 x 0.01)
        b = sim.createPureShape(0, 1+2, [0.16, 0.16, 0.01], 0, None)
        sim.setObjectPosition(b, sim.handle_world, [x, y, z_base + 0.005])
        parts.append(b)
        # 4 walls (0.06m tall, 0.01m thick)
        w1 = sim.createPureShape(0, 1+2, [0.01, 0.16, 0.06], 0, None)
        sim.setObjectPosition(w1, sim.handle_world, [x - 0.075, y, z_base + 0.035])
        parts.append(w1)
        w2 = sim.createPureShape(0, 1+2, [0.01, 0.16, 0.06], 0, None)
        sim.setObjectPosition(w2, sim.handle_world, [x + 0.075, y, z_base + 0.035])
        parts.append(w2)
        w3 = sim.createPureShape(0, 1+2, [0.14, 0.01, 0.06], 0, None)
        sim.setObjectPosition(w3, sim.handle_world, [x, y - 0.075, z_base + 0.035])
        parts.append(w3)
        w4 = sim.createPureShape(0, 1+2, [0.14, 0.01, 0.06], 0, None)
        sim.setObjectPosition(w4, sim.handle_world, [x, y + 0.075, z_base + 0.035])
        parts.append(w4)

        compound = sim.groupShapes(parts)
        sim.setObjectAlias(compound, f'{name}_mesh')
        sim.setShapeColor(compound, None, sim.colorcomponent_ambient_diffuse, col)
        sim.setObjectInt32Param(compound, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(compound, sim.shapeintparam_respondable, 1)
        sim.setObjectParent(compound, root_dummy, True)
        print(f"[Fix] Created hollow open bin: /{name} at {pos} (opening: 140x140mm)", flush=True)

    # 7. Anchor UR5 shapes as static so kinematic joints never collapse
    ur5 = sim.getObject('/UR5', {'noError': True})
    if ur5 != -1:
        for h in sim.getObjectsInTree(ur5):
            if sim.getObjectType(h) == sim.object_shape_type:
                sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
        print("[Fix] UR5 shapes anchored as static (kinematic rock-solid stability).", flush=True)

    # 8. Configure /VisionSensor with small 0.04m visual size (eliminates giant blue cube)
    old_vs = sim.getObject('/VisionSensor', {'noError': True})
    if old_vs != -1:
        sim.removeObject(old_vs)
    v_int = [64, 64, 0, 0]
    v_float = [0.01, 1.0, 60 * math.pi / 180, 0.04, 0.04, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    new_vs = sim.createVisionSensor(0, v_int, v_float)
    sim.setObjectAlias(new_vs, 'VisionSensor')
    sim.setObjectPosition(new_vs, sim.handle_world, [0.0, 0.5, 0.35])
    sim.setObjectOrientation(new_vs, sim.handle_world, [math.pi, 0, 0])
    print("[Fix] /VisionSensor re-created with compact size at [0.0, 0.5, 0.35].", flush=True)

    # 9. Configure /ProxSensor with range 0.20m and radius 0.08m
    old_prox = sim.getObject('/ProxSensor', {'noError': True})
    if old_prox != -1:
        sim.removeObject(old_prox)
    int_params = [0, 0, 0, 0, 0, 0, 0, 0]
    float_params = [0.0, 0.20, 0.08, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    prox = sim.createProximitySensor(
        sim.proximitysensor_cylinder_subtype,
        sim.objectspecialproperty_detectable_all,
        0,
        int_params,
        float_params
    )
    sim.setObjectAlias(prox, 'ProxSensor')
    sim.setObjectPosition(prox, sim.handle_world, [0.0, 0.5, 0.15])
    sim.setObjectOrientation(prox, sim.handle_world, [math.pi, 0, 0])
    print("[Fix] /ProxSensor re-created with 0.20m range at [0.0, 0.5, 0.15].", flush=True)

    # 10. Push scripts/ur5_ik.lua to UR5
    ur5_lua_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "ur5_ik.lua")
    with open(ur5_lua_path, "r", encoding="utf-8") as f:
        ur5_code = f.read()

    ur5_sc = sim.getScript(sim.scripttype_childscript, ur5)
    if ur5_sc == -1:
        ur5_sc = sim.addScript(sim.scripttype_childscript)
        sim.associateScriptWithObject(ur5_sc, ur5)
    sim.setScriptStringParam(ur5_sc, sim.scriptstringparam_text, ur5_code)
    print(f"[Fix] Attached ur5_ik.lua to /UR5 (script {ur5_sc}).", flush=True)

    # 11. Push scripts/color_sort_scene.lua to SceneManager
    scene_mgr = sim.getObject('/SceneManager', {'noError': True})
    scene_lua_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "color_sort_scene.lua")
    with open(scene_lua_path, "r", encoding="utf-8") as f:
        scene_code = f.read()

    sm_sc = sim.getScript(sim.scripttype_childscript, scene_mgr)
    if sm_sc == -1:
        sm_sc = sim.addScript(sim.scripttype_childscript)
        sim.associateScriptWithObject(sm_sc, scene_mgr)
    sim.setScriptStringParam(sm_sc, sim.scriptstringparam_text, scene_code)
    print(f"[Fix] Attached color_sort_scene.lua to /SceneManager (script {sm_sc}).", flush=True)

    # 12. Reset IKTarget pose and UR5 joints to home
    target = sim.getObject('/IKTarget', {'noError': True})
    if target != -1:
        sim.setObjectPosition(target, sim.handle_world, [0.0, 0.3, 0.4])
        sim.setObjectOrientation(target, sim.handle_world, [0, math.pi, 0])
        print("[Fix] /IKTarget set to home pose [0.0, 0.3, 0.4].", flush=True)

    home_deg = [0, -30, 60, -30, -90, 0]
    for i, d in enumerate(home_deg):
        j = sim.getObject(f'/UR5/joint{i+1}', {'noError': True})
        if j != -1:
            sim.setJointPosition(j, math.radians(d))
            sim.setJointMode(j, sim.jointmode_kinematic, 0)
    print("[Fix] UR5 joints positioned to home pose.", flush=True)

    # 13. Save scene
    scene_save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scenes", "color_sort.ttt")).replace("\\", "/")
    sim.saveScene(scene_save_path)
    print(f"\n[Fix] [SUCCESS] Perfect scene saved to:\n  {scene_save_path}\n", flush=True)

if __name__ == '__main__':
    fix()
