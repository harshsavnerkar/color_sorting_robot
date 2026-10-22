"""
color_detector.py
Reads the CoppeliaSim vision sensor image and classifies block color using HSV thresholding.
"""

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV not installed. Falling back to numpy-only color detection.")


# ── HSV Color Ranges ───────────────────────────────────────────────────────────
# Tuned for solid-colored blocks under default CoppeliaSim lighting.
# Adjust Lower/Upper bounds if your scene uses different lighting or colors.

HSV_RANGES = {
    'red': [
        (np.array([0,   120,  70]),  np.array([10,  255, 255])),
        (np.array([170, 120,  70]),  np.array([180, 255, 255])),   # red wraps hue
    ],
    'green': [
        (np.array([36,  100, 100]),  np.array([86,  255, 255])),
    ],
    'blue': [
        (np.array([94,  80,   2]),   np.array([126, 255, 255])),
    ],
    'yellow': [
        (np.array([20,  100, 100]),  np.array([35,  255, 255])),
    ],
}
# ───────────────────────────────────────────────────────────────────────────────


class ColorDetector:
    """
    Detects the color of the block currently under the vision sensor.

    Args:
        sim              : CoppeliaSim sim object from ZMQ API
        sensor_path      : Scene path of the vision sensor object
        min_pixel_ratio  : Fraction of image pixels needed to confirm a color (0–1)
        debug_window     : Show cv2 debug window during detection
    """

    def __init__(self,
                 sim,
                 sensor_path='/VisionSensor',
                 min_pixel_ratio=0.05,
                 debug_window=False):
        self.sim             = sim
        self.sensor_path     = sensor_path
        self.min_pixel_ratio = min_pixel_ratio
        self.debug_window    = debug_window
        self._handle         = None

    def _get_handle(self):
        if self._handle is None:
            try:
                self._handle = self.sim.getObject(self.sensor_path)
            except Exception:
                print(f"[WARN] Vision sensor '{self.sensor_path}' not found in scene.")
        return self._handle

    def capture_image(self):
        """
        Capture image from CoppeliaSim vision sensor.
        Returns an (H, W, 3) uint8 BGR numpy array, or None on failure.
        """
        handle = self._get_handle()
        if handle is None:
            return None

        try:
            res = self.sim.getVisionSensorImg(handle)
            if len(res) == 2:
                image_data, resolution = res
            elif len(res) == 3:
                _, resolution, image_data = res
            else:
                image_data, resolution = res[0], res[1]
        except Exception as e:
            print(f"[ERROR] Vision sensor read failed: {e}")
            return None

        if not image_data:
            return None

        # CoppeliaSim returns flattened RGB bytes
        if isinstance(image_data, (bytes, bytearray)):
            img = np.frombuffer(image_data, dtype=np.uint8)
        else:
            img = np.array(image_data, dtype=np.uint8)
        img = img.reshape((resolution[1], resolution[0], 3))
        img = np.flipud(img)                          # flip vertically (CoppeliaSim origin is bottom-left)

        if CV2_AVAILABLE:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        return img

    def classify_color(self, bgr_image):
        """
        Given a BGR image, return the dominant color name or 'unknown'.
        """
        if not CV2_AVAILABLE:
            return self._classify_numpy(bgr_image)

        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        total_pixels = hsv.shape[0] * hsv.shape[1]
        scores = {}

        for color, ranges in HSV_RANGES.items():
            combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for (lo, hi) in ranges:
                combined_mask = cv2.bitwise_or(combined_mask, cv2.inRange(hsv, lo, hi))
            scores[color] = cv2.countNonZero(combined_mask) / total_pixels

        if self.debug_window:
            self._show_debug(bgr_image, scores)

        best_color, best_score = max(scores.items(), key=lambda kv: kv[1])
        if best_score >= self.min_pixel_ratio:
            return best_color
        return 'unknown'

    def _classify_numpy(self, rgb_image):
        """Fallback color classification without OpenCV — uses mean RGB heuristics."""
        mean = rgb_image.mean(axis=(0, 1))  # [R, G, B]
        r, g, b = mean[0], mean[1], mean[2]

        if r > 150 and r > g * 1.5 and r > b * 1.5:
            return 'red'
        if g > 150 and g > r * 1.5 and g > b * 1.2:
            return 'green'
        if b > 150 and b > r * 1.5 and b > g * 1.2:
            return 'blue'
        if r > 150 and g > 150 and b < 80:
            return 'yellow'
        return 'unknown'

    def detect_color(self, block_handle=None):
        """
        Full pipeline: capture -> classify -> return color string.
        Falls back to reading the custom string data tag on the block if sensor fails.
        """
        img = self.capture_image()
        color = 'unknown'
        if img is not None:
            color = self.classify_color(img)

        if color in ['red', 'green', 'blue', 'yellow']:
            print(f"  [CAM] Detected color: {color}")
            return color

        # Fallback: check custom string data written by scene script
        if block_handle is not None and block_handle > 0:
            try:
                tag = self.sim.readCustomStringData(block_handle, 'blockColor')
                if tag in ['red', 'green', 'blue', 'yellow']:
                    print(f"  [TAG] RFID/Color tag detected: {tag}")
                    return tag
            except Exception:
                pass

        print(f"  [CAM] Classification inconclusive ('{color}'), defaulting to 'red'")
        return 'red'

    def _show_debug(self, img, scores):
        """Render debug overlay window (requires a display)."""
        try:
            debug = img.copy()
            y = 20
            for color, score in sorted(scores.items(), key=lambda kv: -kv[1]):
                text = f"{color}: {score:.3f}"
                cv2.putText(debug, text, (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                y += 22
            cv2.imshow("Color Detector — Debug", debug)
            cv2.waitKey(1)
        except Exception:
            pass

    def calibrate(self, known_color, num_samples=10):
        """
        Interactive calibration helper: capture N frames of a known-color block
        and print the mean HSV value to help tune thresholds.
        """
        if not CV2_AVAILABLE:
            print("[WARN] OpenCV required for calibration.")
            return

        print(f"[CAL] Calibrating for color='{known_color}'. Capturing {num_samples} frames...")
        h_vals, s_vals, v_vals = [], [], []

        for i in range(num_samples):
            img = self.capture_image()
            if img is None:
                continue
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h_vals.append(hsv[:, :, 0].mean())
            s_vals.append(hsv[:, :, 1].mean())
            v_vals.append(hsv[:, :, 2].mean())
            import time; time.sleep(0.1)

        print(f"[CAL] Mean HSV for '{known_color}': "
              f"H={np.mean(h_vals):.1f}, S={np.mean(s_vals):.1f}, V={np.mean(v_vals):.1f}")
