"""
Color Sorting Pick & Place Robot — Main Controller
CoppeliaSim + Python ZMQ Remote API

Usage:
    1. Open CoppeliaSim and load scenes/color_sort.ttt
    2. Press Play in CoppeliaSim
    3. Run: python src/main.py
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'zmqRemoteApi'))

from robot_controller import RobotController
from color_detector import ColorDetector

# ── Configuration ──────────────────────────────────────────────────────────────
PICKUP_ZONE    = [0.0, 0.5, 0.05]   # Where blocks arrive from conveyor
HOVER_HEIGHT   = 0.12               # Height above target before descend
MOTION_DELAY   = 0.45               # Fast and responsive IK motion (no lag!)

# Drop positions for each color bin (x, y, z)
DROP_ZONES = {
    'red':    [ 0.40, -0.35, 0.085],
    'green':  [ 0.45, -0.12, 0.085],
    'blue':   [ 0.45,  0.12, 0.085],
    'yellow': [ 0.35,  0.32, 0.085],
}
# ───────────────────────────────────────────────────────────────────────────────


def hover_above(pos, height=HOVER_HEIGHT):
    """Return a position directly above a given XYZ."""
    return [pos[0], pos[1], pos[2] + height]


def print_scoreboard(counts):
    total = sum(counts.values())
    print("\n" + "="*56)
    print("             COLOR SORTING SCOREBOARD")
    print("="*56)
    print(f"  [RED]    Red Bin    (x: 0.40, y: -0.35) :  {counts['red']:2d} blocks")
    print(f"  [GREEN]  Green Bin  (x: 0.45, y: -0.12) :  {counts['green']:2d} blocks")
    print(f"  [BLUE]   Blue Bin   (x: 0.45, y:  0.12) :  {counts['blue']:2d} blocks")
    print(f"  [YELLOW] Yellow Bin (x: 0.35, y:  0.32) :  {counts['yellow']:2d} blocks")
    print("-" * 56)
    print(f"  TOTAL BLOCKS SORTED: {total:2d}")
    print("="*56 + "\n", flush=True)


def start_keyboard_listener(robot: RobotController):
    import threading
    def listener():
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if not cmd:
                    continue
                color_map = {
                    'r': 'red', 'red': 'red',
                    'g': 'green', 'green': 'green',
                    'b': 'blue', 'blue': 'blue',
                    'y': 'yellow', 'yellow': 'yellow',
                }
                if cmd in color_map:
                    chosen = color_map[cmd]
                    robot.sim.setStringSignal('user_spawn_request', chosen)
                    print(f"  -> [USER INPUT] Spawn requested: {chosen.upper()} block!\n", flush=True)
                elif cmd == 'help':
                    print("  [HELP] Type: r (Red), g (Green), b (Blue), y (Yellow) + Enter to spawn that block.\n", flush=True)
            except Exception:
                break
    t = threading.Thread(target=listener, daemon=True)
    t.start()


def run_sorting_loop(robot: RobotController, detector: ColorDetector, initial_spawn=None, queue=None):
    print("[INFO] Color sorting loop started. Press Ctrl+C to stop.")
    print("[TIP]  YOU DECIDE WHICH BLOCK COMES NEXT:")
    print("       1. Click [Spawn RED/GREEN/BLUE/YELLOW] in the CoppeliaSim 3D Dashboard")
    print("       2. Or type r, g, b, or y + Enter right here in the terminal!\n", flush=True)
    sorted_counts = {'red': 0, 'green': 0, 'blue': 0, 'yellow': 0}

    # Start terminal keyboard listener
    start_keyboard_listener(robot)

    # If user provided a specific spawn queue or block via CLI
    pending_queue = []
    if initial_spawn:
        pending_queue.append(initial_spawn)
    if queue:
        pending_queue.extend([q.strip().lower() for q in queue.split(',') if q.strip()])

    if pending_queue:
        # Pause background random auto-spawn so only the user's requested queue runs
        try:
            robot.sim.setInt32Signal('auto_spawn', 0)
        except Exception:
            pass

    while True:
        # If user specified blocks in queue, request next one
        if pending_queue:
            next_col = pending_queue.pop(0)
            robot.sim.setStringSignal('user_spawn_request', next_col)
            print(f"  -> [QUEUE] Spawning requested block: {next_col.upper()}", flush=True)

        # ── 1. Wait for a block at the pickup sensor ───────────────────────
        block_handle = robot.wait_for_block()
        if block_handle is None:
            time.sleep(0.05)
            continue

        block_pos = robot.get_object_position(block_handle)
        print(f"[INFO] Block arrived at pickup zone: {[round(x, 3) for x in block_pos]}")

        # ── 2. Detect color via vision sensor ─────────────────────────────
        color = detector.detect_color(block_handle)
        if color not in DROP_ZONES:
            print(f"[WARN] Unknown color '{color}', skipping block.")
            continue
        print(f"[INFO] Detected color: {color.upper()}")

        # ── 3. Pick ────────────────────────────────────────────────────────
        # Block center is at block_pos[2]. Top surface is at block_pos[2] + 0.025.
        # Flange descends to block_pos[2] + 0.026 to contact the top face without knocking the block.
        pick_hover   = [block_pos[0], block_pos[1], block_pos[2] + 0.16]
        pick_surface = [block_pos[0], block_pos[1], block_pos[2] + 0.026]

        robot.move_to(pick_hover)                   # hover above block
        robot.move_to(pick_surface)                 # descend gently to top surface
        robot.grasp(block_handle)                   # securely attach block centered
        robot.move_to(pick_hover)                   # lift block into air

        # ── 4. Transport ───────────────────────────────────────────────────
        # Dynamically query bin center if available
        bin_h = robot.sim.getObject(f'/Bin{color.capitalize()}', {'noError': True})
        if bin_h != -1:
            bx, by, bz = robot.sim.getObjectPosition(bin_h, -1)
            drop_pos   = [bx, by, bz + 0.085]
            drop_hover = [bx, by, bz + 0.22]
        else:
            drop_pos   = DROP_ZONES[color]
            drop_hover = hover_above(drop_pos, height=0.14)

        robot.move_to(drop_hover)                   # hover above bin
        robot.move_to(drop_pos)                     # lower block into bin cavity

        # ── 5. Place ───────────────────────────────────────────────────────
        time.sleep(0.05)
        robot.release()                             # release block inside bin
        time.sleep(0.05)
        robot.move_to(drop_hover)                   # retract cleanly

        # ── 6. Return to home ─────────────────────────────────────────────
        robot.go_home()

        sorted_counts[color] += 1
        # Update in-scene CoppeliaSim dashboard
        try:
            robot.sim.setStringSignal('sorted_counts', f"{sorted_counts['red']},{sorted_counts['green']},{sorted_counts['blue']},{sorted_counts['yellow']}")
        except Exception:
            pass

        print_scoreboard(sorted_counts)


def is_coppelia_running(host='localhost', port=23000, timeout=1.5):
    """Check if CoppeliaSim ZeroMQ remote API is listening."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Color Sorting Pick & Place Robot")
    parser.add_argument('--host', type=str, default='localhost', help="Host IP for CoppeliaSim (default: localhost)")
    parser.add_argument('--port', type=int, default=23000, help="ZeroMQ remote API port (default: 23000)")
    parser.add_argument('--web', action='store_true', help="Launch localhost web dashboard on http://localhost:8080")
    parser.add_argument('--coppelia', action='store_true', help="Force CoppeliaSim 3D mode")
    parser.add_argument('--sim', '--standalone', action='store_true', dest='sim', help="Run standalone visual simulation (Pygame + OpenCV)")
    parser.add_argument('--spawn', type=str, default=None, help="Immediately spawn a specific color block (red, green, blue, yellow)")
    parser.add_argument('--queue', type=str, default=None, help="Comma-separated block sequence, e.g. red,yellow,blue,green")
    args = parser.parse_args()

    print("=" * 55, flush=True)
    print("  Color Sorting Pick & Place Robot", flush=True)
    print("=" * 55, flush=True)

    if args.web:
        print("[INFO] Starting localhost web dashboard...", flush=True)
        from web_sim import run_web_server
        run_web_server(port=8080)
        return

    coppelia_online = is_coppelia_running(host=args.host, port=args.port)

    if args.sim or (not args.coppelia and not coppelia_online):
        if not args.sim and not coppelia_online:
            print(f"[INFO] CoppeliaSim not detected on {args.host}:{args.port}.", flush=True)
            print("[INFO] Launching standalone interactive visual simulation...", flush=True)
            print(f"[TIP]  To connect to CoppeliaSim: open CoppeliaSim on {args.host}:{args.port}")
            print("       and run with: python src/main.py --host <IP> --coppelia")
            print("       To view in your browser: python src/main.py --web\n", flush=True)
        from standalone_sim import run_standalone
        run_standalone()
        return

    # CoppeliaSim mode
    print(f"[INFO] Connecting to CoppeliaSim at {args.host}:{args.port}...", flush=True)
    robot = RobotController(host=args.host, port=args.port, motion_delay=MOTION_DELAY)

    try:
        robot.connect()
        detector = ColorDetector(robot.sim)
        robot.start_simulation()
        run_sorting_loop(robot, detector, initial_spawn=args.spawn, queue=args.queue)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping simulation...")
    except ConnectionError as e:
        print(f"\n[ERROR] {e}")
    finally:
        if robot.sim is not None:
            robot.stop_simulation()
            robot.disconnect()
        print("[INFO] Done.")


if __name__ == '__main__':
    main()
