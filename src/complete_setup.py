"""
complete_setup.py
Fully automates the complete CoppeliaSim scene configuration:
- Loads UR5 if not loaded
- Renames joints to joint1..joint6
- Creates /UR5/ikTip and /UR5/gripper
- Attaches ur5_ik.lua to UR5
- Attaches color_sort_scene.lua to SceneManager
- Saves the scene to scenes/color_sort.ttt
"""

import os
import sys

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

def run_setup():
    print("[Setup] Connecting to CoppeliaSim...", flush=True)
    client = RemoteAPIClient()
    sim = client.getObject('sim')
    print("[Setup] Connected to CoppeliaSim successfully!", flush=True)

    # 1. Check or load UR5
    ur5 = sim.getObject('/UR5', {'noError': True})
    if ur5 == -1:
        app_path = sim.getStringParam(sim.stringparam_application_path)
        ur5_model_path = os.path.join(app_path, "models", "robots", "non-mobile", "UR5.ttm").replace("\\", "/")
        print(f"[Setup] Loading UR5 from {ur5_model_path} ...", flush=True)
        ur5 = sim.loadModel(ur5_model_path)
        sim.setObjectAlias(ur5, "UR5")
        sim.setObjectPosition(ur5, -1, [0.0, 0.0, 0.0])
    print(f"[Setup] UR5 handle: {ur5}", flush=True)

    # 2. Rename joints to joint1..joint6
    joints = [h for h in sim.getObjectsInTree(ur5) if sim.getObjectType(h) == sim.object_joint_type]
    print(f"[Setup] Found {len(joints)} joints in UR5.", flush=True)
    for i, j in enumerate(joints):
        name = f"joint{i+1}"
        sim.setObjectAlias(j, name)
        print(f"  Joint {i+1} named -> {name} (handle {j})", flush=True)

    # 3. Create /UR5/ikTip and /UR5/gripper
    connection = sim.getObject('/UR5/connection', {'noError': True})
    if connection == -1:
        connection = joints[-1]

    ik_tip = sim.getObject('/UR5/ikTip', {'noError': True})
    if ik_tip == -1:
        ik_tip = sim.createDummy(0.02, None)
        sim.setObjectAlias(ik_tip, 'ikTip')
        sim.setObjectParent(ik_tip, connection, False)
        sim.setObjectPosition(ik_tip, connection, [0.0, 0.0, 0.05])
        print(f"[Setup] Created /UR5/ikTip at tip (handle {ik_tip})", flush=True)
    else:
        print(f"[Setup] /UR5/ikTip already exists (handle {ik_tip})", flush=True)

    gripper = sim.getObject('/UR5/gripper', {'noError': True})
    if gripper == -1:
        gripper = sim.createDummy(0.02, None)
        sim.setObjectAlias(gripper, 'gripper')
        sim.setObjectParent(gripper, ik_tip, False)
        sim.setObjectPosition(gripper, ik_tip, [0.0, 0.0, 0.0])
        print(f"[Setup] Created /UR5/gripper (handle {gripper})", flush=True)
    else:
        print(f"[Setup] /UR5/gripper already exists (handle {gripper})", flush=True)

    # 4. Attach ur5_ik.lua to UR5
    ur5_lua_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "ur5_ik.lua")
    with open(ur5_lua_path, "r", encoding="utf-8") as f:
        ur5_lua_code = f.read()

    ur5_script = sim.getScript(sim.scripttype_childscript, ur5)
    if ur5_script != -1:
        sim.setScriptText(ur5_script, ur5_lua_code)
        print(f"[Setup] Updated child script on UR5 with ur5_ik.lua (script handle {ur5_script})", flush=True)
    else:
        ur5_script = sim.createScript(sim.scripttype_childscript, ur5_lua_code, 0)
        sim.associateScriptWithObject(ur5_script, ur5)
        print(f"[Setup] Attached new child script on UR5 with ur5_ik.lua (script handle {ur5_script})", flush=True)

    # 5. Attach color_sort_scene.lua to SceneManager
    scene_mgr = sim.getObject('/SceneManager')
    scene_lua_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "color_sort_scene.lua")
    with open(scene_lua_path, "r", encoding="utf-8") as f:
        scene_lua_code = f.read()

    sm_script = sim.getScript(sim.scripttype_childscript, scene_mgr)
    if sm_script == -1:
        sm_script = sim.addScript(sim.scripttype_childscript)
        sim.associateScriptWithObject(sm_script, scene_mgr)
    sim.setScriptText(sm_script, scene_lua_code)
    print(f"[Setup] Configured child script on SceneManager with color_sort_scene.lua (script handle {sm_script})", flush=True)

    # 6. Save scene to scenes/color_sort.ttt
    scene_save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scenes", "color_sort.ttt")).replace("\\", "/")
    sim.saveScene(scene_save_path)
    print(f"\n[Setup] SUCCESS! Scene saved to:\n  {scene_save_path}", flush=True)
    print("\nCoppeliaSim is now 100% configured and ready!", flush=True)


if __name__ == '__main__':
    run_setup()
