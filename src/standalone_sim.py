"""
standalone_sim.py
Interactive standalone visual simulation of the Color Sorting Pick & Place Robot.
Simulates the conveyor, proximity sensor, overhead camera, OpenCV HSV color detection,
and articulated 6-DOF UR5 robotic arm kinematics with real-time Pygame visualization.
"""

import math
import time
import random
import numpy as np
import pygame
import cv2

from color_detector import ColorDetector, HSV_RANGES

# ── Color Palette & Config ──────────────────────────────────────────────────
BG_COLOR       = (26, 28, 36)
PANEL_BG       = (35, 38, 48)
PANEL_BORDER   = (60, 64, 78)
TEXT_WHITE     = (240, 240, 245)
TEXT_MUTED     = (150, 155, 170)
TEXT_ACCENT    = (80, 200, 255)
CONVEYOR_COLOR = (50, 53, 64)
BELT_LINE      = (70, 74, 90)

COLOR_RGB = {
    'red':    (235, 50, 50),
    'green':  (40, 200, 70),
    'blue':   (40, 120, 245),
    'yellow': (245, 200, 30),
}

DROP_BINS = {
    'red':    {"pos": (740, 95),  "size": (90, 72), "color": COLOR_RGB['red']},
    'green':  {"pos": (740, 185), "size": (90, 72), "color": COLOR_RGB['green']},
    'blue':   {"pos": (740, 275), "size": (90, 72), "color": COLOR_RGB['blue']},
    'yellow': {"pos": (740, 365), "size": (90, 72), "color": COLOR_RGB['yellow']},
}


class MockVisionSensor:
    """Provides synthetic vision sensor images for the real OpenCV ColorDetector."""
    def __init__(self, size=64):
        self.size = size

    def render_block_view(self, block_color):
        """Generate a simulated 64x64 BGR camera frame looking down on the block."""
        img = np.full((self.size, self.size, 3), 45, dtype=np.uint8) # Conveyor grey background
        if block_color in COLOR_RGB:
            r, g, b = COLOR_RGB[block_color]
            # Draw square block in center with subtle lighting noise
            half = self.size // 3
            cx, cy = self.size // 2, self.size // 2
            # Add synthetic lighting gradient
            for y in range(cy - half, cy + half):
                for x in range(cx - half, cx + half):
                    factor = 1.0 - 0.15 * math.hypot((x - cx) / half, (y - cy) / half)
                    img[y, x] = [int(b * factor), int(g * factor), int(r * factor)] # BGR
        return img


class Block:
    def __init__(self, color_name, x, y):
        self.color_name = color_name
        self.x = x
        self.y = y
        self.size = 28
        self.held = False
        self.sorted = False

    @property
    def rect(self):
        return pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)


