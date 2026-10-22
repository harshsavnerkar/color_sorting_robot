# color_sorting_robot
A complete simulation of a robotic arm that picks colored blocks from a conveyor belt and sorts them into matching colored bins.


## Project Structure

```
color_sorting_robot/
├── scenes/
│   └── color_sort.ttt          ← CoppeliaSim scene (save here after building)
├── src/
│   ├── main.py                 ← Entry point — run this
│   ├── robot_controller.py     ← ZMQ API: motion, gripper, sensors
│   ├── color_detector.py       ← OpenCV HSV color classification
│   ├── build_scene.py          ← Auto-builds the CoppeliaSim scene
│   └── zmqRemoteApi/           ← ZMQ client (copy from CoppeliaSim install)
├── scripts/
│   ├── color_sort_scene.lua    ← Scene script: spawns blocks, drives conveyor
│   └── ur5_ik.lua              ← UR5 inverse kinematics script
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Software | Version | Link |
|----------|---------|------|
| CoppeliaSim EDU | 4.4+ | https://www.coppeliarobotics.com/downloads |
| Python | 3.8+ | https://www.python.org |

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Copy the ZMQ Remote API client

```bash
# From your CoppeliaSim installation:
cp -r <CoppeliaSim_dir>/programming/zmqRemoteApi/clients/python/src/ \
      src/zmqRemoteApi/
```

### 3. Build the scene (one-time setup)

Open CoppeliaSim (no scene loaded), then:

```bash
python src/build_scene.py
```

This creates all scene objects. Then in CoppeliaSim:
- Add a **UR5 robot** from: `Models → robots → non-mobile → UR5`
- Position it at `[0, 0, 0]`
- Attach `scripts/ur5_ik.lua` as a child script on the UR5
- Attach `scripts/color_sort_scene.lua` as a child script on a Dummy called `SceneManager`
- Save as `scenes/color_sort.ttt`

### 4. Run the simulation

```bash
# Terminal 1: Open CoppeliaSim and load scenes/color_sort.ttt, then press Play ▶

# Terminal 2:
python src/main.py
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                          │
│                                                                 │
│  ┌──────────────┐   ZMQ API    ┌─────────────────────────┐     │
│  │  Python       │◄────────────►│    CoppeliaSim Scene    │     │
│  │  Controller   │             │                         │     │
│  │               │             │  ┌──────────┐           │     │
│  │  main.py      │             │  │ Conveyor │ ──► blocks │     │
│  │  robot_       │             │  └──────────┘           │     │
│  │  controller   │             │       │                 │     │
│  │               │             │  ┌────▼─────┐           │     │
│  │  color_       │◄────image───│  │  Vision  │           │     │
│  │  detector     │             │  │  Sensor  │           │     │
│  │               │             │  └──────────┘           │     │
│  │  OpenCV HSV   │             │                         │     │
│  │  detection    │             │  ┌──────────┐           │     │
│  │               │────commands►│  │  UR5 Arm │           │     │
│  │               │             │  │  + IK    │           │     │
│  └──────────────┘             │  └──────────┘           │     │
│                                │                         │     │
│                                │  🔴 Bin   🟢 Bin  🔵 Bin │     │
│                                └─────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Sorting Pipeline (per block)

1. **Spawn** — Lua script spawns a random-color block on the conveyor
2. **Detect arrival** — Proximity sensor fires when block reaches pickup zone
3. **Color detection** — Vision sensor image → OpenCV HSV → color name
4. **Pick** — Python moves IK target → UR5 descends → gripper grasps block
5. **Place** — UR5 moves to matching color bin → releases block
6. **Repeat** — Conveyor resumes, next block spawns

---

## Scene Object Names

| Object | Scene Path | Purpose |
|--------|-----------|---------|
| Robot arm | `/UR5` | 6-DOF manipulator |
| IK target | `/IKTarget` | Drives end-effector pose |
| IK tip | `/UR5/ikTip` | End-effector reference |
| Proximity sensor | `/ProxSensor` | Detects block at pickup |
| Vision sensor | `/VisionSensor` | Captures color image |
| Conveyor joint | `/ConveyorBelt` | Controls belt speed |
| Spawn dummy | `/SpawnPoint` | Block spawn location |
| Bins | `/BinRed`, `/BinGreen`, `/BinBlue` | Destination bins |

---

## Configuration

Edit the top of `src/main.py`:

```python
PICKUP_ZONE    = [0.0, 0.5, 0.05]   # Where blocks arrive
HOVER_HEIGHT   = 0.15               # Lift height above objects
MOTION_DELAY   = 1.2                # Seconds to wait for IK motion

DROP_ZONES = {
    'red':    [0.50, -0.40, 0.05],
    'green':  [0.50,  0.00, 0.05],
    'blue':   [0.50,  0.40, 0.05],
}
```

Edit the top of `scripts/color_sort_scene.lua`:

```lua
local SPAWN_INTERVAL  = 4.0    -- seconds between blocks
local CONVEYOR_SPEED  = 0.08   -- m/s
local BLOCK_SIZE      = 0.05   -- meters
```

---

## Adding More Colors

1. Add to `COLORS` in `color_sort_scene.lua`:
```lua
{name='yellow', rgb={1.0, 0.85, 0.0}},
```

2. Add to `DROP_ZONES` in `main.py`:
```python
'yellow': [0.50, 0.70, 0.05],
```

3. HSV ranges for yellow are already in `color_detector.py`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ImportError: zmqRemoteApi` | Copy zmqRemoteApi from CoppeliaSim install into `src/zmqRemoteApi/` |
| `Object not found: /UR5` | Check your scene object names match those in `robot_controller.py` |
| Robot not moving | Ensure IK is set up: UR5 joints must be in IK mode |
| Wrong color detected | Run `ColorDetector.calibrate('red')` to tune HSV thresholds |
| Simulation too slow | Reduce rendering quality in CoppeliaSim → Simulation settings |

---

## Related Resources

- [CoppeliaSim Documentation](https://www.coppeliarobotics.com/helpFiles/)
- [ZMQ Remote API Guide](https://www.coppeliarobotics.com/helpFiles/en/zmqRemoteApiOverview.htm)
- [simIK Reference](https://www.coppeliarobotics.com/helpFiles/en/simIK.htm)
- [UR5 Model Info](https://www.universal-robots.com/products/ur5-robot/)

---

## License

MIT License — free to use, modify, and distribute.

