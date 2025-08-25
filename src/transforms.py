from copy import deepcopy

def _split_path(path: str):
    # supports a.b[0].c
    import re
    tokens = []
    for part in path.split("."):
        idxs = re.findall(r"\[(\d+)\]", part)
        key = part.split("[")[0]
        if key:
            tokens.append(key)
        for i in idxs:
            tokens.append(int(i))
    return tokens

def _ensure(obj, token):
    if isinstance(token, int):
        if not isinstance(obj, list):
            # convert to list
            return []
        while len(obj) <= token:
            obj.append({})
        return obj
    else:
        if not isinstance(obj, dict):
            return {}
        if token not in obj:
            obj[token] = {}
        return obj

def set_by_path(root, path: str, value):
    tokens = _split_path(path)
    obj = root
    for i, tok in enumerate(tokens):
        last = (i == len(tokens)-1)
        if last:
            if isinstance(tok, int):
                if not isinstance(obj, list):
                    raise TypeError(f"Path expects list at token {tok}")
                while len(obj) <= tok:
                    obj.append(None)
                obj[tok] = value
            else:
                if not isinstance(obj, dict):
                    raise TypeError(f"Path expects dict at token {tok}")
                obj[tok] = value
        else:
            # descend
            if isinstance(tok, int):
                if not isinstance(obj, list):
                    raise TypeError(f"Path expects list at token {tok}")
                while len(obj) <= tok:
                    obj.append({})
                if not isinstance(obj[tok], (dict, list)):
                    obj[tok] = {}
                obj = obj[tok]
            else:
                if not isinstance(obj, dict):
                    raise TypeError(f"Path expects dict at token {tok}")
                if tok not in obj or not isinstance(obj[tok], (dict, list)):
                    obj[tok] = {}
                obj = obj[tok]
    return root

def _find_container(spec, name_hint=None):
    try:
        containers = spec["template"]["spec"]["containers"]
    except Exception:
        return None, None
    if not containers:
        return None, None
    if name_hint:
        for c in containers:
            if c.get("name") == name_hint:
                return c, containers
    return containers[0], containers

def ensure_deployment(obj):
    if not isinstance(obj, dict) or obj.get("kind") != "Deployment":
        # upgrade to Deployment shell if looks generic
        return {
            "apiVersion":"apps/v1",
            "kind":"Deployment",
            "metadata":{"name":"app"},
            "spec":{
                "replicas": 1,
                "selector":{"matchLabels":{"app":"app"}},
                "template":{
                    "metadata":{"labels":{"app":"app"}},
                    "spec":{"containers":[{"name":"app","image":"nginx:latest"}]}
                }
            }
        }
    return obj

def ensure_service_for(deploy, port=80, targetPort=None):
    name = deploy.get("metadata",{}).get("name","app")
    if targetPort is None:
        c, _ = _find_container(deploy.get("spec",{}), None)
        if c:
            # try first port
            p = c.get("ports",[{"containerPort":port}])[0].get("containerPort", port)
            targetPort = p
        else:
            targetPort = port
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name},
        "spec": {
            "selector": {"app": name},
            "ports": [{"port": port, "targetPort": targetPort}]
        }
    }

def apply_actions(obj, actions, prompt=""):
    doc = deepcopy(obj)
    extras = {"autoscaling": []}
    container_hint = None

    # upgrade to deployment if needed for k8s-focused intents
    for a in actions:
        if a.get("op") == "create_kind" and a.get("kind") == "k8s:Deployment":
            doc = ensure_deployment(doc)
            break

    for a in actions:
        op = a.get("op")
        if op == "container_hint":
            container_hint = a.get("container")
        elif op == "k8s_name":
            doc.setdefault("metadata",{})["name"] = a["name"]
            # also propagate to labels/selectors if looks like Deployment
            try:
                doc["spec"]["selector"]["matchLabels"]["app"] = a["name"]
                doc["spec"]["template"]["metadata"]["labels"]["app"] = a["name"]
            except Exception:
                pass
        elif op == "set":
            try:
                set_by_path(doc, a["path"], a["value"])
            except Exception:
                # best effort: attach under metadata.annotations if path invalid
                ann = doc.setdefault("metadata",{}).setdefault("annotations",{})
                ann[f"askcfg.failed.{a['path']}"] = str(a["value"])
        elif op == "image":
            # find container
            doc = ensure_deployment(doc)
            c, containers = _find_container(doc.get("spec",{}), container_hint)
            if c is None:
                # create container list
                doc.setdefault("spec",{}).setdefault("template",{}).setdefault("spec",{})["containers"] = [{"name": container_hint or "app", "image": a["value"]}]
            else:
                c["image"] = a["value"]
        elif op == "port":
            doc = ensure_deployment(doc)
            c, containers = _find_container(doc.get("spec",{}), container_hint)
            if c is None:
                c = {"name": container_hint or "app", "image":"nginx:latest"}
                containers.append(c)
            ports = c.setdefault("ports",[])
            if ports:
                ports[0]["containerPort"] = a["containerPort"]
            else:
                ports.append({"containerPort": a["containerPort"]})
        elif op == "env_add":
            doc = ensure_deployment(doc)
            c, containers = _find_container(doc.get("spec",{}), container_hint)
            if c is None:
                c = {"name": container_hint or "app", "image":"nginx:latest"}
                containers.append(c)
            env = c.setdefault("env",[])
            # replace if exists
            for e in env:
                if e.get("name")==a["name"]:
                    e["value"]=a["value"]
                    break
            else:
                env.append({"name": a["name"], "value": a["value"]})
        elif op == "autoscale":
            extras["autoscaling"].append({
                "min": a.get("min",1),
                "max": a.get("max",5),
                "cpu": a.get("cpu",0.7)
            })

    return doc, extras

def k8s_enable_autoscaling(deploy, min=1, max=5, cpu=0.7):
    # produce an HPA manifest wired to the deployment name
    name = deploy.get("metadata",{}).get("name","app")
    return {
        "apiVersion":"autoscaling/v2",
        "kind":"HorizontalPodAutoscaler",
        "metadata":{"name": name},
        "spec":{
            "scaleTargetRef":{"apiVersion":"apps/v1","kind":"Deployment","name": name},
            "minReplicas": int(min),
            "maxReplicas": int(max),
            "metrics":[{"type":"Resource","resource":{
                "name":"cpu",
                "target":{"type":"Utilization","averageUtilization": int(round(cpu*100))}
            }}]
        }
    }