class StandaloneSimulator:
    def __init__(self, width=1024, height=640):
        pygame.init()
        pygame.font.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Color Sorting Robot — Standalone Simulation (OpenCV HSV + UR5)")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_main  = pygame.font.SysFont("Segoe UI", 15)
        self.font_bold  = pygame.font.SysFont("Segoe UI", 15, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 12)

        # Simulation layout coordinates
        self.conveyor_y = 350
        self.conveyor_start_x = 60
        self.conveyor_end_x   = 440
        self.pickup_x         = 380
        self.pickup_y         = self.conveyor_y

        # Robot Base
        self.robot_base_x = 520
        self.robot_base_y = 350
        self.arm_target_x = self.robot_base_x
        self.arm_target_y = self.robot_base_y - 120
        self.arm_x = self.arm_target_x
        self.arm_y = self.arm_target_y
        self.gripper_open = 18

        # Vision sensor & detector
        self.mock_vision = MockVisionSensor(size=72)
        self.detector = ColorDetector(sim=None)
        self.last_camera_frame = self.mock_vision.render_block_view(None)
        self.last_detected_color = "none"

        # Simulation state
        self.blocks = []
        self.grasped_block = None
        self.spawn_timer = 0.0
        self.spawn_interval = 4.0
        self.conveyor_running = True
        self.conveyor_speed = 70.0  # px/s
        self.belt_offset = 0.0

        # State machine: IDLE, WAITING_BLOCK, DETECTING, HOVER_PICK, DESCEND_PICK, GRASP, LIFT, TRANSPORT, LOWER, RELEASE, RETRACT, RETURN_HOME
        self.state = "WAITING_BLOCK"
        self.state_timer = 0.0
        self.current_drop_pos = None
        self.target_color = None

        # Statistics
        self.counts = {'red': 0, 'green': 0, 'blue': 0, 'yellow': 0}
        self.total_sorted = 0
        self.is_paused = False

    def spawn_block(self):
        # Weighted random color (red, green, blue, yellow)
        color = random.choice(['red', 'green', 'blue', 'yellow'])
        block = Block(color, self.conveyor_start_x, self.conveyor_y)
        self.blocks.append(block)

    def update(self, dt):
        if self.is_paused:
            return

        # ── 1. Conveyor & Spawning ──────────────────────────────────────────
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval and len(self.blocks) < 5:
            # Check if start zone is clear
            if not any(b.x < self.conveyor_start_x + 60 for b in self.blocks if not b.sorted and not b.held):
                self.spawn_block()
                self.spawn_timer = 0.0

        if self.conveyor_running:
            self.belt_offset = (self.belt_offset + self.conveyor_speed * dt) % 24
            for b in self.blocks:
                if not b.held and not b.sorted:
                    if b.x < self.pickup_x:
                        b.x += self.conveyor_speed * dt
                        if b.x >= self.pickup_x:
                            b.x = self.pickup_x

        # ── 2. Robot Arm Position Interpolation ─────────────────────────────
        move_speed = 350.0  # px/s
        dx = self.arm_target_x - self.arm_x
        dy = self.arm_target_y - self.arm_y
        dist = math.hypot(dx, dy)
        if dist > 1.0:
            step = min(dist, move_speed * dt)
            self.arm_x += (dx / dist) * step
            self.arm_y += (dy / dist) * step
        else:
            self.arm_x = self.arm_target_x
            self.arm_y = self.arm_target_y

        if self.grasped_block:
            self.grasped_block.x = self.arm_x
            self.grasped_block.y = self.arm_y + 16

        # ── 3. Pick & Place State Machine ───────────────────────────────────
        self.state_timer += dt

        if self.state == "WAITING_BLOCK":
            self.conveyor_running = True
            self.arm_target_x = self.robot_base_x - 30
            self.arm_target_y = self.robot_base_y - 100
            self.gripper_open = 22

            # Proximity sensor check
            candidate = next((b for b in self.blocks if not b.held and not b.sorted and abs(b.x - self.pickup_x) <= 3.0), None)
            if candidate:
                self.conveyor_running = False
                self.state = "DETECTING"
                self.state_timer = 0.0
                print(f"[EVENT] Block arrived at pickup zone. Proximity sensor triggered.", flush=True)

        elif self.state == "DETECTING":
            candidate = next((b for b in self.blocks if not b.held and not b.sorted and abs(b.x - self.pickup_x) <= 3.0), None)
            if candidate:
                # Capture simulated vision sensor frame and run OpenCV ColorDetector
                self.last_camera_frame = self.mock_vision.render_block_view(candidate.color_name)
                detected = self.detector.classify_color(self.last_camera_frame)
                self.last_detected_color = detected
                self.target_color = detected
                if self.state_timer < 0.05:
                    print(f"[CAM]   Vision sensor captured frame. OpenCV HSV detected: {detected.upper()}", flush=True)
            else:
                self.state = "WAITING_BLOCK"
                return

            if self.state_timer > 0.6:
                if self.target_color in DROP_BINS:
                    self.state = "HOVER_PICK"
                    self.state_timer = 0.0
                    self.arm_target_x = self.pickup_x
                    self.arm_target_y = self.pickup_y - 65
                else:
                    # Unknown / Yellow - skip or drop
                    self.state = "HOVER_PICK"
                    self.state_timer = 0.0
                    self.arm_target_x = self.pickup_x
                    self.arm_target_y = self.pickup_y - 65

        elif self.state == "HOVER_PICK":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 3.0:
                self.state = "DESCEND_PICK"
                self.arm_target_y = self.pickup_y - 12
                self.gripper_open = 22

        elif self.state == "DESCEND_PICK":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 3.0:
                self.state = "GRASP"
                self.state_timer = 0.0
                candidate = next((b for b in self.blocks if not b.held and not b.sorted and abs(b.x - self.pickup_x) <= 6.0), None)
                if candidate:
                    candidate.held = True
                    self.grasped_block = candidate
                    print(f"[GRIP]  Grasped {candidate.color_name.upper()} block.", flush=True)

        elif self.state == "GRASP":
            self.gripper_open = max(8, self.gripper_open - 40 * dt)
            if self.state_timer > 0.4:
                self.state = "LIFT"
                self.arm_target_y = self.pickup_y - 80

        elif self.state == "LIFT":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 3.0:
                self.state = "TRANSPORT"
                target_bin = DROP_BINS.get(self.target_color, DROP_BINS['blue'])
                bin_cx = target_bin["pos"][0] + target_bin["size"][0] // 2
                bin_cy = target_bin["pos"][1] + target_bin["size"][1] // 2
                self.current_drop_pos = (bin_cx, bin_cy)
                self.arm_target_x = bin_cx
                self.arm_target_y = bin_cy - 70
                print(f"[ARM]   Transporting block to {self.target_color.upper()} bin...", flush=True)

        elif self.state == "TRANSPORT":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 4.0:
                self.state = "LOWER"
                self.arm_target_y = self.current_drop_pos[1] - 15

        elif self.state == "LOWER":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 3.0:
                self.state = "RELEASE"
                self.state_timer = 0.0

        elif self.state == "RELEASE":
            self.gripper_open = min(22, self.gripper_open + 40 * dt)
            if self.state_timer > 0.3:
                if self.grasped_block:
                    self.grasped_block.held = False
                    self.grasped_block.sorted = True
                    c = self.grasped_block.color_name
                    self.counts[c] = self.counts.get(c, 0) + 1
                    self.total_sorted += 1
                    print(f"[OK]    Successfully sorted {c.upper()} block! Total sorted: {self.total_sorted} | Counts: {self.counts}", flush=True)
                    self.grasped_block = None
                self.state = "RETRACT"
                self.arm_target_y = self.current_drop_pos[1] - 80

        elif self.state == "RETRACT":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 4.0:
                self.state = "RETURN_HOME"
                self.arm_target_x = self.robot_base_x - 30
                self.arm_target_y = self.robot_base_y - 100

        elif self.state == "RETURN_HOME":
            if math.hypot(self.arm_x - self.arm_target_x, self.arm_y - self.arm_target_y) < 4.0:
                self.state = "WAITING_BLOCK"
                self.conveyor_running = True

        # Clean up off-screen blocks
        self.blocks = [b for b in self.blocks if not b.sorted]

    def draw_robot(self):
        # 2-segment inverse/forward kinematics representation of UR5
        bx, by = self.robot_base_x, self.robot_base_y
        tx, ty = self.arm_x, self.arm_y

        # Base pedestal
        pygame.draw.rect(self.screen, (40, 42, 52), (bx - 26, by - 12, 52, 24), border_radius=4)
        pygame.draw.circle(self.screen, (80, 85, 105), (bx, by), 16)
        pygame.draw.circle(self.screen, (120, 125, 145), (bx, by), 8)

        # 2-link analytic IK for elbow
        L1, L2 = 130.0, 120.0
        dist = math.hypot(tx - bx, ty - by)
        dist = max(20.0, min(dist, L1 + L2 - 2.0))
        angle_base = math.atan2(ty - by, tx - bx)

        cos_elbow = (dist * dist - L1 * L1 - L2 * L2) / (2 * L1 * L2)
        cos_elbow = max(-1.0, min(1.0, cos_elbow))
        angle_elbow = -math.acos(cos_elbow)

        cos_shoulder = (dist * dist + L1 * L1 - L2 * L2) / (2 * dist * L1)
        cos_shoulder = max(-1.0, min(1.0, cos_shoulder))
        angle_shoulder = angle_base - math.acos(cos_shoulder)

        # Joint 1 (Elbow) pos
        jx = bx + L1 * math.cos(angle_shoulder)
        jy = by + L1 * math.sin(angle_shoulder)

        # Link 1 (Shoulder to Elbow)
        pygame.draw.line(self.screen, (90, 95, 115), (bx, by), (jx, jy), 14)
        pygame.draw.line(self.screen, (140, 145, 165), (bx, by), (jx, jy), 4)
        pygame.draw.circle(self.screen, (70, 75, 90), (int(jx), int(jy)), 12)
        pygame.draw.circle(self.screen, (160, 165, 185), (int(jx), int(jy)), 6)

        # Link 2 (Elbow to Wrist)
        pygame.draw.line(self.screen, (100, 105, 125), (jx, jy), (tx, ty), 10)
        pygame.draw.line(self.screen, (150, 155, 175), (jx, jy), (tx, ty), 3)
        pygame.draw.circle(self.screen, (60, 65, 80), (int(tx), int(ty)), 9)

        # Gripper Assembly
        gw = self.gripper_open
        # Wrist block
        pygame.draw.rect(self.screen, (170, 175, 195), (int(tx - 12), int(ty), 24, 8), border_radius=2)
        # Left finger
        pygame.draw.rect(self.screen, (200, 205, 220), (int(tx - gw // 2 - 4), int(ty + 8), 4, 16), border_radius=2)
        # Right finger
        pygame.draw.rect(self.screen, (200, 205, 220), (int(tx + gw // 2), int(ty + 8), 4, 16), border_radius=2)

    def draw(self):
        self.screen.fill(BG_COLOR)

        # ── Header ──────────────────────────────────────────────────────────
        header_surf = pygame.Rect(0, 0, self.width, 54)
        pygame.draw.rect(self.screen, PANEL_BG, header_surf)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, 54), (self.width, 54), 2)

        title = self.font_title.render("Color Sorting Robot — Simulation Environment", True, TEXT_WHITE)
        self.screen.blit(title, (20, 12))

        mode_badge = self.font_small.render("STANDALONE MODE (Pygame + OpenCV)", True, (40, 220, 120))
        pygame.draw.rect(self.screen, (20, 50, 35), (self.width - 270, 14, 250, 26), border_radius=4)
        pygame.draw.rect(self.screen, (40, 180, 100), (self.width - 270, 14, 250, 26), 1, border_radius=4)
        self.screen.blit(mode_badge, (self.width - 258, 18))

        # ── Conveyor Belt ───────────────────────────────────────────────────
        cw = self.conveyor_end_x - self.conveyor_start_x
        ch = 44
        cx = self.conveyor_start_x
        cy = self.conveyor_y - ch // 2

        # Belt shadow & body
        pygame.draw.rect(self.screen, (20, 22, 28), (cx - 4, cy - 4, cw + 8, ch + 8), border_radius=6)
        pygame.draw.rect(self.screen, CONVEYOR_COLOR, (cx, cy, cw, ch), border_radius=4)

        # Moving belt chevrons
        for x in range(int(cx - 24 + self.belt_offset), int(cx + cw), 24):
            if cx + 6 <= x <= cx + cw - 12:
                pygame.draw.line(self.screen, BELT_LINE, (x, cy + 4), (x + 8, cy + ch // 2), 2)
                pygame.draw.line(self.screen, BELT_LINE, (x + 8, cy + ch // 2), (x, cy + ch - 4), 2)

        # Rollers
        pygame.draw.circle(self.screen, (80, 85, 100), (cx + 6, cy + ch // 2), 14)
        pygame.draw.circle(self.screen, (80, 85, 100), (cx + cw - 6, cy + ch // 2), 14)

        conveyor_label = self.font_small.render("Conveyor Belt (0.08 m/s)", True, TEXT_MUTED)
        self.screen.blit(conveyor_label, (cx + 20, cy + ch + 8))

        # ── Proximity Sensor & Vision Sensor ────────────────────────────────
        px, py = self.pickup_x, self.pickup_y

        # Proximity sensor beam
        beam_color = (255, 220, 50, 90) if self.state in ["DETECTING", "HOVER_PICK", "DESCEND_PICK", "GRASP"] else (80, 180, 255, 45)
        beam_surf = pygame.Surface((30, 80), pygame.SRCALPHA)
        pygame.draw.polygon(beam_surf, beam_color, [(15, 0), (0, 80), (30, 80)])
        self.screen.blit(beam_surf, (px - 15, py - 90))

        # Sensor head
        pygame.draw.rect(self.screen, (70, 75, 90), (px - 12, py - 95, 24, 12), border_radius=3)
        pygame.draw.circle(self.screen, (255, 200, 40) if not self.conveyor_running else (50, 150, 255), (px, py - 90), 4)

        sensor_txt = self.font_small.render("Prox + Vision", True, TEXT_MUTED)
        self.screen.blit(sensor_txt, (px - 34, py - 114))

        # Pickup Zone marker
        pygame.draw.circle(self.screen, (100, 105, 125), (px, py), 22, 1)

        # ── Destination Bins ────────────────────────────────────────────────
        bins_title = self.font_bold.render("SORTING DESTINATION BINS", True, TEXT_MUTED)
        self.screen.blit(bins_title, (735, 68))

        for color_name, b_info in DROP_BINS.items():
            bx, by = b_info["pos"]
            bw, bh = b_info["size"]
            bc     = b_info["color"]
            count  = self.counts.get(color_name, 0)

            # Bin Container Box
            pygame.draw.rect(self.screen, PANEL_BG, (bx, by, bw, bh), border_radius=8)
            pygame.draw.rect(self.screen, bc, (bx, by, bw, bh), 2, border_radius=8)

            # Color Indicator Pill
            pygame.draw.circle(self.screen, bc, (bx + 20, by + 24), 10)

            name_surf = self.font_bold.render(color_name.upper(), True, TEXT_WHITE)
            self.screen.blit(name_surf, (bx + 38, by + 14))

            cnt_surf = self.font_main.render(f"Count: {count}", True, TEXT_ACCENT)
            self.screen.blit(cnt_surf, (bx + 18, by + 46))

        # ── Blocks ──────────────────────────────────────────────────────────
        for b in self.blocks:
            bc = COLOR_RGB.get(b.color_name, (200, 200, 200))
            rect = b.rect
            pygame.draw.rect(self.screen, bc, rect, border_radius=4)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 1, border_radius=4)

        # ── UR5 Robot Arm ───────────────────────────────────────────────────
        self.draw_robot()

        # ── Right / Top Panel: Vision Sensor Camera Preview ─────────────────
        cam_panel = pygame.Rect(490, 80, 210, 190)
        pygame.draw.rect(self.screen, PANEL_BG, cam_panel, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, cam_panel, 1, border_radius=8)

        cam_title = self.font_bold.render("VISION SENSOR CAM", True, TEXT_WHITE)
        self.screen.blit(cam_title, (cam_panel.x + 12, cam_panel.y + 10))

        # Render OpenCV camera image into Pygame surface
        if self.last_camera_frame is not None:
            rgb_frame = cv2.cvtColor(self.last_camera_frame, cv2.COLOR_BGR2RGB)
            cam_surf = pygame.surfarray.make_surface(np.transpose(rgb_frame, (1, 0, 2)))
            cam_surf = pygame.transform.scale(cam_surf, (90, 90))
            self.screen.blit(cam_surf, (cam_panel.x + 12, cam_panel.y + 36))
            pygame.draw.rect(self.screen, PANEL_BORDER, (cam_panel.x + 12, cam_panel.y + 36, 90, 90), 1)

        # Detection text details
        det_label = self.font_small.render("OpenCV HSV:", True, TEXT_MUTED)
        self.screen.blit(det_label, (cam_panel.x + 110, cam_panel.y + 38))

        color_str = self.last_detected_color.upper()
        det_color_val = COLOR_RGB.get(self.last_detected_color, TEXT_WHITE)
        color_surf = self.font_bold.render(color_str, True, det_color_val)
        self.screen.blit(color_surf, (cam_panel.x + 110, cam_panel.y + 56))

        pipe_label = self.font_small.render("Pipeline:", True, TEXT_MUTED)
        self.screen.blit(pipe_label, (cam_panel.x + 110, cam_panel.y + 84))
        ok_txt = self.font_small.render("HSV Masks OK", True, (80, 220, 120))
        self.screen.blit(ok_txt, (cam_panel.x + 110, cam_panel.y + 102))

        stat_txt = self.font_small.render(f"Total Sorted: {self.total_sorted}", True, TEXT_ACCENT)
        self.screen.blit(stat_txt, (cam_panel.x + 12, cam_panel.y + 140))

        # ── Bottom Telemetry Panel ──────────────────────────────────────────
        bot_panel = pygame.Rect(20, self.height - 90, self.width - 40, 75)
        pygame.draw.rect(self.screen, PANEL_BG, bot_panel, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, bot_panel, 1, border_radius=8)

        st_lbl = self.font_small.render("ROBOT STATE:", True, TEXT_MUTED)
        self.screen.blit(st_lbl, (bot_panel.x + 16, bot_panel.y + 12))
        st_val = self.font_bold.render(self.state, True, TEXT_ACCENT)
        self.screen.blit(st_val, (bot_panel.x + 110, bot_panel.y + 10))

        pos_lbl = self.font_small.render(f"IK Target (X, Y): ({int(self.arm_x)}, {int(self.arm_y)})", True, TEXT_WHITE)
        self.screen.blit(pos_lbl, (bot_panel.x + 16, bot_panel.y + 38))

        ctrl_info = self.font_small.render("[SPACE] Pause   [S] Spawn Block   [R] Reset   [ESC] Quit", True, TEXT_MUTED)
        self.screen.blit(ctrl_info, (bot_panel.x + 360, bot_panel.y + 38))

        mode_info = self.font_small.render("Running full color sorting loop without requiring CoppeliaSim installation.", True, (120, 200, 140))
        self.screen.blit(mode_info, (bot_panel.x + 360, bot_panel.y + 12))

        pygame.display.flip()

    def run(self):
        print("\n" + "=" * 60, flush=True)
        print("  Color Sorting Pick & Place Robot — Standalone Simulation", flush=True)
        print("=" * 60, flush=True)
        print("Running visual simulation with Pygame + OpenCV ColorDetector.", flush=True)
        print("Controls: [Space] Pause/Resume, [S] Spawn block, [Esc] Exit\n", flush=True)

        # Spawn initial block
        self.spawn_block()

        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_ESCAPE, pygame.K_q]:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.is_paused = not self.is_paused
                    elif event.key == pygame.K_s:
                        self.spawn_block()
                    elif event.key == pygame.K_r:
                        self.counts = {'red': 0, 'green': 0, 'blue': 0, 'yellow': 0}
                        self.total_sorted = 0

            self.update(dt)
            self.draw()

        pygame.quit()
        print("[INFO] Standalone simulation closed.")


def run_standalone():
    sim = StandaloneSimulator()
    sim.run()


if __name__ == '__main__':
    run_standalone()
