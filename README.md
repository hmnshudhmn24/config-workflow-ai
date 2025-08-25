# 🤖🛠️ askcfg — AI Workflow for Config Files (YAML/JSON/Kubernetes)

Turn natural-language prompts into **config edits** or **fresh manifests**.  
Works offline with a rule-based planner, with a clean hook to drop in your LLM later.

> “Set replicas to 3, image to `nginx:1.25`, add env `FOO=bar`, and enable autoscaling to 50–80% CPU.”

---

## ✨ Features
- 🧠 **NLU** (rule-based) for common infra intents: replicas, image, env, ports, names, autoscaling, generic `set path=value`.
- 📦 **Formats**: YAML & JSON (auto-detect), multi-doc YAML supported.
- ☸️ **Kubernetes-aware**: Create/patch **Deployment**, add **HPA** when you say “enable autoscaling”.
- 🧪 **Safe edits**: `--plan`, `--diff`, and `--backup`.
- 🔌 **Bring-your-own-LLM**: Drop-in hook in `engine.py` to swap the planner.

---

## 📦 Install
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🚀 Quick Start

### 1) Edit an existing Kubernetes Deployment
```bash
python askcfg.py "set replicas to 3 and image to nginx:1.25" \
  -i examples/deployment.yaml --diff --backup
```
- Shows a color diff, updates `spec.replicas` and container image, creates `deployment.yaml.bak`.

### 2) Add env and port
```bash
python askcfg.py "add env FOO=bar, port to 8080" -i examples/deployment.yaml --diff
```

### 3) Enable autoscaling (adds a second YAML doc for HPA)
```bash
python askcfg.py "enable autoscaling min=2 max=6 cpu=70%" \
  -i examples/deployment.yaml --diff --multi
```
> Use `--multi` to write multi-doc YAML (Deployment + HPA separated by `---`).

### 4) Create a new Deployment from a prompt (no input file)
```bash
python askcfg.py "create deployment named api set replicas=2 image=ghcr.io/acme/api:1.0" \
  -o api.yaml
```

### 5) Generic JSON edit
```bash
python askcfg.py "set logging.level to DEBUG and set service.port to 9090" \
  -i examples/config.json --diff
```

---

## 🧩 How It Works
1. **Planner** (`src/engine.py`) parses your prompt into **actions**:
   - `{"op":"set","path":"spec.replicas","value":3}`
   - `{"op":"image","value":"nginx:1.25"}`
   - `{"op":"env_add","name":"FOO","value":"bar"}`
   - `{"op":"autoscale","min":2,"max":6,"cpu":0.7}`
2. **Transformer** (`src/transforms.py`) applies actions to the loaded object(s). If autoscaling is requested, it emits an **HPA** manifest as an extra YAML document.
3. **I/O** (`src/io_utils.py`) handles format detection, multi-doc YAML, **diffs**, and **backups**.

---

## 🛡️ Safety & Idempotency
- Use `--plan` to preview the actions:
  ```bash
  python askcfg.py "set replicas to 5 and image to registry.io/foo:2.0" --plan
  ```
- Use `--diff` to see a unified, colorized diff before writing.
- Use `--backup` for in-place edits.

---

## 📚 Supported Intents (Rule-Based)
- **K8s**
  - `replicas`, `image`, `name`, `port`, `env`, `enable autoscaling min=? max=? cpu=?%`
  - `create deployment/service named ...`
- **Generic YAML/JSON**
  - `set dotted.path.to.key to value`
  - Arrays via simple indices: `set items[0].value to 42`

> Anything not matched falls back to annotations under `metadata.annotations.askcfg.*` to avoid silent failure.

---

## 🔭 Examples

**Before**
```yaml
# examples/deployment.yaml
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: web
        image: nginx:latest
```

**Prompt**
```
set replicas to 3 and image to nginx:1.25
```

**After (diff)**
```diff
@@
-spec:
-  replicas: 1
+spec:
+  replicas: 3
@@
-        image: nginx:latest
+        image: nginx:1.25
```

---

## 🧪 Tests (manual)
- Run the quick-start commands above.
- Validate multi-doc output when enabling autoscaling.
- Try generic JSON edit on `examples/config.json`.

---

## 📜 License
MIT — Have fun automating config edits! 🎉
