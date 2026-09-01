#!/usr/bin/env python3
"""Cortex public slice — auto-discover Flask blueprints from modules/."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for path in (ROOT, os.path.join(ROOT, "lib")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(ROOT), ".env"))
except ImportError:
    pass

from flask import Flask, jsonify, render_template
from flask_cors import CORS

import config

app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"))
app.secret_key = config.SECRET_KEY
CORS(app)

NAV_ITEMS = []
MOD_DIR = os.path.join(ROOT, "modules")

for fname in sorted(os.listdir(MOD_DIR)):
    if fname.startswith("_") or not fname.endswith(".py"):
        continue
    mod_id = fname[:-3]
    spec = importlib.util.spec_from_file_location(
        f"cortex_mod_{mod_id}", os.path.join(MOD_DIR, fname)
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"[cortex] failed to load {fname}: {exc}")
        continue
    if not hasattr(mod, "bp"):
        continue
    app.register_blueprint(mod.bp)
    NAV_ITEMS.append({
        "id": mod_id,
        "label": getattr(mod, "LABEL", mod_id),
        "icon": getattr(mod, "ICON", ""),
        "url": f"/{mod_id}/",
        "section": getattr(mod, "SECTION", "Tools"),
        "order": getattr(mod, "ORDER", 99),
    })
    print(f"[cortex] registered /{mod_id}/")

NAV_ITEMS.sort(key=lambda x: (x["section"], x["order"]))


@app.route("/health")
def health():
    return jsonify({"status": "ok", "tools": [i["id"] for i in NAV_ITEMS]})


@app.route("/")
def index():
    default = NAV_ITEMS[0]["url"] if NAV_ITEMS else "/"
    return render_template("shell.html", nav_items=NAV_ITEMS, default_url=default)


if __name__ == "__main__":
    print("[cortex] http://localhost:5000")
    app.run(port=5000, debug=False, threaded=True)
