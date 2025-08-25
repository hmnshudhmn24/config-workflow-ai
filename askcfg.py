#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from src.io_utils import (
    read_any, write_any, detect_format, make_backup,
    color_diff, load_yaml_multi, dump_yaml_multi
)
from src.engine import plan_actions, ensure_k8s_kind
from src.transforms import apply_actions, k8s_enable_autoscaling

def parse_args():
    p = argparse.ArgumentParser(
        description="askcfg: LLM-style natural language edits for YAML/JSON/Kubernetes configs"
    )
    p.add_argument("prompt", help="Natural-language instruction, e.g. 'set replicas to 3 and image to nginx:1.25'")
    p.add_argument("-i", "--input", help="Input YAML/JSON file (optional for create flows)")
    p.add_argument("-o", "--output", help="Output file (defaults to in-place edit if -i provided)")
    p.add_argument("--kind", help="For create flows: generic|k8s:Deployment|k8s:Service|k8s:HPA", default=None)
    p.add_argument("--plan", action="store_true", help="Print planned actions and exit")
    p.add_argument("--diff", action="store_true", help="Show a unified diff")
    p.add_argument("--backup", action="store_true", help="Make .bak backup when editing in place")
    p.add_argument("--multi", action="store_true", help="Treat YAML as multi-doc (--- separated)")
    return p.parse_args()

def main():
    args = parse_args()
    prompt = args.prompt.strip()

    # Plan: parse prompt into actions
    actions = plan_actions(prompt)
    if args.plan:
        print("PLANNED ACTIONS:")
        for i, a in enumerate(actions, 1):
            print(f"{i}. {a}")
        return 0

    # Load or initialize documents
    documents = []
    input_fmt = None
    src_path = Path(args.input) if args.input else None

    if src_path:
        if args.multi:
            documents = load_yaml_multi(src_path)
            input_fmt = "yaml"
        else:
            data, input_fmt = read_any(src_path)
            documents = [data]
    else:
        # create-flow: initialize based on requested kind or inferred from prompt
        kind_hint = args.kind or ensure_k8s_kind(prompt)
        if kind_hint and kind_hint.startswith("k8s:"):
            documents = [ {"apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":"app"},"spec":{"replicas":1,"selector":{"matchLabels":{"app":"app"}},"template":{"metadata":{"labels":{"app":"app"}},"spec":{"containers":[{"name":"app","image":"nginx:latest"}]}}}} ]
            input_fmt = "yaml"
        else:
            documents = [ {} ]
            input_fmt = "json"

    # Apply actions to each document (best effort)
    modified_docs = []
    autoscaling_requests = []
    for doc in documents:
        new_doc, extras = apply_actions(doc, actions, prompt=prompt)
        modified_docs.append(new_doc)
        autoscaling_requests.extend(extras.get("autoscaling", []))

    # Handle K8s autoscaling extras by generating HPA docs
    extra_docs = []
    for req in autoscaling_requests:
        hpa = k8s_enable_autoscaling(modified_docs[0], **req)
        if hpa:
            extra_docs.append(hpa)

    # Prepare output path
    out_path = Path(args.output) if args.output else (src_path if src_path else None)

    # Show diff if requested and we have input
    if args.diff and src_path:
        original_text = "\n".join(dump_yaml_multi(documents)) if args.multi or input_fmt=="yaml" else ""
        # for json diff, read as text again (simple: serialize before/after)
        if input_fmt == "json":
            from src.io_utils import dumps_json
            original_text = dumps_json(documents[0])
        new_text = "\n".join(dump_yaml_multi(modified_docs + extra_docs)) if (args.multi or input_fmt=="yaml") else ""
        if input_fmt == "json":
            from src.io_utils import dumps_json
            new_text = dumps_json(modified_docs[0])
        print(color_diff(original_text, new_text))

    # Write back
    if out_path:
        if args.backup and src_path and src_path.exists():
            make_backup(src_path)
        if input_fmt == "yaml":
            if args.multi or extra_docs:
                # write multi-doc
                text_docs = dump_yaml_multi(modified_docs + extra_docs)
                out_path.write_text("\n---\n".join(text_docs) + "\n")
            else:
                write_any(modified_docs[0], out_path, fmt="yaml")
        else:
            # json
            write_any(modified_docs[0], out_path, fmt="json")
        print(f"✅ Wrote: {out_path}")
    else:
        # print to stdout
        if input_fmt == "yaml":
            text_docs = dump_yaml_multi(modified_docs + extra_docs)
            print("\n---\n".join(text_docs))
        else:
            from src.io_utils import dumps_json
            print(dumps_json(modified_docs[0]))

    return 0

if __name__ == "__main__":
    sys.exit(main())
