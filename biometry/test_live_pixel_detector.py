import os
import re
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

def run_adb_cmd(cmd):
    """Run an ADB shell command and return stdout."""
    full_cmd = f"adb {cmd}"
    res = subprocess.run(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.stdout.strip()

def capture_live_state():
    """Captures screenshot PNG and UI dump XML from the live emulator."""
    print("[ADB Bridge] Dumping live UI view hierarchy...")
    run_adb_cmd("shell uiautomator dump /sdcard/window_dump.xml")
    run_adb_cmd("pull /sdcard/window_dump.xml window_dump.xml")
    
    print("[ADB Bridge] Capturing live screenshot...")
    # Direct binary capture to avoid line-ending corruption on Windows
    with open("screen.png", "wb") as f:
        subprocess.run("adb exec-out screencap -p", shell=True, stdout=f)

def parse_pixel_elements(xml_path="window_dump.xml"):
    """Parses XML and dynamically extracts pixel bounds for all interactive UI nodes."""
    if not os.path.exists(xml_path):
        print("[-] XML dump file not found.")
        return []

    tree = ET.parse(xml_path)
    root = tree.getroot()

    elements = []
    # Find all nodes with bounds attribute
    for node in root.iter("node"):
        bounds_str = node.attrib.get("bounds", "")
        text = node.attrib.get("text", "")
        resource_id = node.attrib.get("resource-id", "")
        content_desc = node.attrib.get("content-desc", "")
        clickable = node.attrib.get("clickable", "false")

        # Parse bounds format: [x1,y1][x2,y2]
        match = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
        if len(match) == 2:
            x1, y1 = int(match[0][0]), int(match[0][1])
            x2, y2 = int(match[1][0]), int(match[1][1])
            
            w = x2 - x1
            h = y2 - y1
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            # Filter out full-screen zero-content root nodes
            if w > 0 and h > 0 and (clickable == "true" or text != "" or content_desc != ""):
                identifier = text or content_desc or resource_id.split("/")[-1] or "UI_Node"
                elements.append({
                    "id": identifier,
                    "bounds": (x1, y1, x2, y2),
                    "center": (center_x, center_y),
                    "width": w,
                    "height": h,
                    "clickable": clickable
                })
    return elements

def draw_detected_pixels(image_path="screen.png", elements=[], output_path="detected_pixels.png"):
    """Draws bounding boxes and target center coordinates directly on the screenshot."""
    if not os.path.exists(image_path):
        return

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    print("\n" + "=" * 65)
    print(f"DYNAMICALLY DETECTED UI PIXEL TARGETS ({len(elements)} FOUND)")
    print("=" * 65)

    for idx, el in enumerate(elements):
        x1, y1, x2, y2 = el["bounds"]
        cx, cy = el["center"]
        label = f"{el['id']} ({cx},{cy})"

        # Draw green bounding box around element
        draw.rectangle([x1, y1, x2, y2], outline="lime", width=3)
        
        # Draw red crosshair at target center
        draw.line([cx - 15, cy, cx + 15, cy], fill="red", width=2)
        draw.line([cx, cy - 15, cx, cy + 15], fill="red", width=2)
        
        # Draw label background and text
        draw.rectangle([x1, max(0, y1 - 25), x1 + (len(label) * 9), y1], fill="black")
        draw.text((x1 + 3, max(0, y1 - 22)), label, fill="yellow")

        print(f"[{idx+1:02d}] Target: {el['id']:<20} | Bounds: [{x1},{y1}][{x2},{y2}] | Center: ({cx}, {cy}) | Size: {el['width']}x{el['height']}px")

    img.save(output_path)
    print("=" * 65)
    print(f"[+] Verification image saved to: {output_path}")

if __name__ == "__main__":
    capture_live_state()
    detected = parse_pixel_elements("window_dump.xml")
    draw_detected_pixels("screen.png", detected, "detected_pixels.png")