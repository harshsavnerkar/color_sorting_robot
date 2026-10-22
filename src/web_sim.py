"""
web_sim.py
Localhost Web Server & Dashboard for the Color Sorting Robot.
Runs an interactive web simulation on http://localhost:8080 accessible from any browser.
"""

import http.server
import socketserver
import json
import threading
import os
import sys

PORT = 8080

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Color Sorting Robot — Localhost Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #121318;
      color: #e2e4ed;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }
    .header {
      width: 100%;
      max-width: 1080px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 24px;
      background: #1a1d26;
      border: 1px solid #2d3142;
      border-radius: 12px;
      margin-bottom: 20px;
    }
    .header h1 { font-size: 1.25rem; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 10px; }
    .badge {
      font-size: 0.75rem;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(40, 200, 100, 0.15);
      color: #4ade80;
      border: 1px solid rgba(40, 200, 100, 0.3);
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 20px;
      width: 100%;
      max-width: 1080px;
    }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
    .canvas-card {
      background: #1a1d26;
      border: 1px solid #2d3142;
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    canvas {
      width: 100%;
      max-width: 700px;
      height: 480px;
      background: #14161f;
      border: 1px solid #282b3a;
      border-radius: 8px;
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .panel {
      background: #1a1d26;
      border: 1px solid #2d3142;
      border-radius: 12px;
      padding: 18px;
    }
    .panel-title {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #94a3b8;
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .bins-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }
    .bin-card {
      background: #14161f;
      border-radius: 8px;
      padding: 12px 8px;
      text-align: center;
      border: 1px solid #282b3a;
      transition: transform 0.15s ease;
    }
    .bin-card.red { border-top: 3px solid #ef4444; }
    .bin-card.green { border-top: 3px solid #22c55e; }
    .bin-card.blue { border-top: 3px solid #3b82f6; }
    .bin-card.yellow { border-top: 3px solid #eab308; }
    .bin-count { font-size: 1.4rem; font-weight: 700; color: #ffffff; margin-top: 4px; }
    .bin-label { font-size: 0.72rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; }
    
    .cam-box {
      display: flex;
      align-items: center;
      gap: 16px;
      background: #14161f;
      border: 1px solid #282b3a;
      border-radius: 8px;
      padding: 12px;
    }
    .cam-preview {
      width: 72px;
      height: 72px;
      background: #202430;
      border: 1px solid #3b4256;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }
    .cam-swatch {
      width: 32px;
      height: 32px;
      border-radius: 4px;
      box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }
    .cam-details { font-size: 0.8rem; line-height: 1.5; }
    .cam-color-name { font-weight: 700; font-size: 1rem; }
    
    .controls-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    button {
      background: #252936;
      border: 1px solid #3d4358;
      color: #e2e4ed;
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    button:hover { background: #32384a; border-color: #555d78; }
    button.btn-primary { background: #2563eb; border-color: #3b82f6; color: #fff; }
    button.btn-primary:hover { background: #1d4ed8; }
    button.btn-red { border-color: #ef4444; color: #fca5a5; }
    button.btn-green { border-color: #22c55e; color: #86efac; }
    button.btn-blue { border-color: #3b82f6; color: #93c5fd; }
    button.btn-yellow { border-color: #eab308; color: #fde047; }
    
    .telemetry {
      font-family: monospace;
      font-size: 0.78rem;
      color: #94a3b8;
      line-height: 1.6;
    }
    .telemetry span { color: #38bdf8; font-weight: 600; }
  </style>
</head>
<body>

  <div class="header">
    <h1>
      <span>🦾</span> Color Sorting Robot
      <span class="badge">RUNNING ON LOCALHOST:8080</span>
    </h1>
    <div style="font-size: 0.82rem; color: #94a3b8;">
      Simulation Mode: <strong style="color: #38bdf8;">Visual & Computer Vision</strong>
    </div>
  </div>

  <div class="grid">
    <!-- Main Canvas Card -->
    <div class="canvas-card">
      <canvas id="simCanvas" width="700" height="480"></canvas>
      <div style="margin-top: 12px; font-size: 0.78rem; color: #64748b; display: flex; gap: 20px;">
        <span><strong>Space:</strong> Pause/Play</span>
        <span><strong>S:</strong> Spawn Random Block</span>
        <span><strong>R:</strong> Reset Scores</span>
      </div>
    </div>

    <!-- Right Sidebar -->
    <div class="sidebar">
      <!-- Destination Bins -->
      <div class="panel">
        <div class="panel-title">
          <span>Destination Bins</span>
          <span style="font-size: 0.75rem; color: #38bdf8;">Total: <strong id="totalCount">0</strong></span>
        </div>
        <div class="bins-grid">
          <div class="bin-card red">
            <div class="bin-label">RED</div>
            <div class="bin-count" id="redCount">0</div>
          </div>
          <div class="bin-card green">
            <div class="bin-label">GREEN</div>
            <div class="bin-count" id="greenCount">0</div>
          </div>
          <div class="bin-card blue">
            <div class="bin-label">BLUE</div>
            <div class="bin-count" id="blueCount">0</div>
          </div>
          <div class="bin-card yellow">
            <div class="bin-label">YELLOW</div>
            <div class="bin-count" id="yellowCount">0</div>
          </div>
        </div>
      </div>

      <!-- Vision Camera Preview -->
      <div class="panel">
        <div class="panel-title">Vision Sensor (OpenCV HSV)</div>
        <div class="cam-box">
          <div class="cam-preview">
            <div class="cam-swatch" id="camSwatch" style="background: #333;"></div>
          </div>
          <div class="cam-details">
            <div class="cam-color-name" id="camColorName" style="color: #94a3b8;">NO TARGET</div>
            <div style="color: #64748b; font-size: 0.74rem;">Pipeline: OpenCV HSV</div>
            <div style="color: #4ade80; font-size: 0.74rem;">Confidence: <span id="camConf">--</span></div>
          </div>
        </div>
      </div>

      <!-- Manual Controls -->
      <div class="panel">
        <div class="panel-title">Manual Spawner</div>
        <div class="controls-grid">
          <button class="btn-red" onclick="spawnColor('red')">+ Red</button>
          <button class="btn-green" onclick="spawnColor('green')">+ Green</button>
          <button class="btn-blue" onclick="spawnColor('blue')">+ Blue</button>
          <button class="btn-yellow" onclick="spawnColor('yellow')">+ Yellow</button>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 10px;">
          <button class="btn-primary" style="flex: 1;" onclick="spawnColor()">+ Random</button>
          <button style="flex: 1;" onclick="togglePause()" id="pauseBtn">Pause</button>
          <button style="flex: 1;" onclick="resetStats()">Reset</button>
        </div>
      </div>

      <!-- Telemetry Info -->
      <div class="panel">
        <div class="panel-title">Robot Telemetry</div>
        <div class="telemetry">
          <div>State: <span id="teleState">WAITING_BLOCK</span></div>
          <div>IK Target: <span id="teleTarget">(380, 240)</span></div>
          <div>Conveyor: <span id="teleConveyor">RUNNING (0.08 m/s)</span></div>
          <div>Gripper: <span id="teleGripper">OPEN (22mm)</span></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const canvas = document.getElementById('simCanvas');
    const ctx = canvas.getContext('2d');

    const COLOR_MAP = {
      red: '#ef4444',
      green: '#22c55e',
      blue: '#3b82f6',
      yellow: '#eab308'
    };

    const BINS = {
      red:    { x: 550, y: 70,  w: 90, h: 65, color: '#ef4444' },
      green:  { x: 550, y: 155, w: 90, h: 65, color: '#22c55e' },
      blue:   { x: 550, y: 240, w: 90, h: 65, color: '#3b82f6' },
      yellow: { x: 550, y: 325, w: 90, h: 65, color: '#eab308' }
    };

    const CONVEYOR = {
      x: 40,
      y: 240,
      w: 320,
      h: 46,
      pickupX: 300,
      speed: 65,
      offset: 0
    };

    const ROBOT = {
      baseX: 430,
      baseY: 240,
      targetX: 430,
      targetY: 140,
      armX: 430,
      armY: 140,
      gripper: 20
    };

    let blocks = [];
    let graspedBlock = null;
    let counts = { red: 0, green: 0, blue: 0, yellow: 0 };
    let totalSorted = 0;
    let state = 'WAITING_BLOCK';
    let stateTimer = 0;
    let targetColor = null;
    let isPaused = false;
    let spawnTimer = 0;

    function spawnColor(specificColor) {
      const colors = ['red', 'green', 'blue', 'yellow'];
      const c = specificColor || colors[Math.floor(Math.random() * colors.length)];
      blocks.push({
        color: c,
        x: CONVEYOR.x + 10,
        y: CONVEYOR.y,
        size: 26,
        held: false,
        sorted: false
      });
    }

    function togglePause() {
      isPaused = !isPaused;
      document.getElementById('pauseBtn').innerText = isPaused ? 'Resume' : 'Pause';
    }

    function resetStats() {
      counts = { red: 0, green: 0, blue: 0, yellow: 0 };
      totalSorted = 0;
      updateUI();
    }

    function updateUI() {
      document.getElementById('redCount').innerText = counts.red;
      document.getElementById('greenCount').innerText = counts.green;
      document.getElementById('blueCount').innerText = counts.blue;
      document.getElementById('yellowCount').innerText = counts.yellow;
      document.getElementById('totalCount').innerText = totalSorted;
      document.getElementById('teleState').innerText = state;
      document.getElementById('teleTarget').innerText = `(${Math.round(ROBOT.armX)}, ${Math.round(ROBOT.armY)})`;
      document.getElementById('teleConveyor').innerText = (state === 'WAITING_BLOCK' && !isPaused) ? 'RUNNING (0.08 m/s)' : 'STOPPED';
      document.getElementById('teleGripper').innerText = Math.round(ROBOT.gripper) + 'mm';
    }

    function update(dt) {
      if (isPaused) return;

      // Spawning
      spawnTimer += dt;
      if (spawnTimer > 4.5 && blocks.length < 4) {
        if (!blocks.some(b => !b.sorted && !b.held && b.x < CONVEYOR.x + 60)) {
          spawnColor();
          spawnTimer = 0;
        }
      }

      // Conveyor
      const conveyorRunning = (state === 'WAITING_BLOCK');
      if (conveyorRunning) {
        CONVEYOR.offset = (CONVEYOR.offset + CONVEYOR.speed * dt) % 24;
        for (let b of blocks) {
          if (!b.held && !b.sorted && b.x < CONVEYOR.pickupX) {
            b.x += CONVEYOR.speed * dt;
            if (b.x >= CONVEYOR.pickupX) b.x = CONVEYOR.pickupX;
          }
        }
      }

      // Arm movement interpolation
      const dx = ROBOT.targetX - ROBOT.armX;
      const dy = ROBOT.targetY - ROBOT.armY;
      const dist = Math.hypot(dx, dy);
      const armSpeed = 360;
      if (dist > 1) {
        const step = Math.min(dist, armSpeed * dt);
        ROBOT.armX += (dx / dist) * step;
        ROBOT.armY += (dy / dist) * step;
      } else {
        ROBOT.armX = ROBOT.targetX;
        ROBOT.armY = ROBOT.targetY;
      }

      if (graspedBlock) {
        graspedBlock.x = ROBOT.armX;
        graspedBlock.y = ROBOT.armY + 14;
      }

      // Pick & Place State Machine
      stateTimer += dt;

      if (state === 'WAITING_BLOCK') {
        ROBOT.targetX = ROBOT.baseX - 30;
        ROBOT.targetY = ROBOT.baseY - 90;
        ROBOT.gripper = 22;

        const candidate = blocks.find(b => !b.held && !b.sorted && Math.abs(b.x - CONVEYOR.pickupX) <= 3);
        if (candidate) {
          state = 'DETECTING';
          stateTimer = 0;
          targetColor = candidate.color;

          // Update Vision Panel
          document.getElementById('camSwatch').style.background = COLOR_MAP[candidate.color];
          document.getElementById('camColorName').innerText = candidate.color.toUpperCase();
          document.getElementById('camColorName').style.color = COLOR_MAP[candidate.color];
          document.getElementById('camConf').innerText = '98.4%';
        }
      } else if (state === 'DETECTING') {
        if (stateTimer > 0.6) {
          state = 'HOVER_PICK';
          ROBOT.targetX = CONVEYOR.pickupX;
          ROBOT.targetY = CONVEYOR.y - 65;
        }
      } else if (state === 'HOVER_PICK') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 3) {
          state = 'DESCEND_PICK';
          ROBOT.targetY = CONVEYOR.y - 12;
        }
      } else if (state === 'DESCEND_PICK') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 3) {
          state = 'GRASP';
          stateTimer = 0;
          const candidate = blocks.find(b => !b.held && !b.sorted && Math.abs(b.x - CONVEYOR.pickupX) <= 6);
          if (candidate) {
            candidate.held = true;
            graspedBlock = candidate;
          }
        }
      } else if (state === 'GRASP') {
        ROBOT.gripper = Math.max(8, ROBOT.gripper - 45 * dt);
        if (stateTimer > 0.4) {
          state = 'LIFT';
          ROBOT.targetY = CONVEYOR.y - 80;
        }
      } else if (state === 'LIFT') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 3) {
          state = 'TRANSPORT';
          const bin = BINS[targetColor] || BINS.blue;
          ROBOT.targetX = bin.x + bin.w / 2;
          ROBOT.targetY = bin.y + bin.h / 2 - 60;
        }
      } else if (state === 'TRANSPORT') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 4) {
          state = 'LOWER';
          const bin = BINS[targetColor] || BINS.blue;
          ROBOT.targetY = bin.y + bin.h / 2 - 10;
        }
      } else if (state === 'LOWER') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 3) {
          state = 'RELEASE';
          stateTimer = 0;
        }
      } else if (state === 'RELEASE') {
        ROBOT.gripper = Math.min(22, ROBOT.gripper + 45 * dt);
        if (stateTimer > 0.3) {
          if (graspedBlock) {
            graspedBlock.held = false;
            graspedBlock.sorted = true;
            counts[graspedBlock.color] = (counts[graspedBlock.color] || 0) + 1;
            totalSorted++;
            graspedBlock = null;
          }
          state = 'RETRACT';
          const bin = BINS[targetColor] || BINS.blue;
          ROBOT.targetY = bin.y + bin.h / 2 - 70;
        }
      } else if (state === 'RETRACT') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 4) {
          state = 'RETURN_HOME';
          ROBOT.targetX = ROBOT.baseX - 30;
          ROBOT.targetY = ROBOT.baseY - 90;
        }
      } else if (state === 'RETURN_HOME') {
        if (Math.hypot(ROBOT.armX - ROBOT.targetX, ROBOT.armY - ROBOT.targetY) < 4) {
          state = 'WAITING_BLOCK';
          document.getElementById('camSwatch').style.background = '#202430';
          document.getElementById('camColorName').innerText = 'NO TARGET';
          document.getElementById('camColorName').style.color = '#94a3b8';
          document.getElementById('camConf').innerText = '--';
        }
      }

      blocks = blocks.filter(b => !b.sorted);
      updateUI();
    }

    function drawRobot() {
      const bx = ROBOT.baseX, by = ROBOT.baseY;
      const tx = ROBOT.armX, ty = ROBOT.armY;

      // Base
      ctx.fillStyle = '#262933';
      ctx.fillRect(bx - 20, by - 10, 40, 20);
      ctx.fillStyle = '#475569';
      ctx.beginPath();
      ctx.arc(bx, by, 14, 0, Math.PI * 2);
      ctx.fill();

      // Analytic 2-link IK
      const L1 = 110, L2 = 100;
      const dist = Math.hypot(tx - bx, ty - by);
      const clampedDist = Math.max(10, Math.min(dist, L1 + L2 - 1));
      const angleBase = Math.atan2(ty - by, tx - bx);

      let cosElbow = (clampedDist * clampedDist - L1 * L1 - L2 * L2) / (2 * L1 * L2);
      cosElbow = Math.max(-1, Math.min(1, cosElbow));
      const angleElbow = -Math.acos(cosElbow);

      let cosShoulder = (clampedDist * clampedDist + L1 * L1 - L2 * L2) / (2 * clampedDist * L1);
      cosShoulder = Math.max(-1, Math.min(1, cosShoulder));
      const angleShoulder = angleBase - Math.acos(cosShoulder);

      const jx = bx + L1 * Math.cos(angleShoulder);
      const jy = by + L1 * Math.sin(angleShoulder);

      // Link 1
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 12;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(jx, jy);
      ctx.stroke();

      // Joint 1
      ctx.fillStyle = '#334155';
      ctx.beginPath();
      ctx.arc(jx, jy, 10, 0, Math.PI * 2);
      ctx.fill();

      // Link 2
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 8;
      ctx.beginPath();
      ctx.moveTo(jx, jy);
      ctx.lineTo(tx, ty);
      ctx.stroke();

      // Gripper
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(tx - 10, ty, 20, 6);
      const gw = ROBOT.gripper;
      ctx.fillRect(tx - gw / 2 - 3, ty + 6, 3, 14);
      ctx.fillRect(tx + gw / 2, ty + 6, 3, 14);
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // ── Conveyor Belt ──
      ctx.fillStyle = '#1e222d';
      ctx.fillRect(CONVEYOR.x - 4, CONVEYOR.y - CONVEYOR.h/2 - 4, CONVEYOR.w + 8, CONVEYOR.h + 8);
      ctx.fillStyle = '#2d3342';
      ctx.fillRect(CONVEYOR.x, CONVEYOR.y - CONVEYOR.h/2, CONVEYOR.w, CONVEYOR.h);

      // Moving belt lines
      ctx.strokeStyle = '#3e465a';
      ctx.lineWidth = 2;
      for (let x = CONVEYOR.x - 20 + CONVEYOR.offset; x < CONVEYOR.x + CONVEYOR.w; x += 22) {
        if (x >= CONVEYOR.x + 4 && x <= CONVEYOR.x + CONVEYOR.w - 12) {
          ctx.beginPath();
          ctx.moveTo(x, CONVEYOR.y - CONVEYOR.h/2 + 4);
          ctx.lineTo(x + 8, CONVEYOR.y);
          ctx.lineTo(x, CONVEYOR.y + CONVEYOR.h/2 - 4);
          ctx.stroke();
        }
      }

      // Rollers
      ctx.fillStyle = '#475569';
      ctx.beginPath();
      ctx.arc(CONVEYOR.x + 6, CONVEYOR.y, 12, 0, Math.PI * 2);
      ctx.arc(CONVEYOR.x + CONVEYOR.w - 6, CONVEYOR.y, 12, 0, Math.PI * 2);
      ctx.fill();

      // Sensor Beam
      const isDetecting = ['DETECTING', 'HOVER_PICK', 'DESCEND_PICK', 'GRASP'].includes(state);
      ctx.fillStyle = isDetecting ? 'rgba(234, 179, 8, 0.25)' : 'rgba(56, 189, 248, 0.12)';
      ctx.beginPath();
      ctx.moveTo(CONVEYOR.pickupX, CONVEYOR.y - 70);
      ctx.lineTo(CONVEYOR.pickupX - 16, CONVEYOR.y);
      ctx.lineTo(CONVEYOR.pickupX + 16, CONVEYOR.y);
      ctx.closePath();
      ctx.fill();

      // Sensor Head
      ctx.fillStyle = '#334155';
      ctx.fillRect(CONVEYOR.pickupX - 10, CONVEYOR.y - 76, 20, 10);
      ctx.fillStyle = isDetecting ? '#eab308' : '#38bdf8';
      ctx.beginPath();
      ctx.arc(CONVEYOR.pickupX, CONVEYOR.y - 70, 3, 0, Math.PI * 2);
      ctx.fill();

      // Bins
      for (let [cName, b] of Object.entries(BINS)) {
        ctx.fillStyle = '#1a1d26';
        ctx.fillRect(b.x, b.y, b.w, b.h);
        ctx.strokeStyle = b.color;
        ctx.lineWidth = 2;
        ctx.strokeRect(b.x, b.y, b.w, b.h);

        ctx.fillStyle = b.color;
        ctx.font = 'bold 12px sans-serif';
        ctx.fillText(cName.toUpperCase() + ' BIN', b.x + 14, b.y + 22);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 20px sans-serif';
        ctx.fillText(counts[cName] || 0, b.x + b.w / 2 - 6, b.y + 52);
      }

      // Blocks
      for (let b of blocks) {
        ctx.fillStyle = COLOR_MAP[b.color];
        ctx.fillRect(b.x - b.size/2, b.y - b.size/2, b.size, b.size);
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.strokeRect(b.x - b.size/2, b.y - b.size/2, b.size, b.size);
      }

      // Robot Arm
      drawRobot();
    }

    let lastTime = performance.now();
    function loop(now) {
      const dt = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      update(dt);
      draw();
      requestAnimationFrame(loop);
    }

    // Keyboard shortcuts
    window.addEventListener('keydown', e => {
      if (e.code === 'Space') {
        e.preventDefault();
        togglePause();
      } else if (e.code === 'KeyS') {
        spawnColor();
      } else if (e.code === 'KeyR') {
        resetStats();
      }
    });

    // Start with 1 block
    spawnColor();
    requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


class WebHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode('utf-8'))

    def log_message(self, format, *args):
        # Keep server quiet
        pass


def run_web_server(port=PORT):
    # Allow address reuse
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("0.0.0.0", port), WebHandler) as httpd:
            print(f"\n=======================================================", flush=True)
            print(f"  Color Sorting Robot — Web Dashboard Live!", flush=True)
            print(f"=======================================================", flush=True)
            print(f"[OK] Server running on: http://localhost:{port}", flush=True)
            print(f"[OK] Also accessible on local network IP on port {port}", flush=True)
            print(f"[INFO] Open http://localhost:{port} in any browser.\n", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"[ERROR] Failed to start web server on port {port}: {e}", flush=True)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_web_server(port)
