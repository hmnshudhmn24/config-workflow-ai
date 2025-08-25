"""
Prompt → actions planner (rule-based).
Produces a list of actions the transformer can apply.

Action schema examples:
- {"op":"set", "path":"spec.replicas", "value":3}
- {"op":"image", "container":"app", "value":"nginx:1.25"}
- {"op":"env_add", "container":"app", "name":"FOO", "value":"bar"}
- {"op":"port", "container":"app", "containerPort":8080}
- {"op":"k8s_name", "name":"myapp"}
- {"op":"autoscale", "min":1, "max":5, "cpu":0.75}  # 75%
- {"op":"create_kind", "kind":"k8s:Deployment"}
- {"op":"set", "path":"logging.level", "value":"DEBUG"}  # generic JSON/YAML
"""
import re

def _number(s):
    try:
        return int(s)
    except:
        try:
            return float(s)
        except:
            return s

def plan_actions(prompt: str):
    p = prompt.lower()
    acts = []

    # infer create kind
    if "create" in p and "deployment" in p:
        acts.append({"op":"create_kind", "kind":"k8s:Deployment"})
    elif "create" in p and "service" in p:
        acts.append({"op":"create_kind", "kind":"k8s:Service"})

    # name
    m = re.search(r"(name|named)\s+([a-z0-9-_.]+)", p)
    if m:
        acts.append({"op":"k8s_name", "name":m.group(2)})

    # replicas
    m = re.search(r"(replica(s)?|replication)\s*(to|=)?\s*(\d+)", p)
    if m:
        acts.append({"op":"set", "path":"spec.replicas", "value":int(m.group(4))})

    # image
    m = re.search(r"image\s*(to|=)\s*([a-z0-9\-_.:/@]+)", p)
    if m:
        acts.append({"op":"image", "value":m.group(2)})

    # container name
    m = re.search(r"container\s+([a-z0-9-_.]+)", p)
    container_hint = m.group(1) if m else None
    if container_hint:
        acts.append({"op":"container_hint", "container":container_hint})

    # ports
    m = re.search(r"(port|containerport)\s*(to|=)?\s*(\d{2,5})", p)
    if m:
        acts.append({"op":"port", "containerPort":int(m.group(3))})

    # env additions: "add env FOO=bar" or "set env FOO=bar"
    for k, v in re.findall(r"(?:add|set)\s+env\s+([A-Z0-9_]+)\s*=\s*([^\s,;]+)", prompt):
        acts.append({"op":"env_add", "name":k, "value":v})

    # autoscaling: "enable autoscaling" + ranges or cpu percent
    if "enable autoscaling" in p or "autoscale" in p:
        minr = re.search(r"min\s*=?\s*(\d+)", p)
        maxr = re.search(r"max\s*=?\s*(\d+)", p)
        cpu = re.search(r"(cpu|utilization)\s*(to|=)?\s*(\d+)%?", p)
        acts.append({
            "op":"autoscale",
            "min": int(minr.group(1)) if minr else 1,
            "max": int(maxr.group(1)) if maxr else 5,
            "cpu": (int(cpu.group(3))/100.0) if cpu else 0.7
        })

    # generic sets: "set X.Y.Z to VALUE"
    for path, val in re.findall(r"set\s+([a-z0-9_.\[\]]+)\s+(?:to|=)\s+([^\s,;]+)", p):
        # avoid double-adding if replicas/image already caught
        if path not in ("spec.replicas",):
            acts.append({"op":"set", "path":path, "value":_number(val)})

    return acts

def ensure_k8s_kind(prompt: str):
    p = prompt.lower()
    if "k8s" in p or "kubernetes" in p or "deployment" in p or "service" in p:
        return "k8s:Deployment"
    return None
