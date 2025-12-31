import time
import threading
import keyboard
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# ----------------------------
# Key state
# ----------------------------

ALIASES = {
	"left shift": "Shift",
	"right shift": "Shift",
	"left ctrl": "Ctrl",
	"right ctrl": "Ctrl",
	"left alt": "Alt",
	"right alt": "Alt",
	"space": "Space",
	"enter": "Enter",
	"backspace": "Backspace",
}

def normalize(name: str) -> str:
	return ALIASES.get(name, name)

# key -> { last_time, count, order }
keys = {}
char_times = []  # timestamps of character presses for WPM
order_counter = 0  # incremental order for keys

LINGER = 1.50	   # 30 ms minimum key visibility
WPM_WINDOW = 10.0   # seconds for WPM calculation

# ----------------------------
# Keyboard handlers
# ----------------------------

def on_press(event):
	global order_counter
	name = normalize(event.name)
	now = time.time()

	if name not in keys:
		keys[name] = {"last": now, "count": 0, "order": order_counter}
		order_counter += 1

	keys[name]["last"] = now
	keys[name]["count"] += 1
	keys[name]["order"] = order_counter
	order_counter += 1

	# track chars for WPM
	if len(name) == 1 or name == "Space":
		char_times.append(now)

def on_release(event):
	name = normalize(event.name)
	if name in keys:
		keys[name]["last"] = time.time()

def kb_loop():
	keyboard.on_press(on_press)
	keyboard.on_release(on_release)
	keyboard.wait()

# ----------------------------
# Web HTML
# ----------------------------
HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {
	margin: 0;
	background: transparent;
	color: white;
	font-family: sans-serif;
}

#container {
	display: flex;
	flex-direction: column;
	gap: 12px;
	align-items: flex-start; /* children shrink to fit content */
}

#wpm {
	display: inline-block;	/* shrink to text width */
	font-size: 24px;
	line-height: 1;
	background: black;
	color: white;
	padding: 2px 14px;		/* small top/bottom, left/right padding */
	border-radius: 8px;
}

#keys {
	display: flex;
	gap: 6px;
	flex-wrap: wrap;
}

.key {
	position: relative;
	padding: 14px 18px;
	background: black;
	border-radius: 8px;
	font-size: 16px;
}

.count {
	position: absolute;
	bottom: 4px;
	right: 6px;
	font-size: 14px;
	opacity: 0.7;
}
</style>
</head>
<body>

<div id="container">
	<div id="wpm">WPM: 0</div>
	<div id="keys"></div>
</div>

<script>
async function update() {
	const r = await fetch("/kc/state");
	const data = await r.json();

	// update WPM text
	document.getElementById("wpm").textContent = "WPM: " + data.wpm;

	const el = document.getElementById("keys");
	el.innerHTML = "";

	// sort keys by press order
	data.keys.sort((a,b) => a.order - b.order);

	data.keys.forEach(k => {
		const d = document.createElement("div");
		d.className = "key";
		d.textContent = k.name.toUpperCase();

		const c = document.createElement("div");
		c.className = "count";
		c.textContent = k.count;

		d.appendChild(c);
		el.appendChild(d);
	});
}

// poll every 10ms (practical for OBS)
setInterval(update, 10);
</script>

</body>
</html>
"""
# ----------------------------
# Flask routes
# ----------------------------

@app.route("/kc")
def index():
	return render_template_string(HTML)

@app.route("/kc/state")
def state():
	now = time.time()

	# keys currently visible (linger)
	visible = []
	for name, data in keys.items():
		if now - data["last"] <= LINGER:
			visible.append({
				"name": name,
				"count": data["count"],
				"order": data["order"]
			})

	# WPM calculation
	cutoff = now - WPM_WINDOW
	recent = [t for t in char_times if t >= cutoff]
	chars = len(recent)
	wpm = int((chars / 5) * (60 / WPM_WINDOW))

	return jsonify({"keys": visible, "wpm": wpm})

# ----------------------------
# Entry point
# ----------------------------

if __name__ == "__main__":
	threading.Thread(target=kb_loop, daemon=True).start()
	app.run(host="127.0.0.1", port=9999)
