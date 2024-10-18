
# Copy-pasted code from ComfyUI/nodes.py and changed to instead of loading models, just compute a map of which repo defines what nodes.
# This can be run on ComfyUI server and later during ComfyUI->python conversion (after removing unused nodes), to identify which custom nodes are truly needed.
# 

import sys
sys.path.insert(0, "./ComfyUI")
import nodes
import execution
import server

import os
import logging
import importlib
import traceback
import asyncio
import json


global_map = {}


def load_custom_node(module_path: str, ignore=set(), module_parent="custom_nodes") -> bool:
    node_names = []
    module_name = os.path.basename(module_path)
    if os.path.isfile(module_path):
        sp = os.path.splitext(module_path)
        module_name = sp[0]
    try:
        logging.debug("Trying to load custom node {}".format(module_path))
        if os.path.isfile(module_path):
            module_spec = importlib.util.spec_from_file_location(module_name, module_path)
            module_dir = os.path.split(module_path)[0]
        else:
            module_spec = importlib.util.spec_from_file_location(module_name, os.path.join(module_path, "__init__.py"))
            module_dir = module_path

        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)

        if hasattr(module, "NODE_CLASS_MAPPINGS") and getattr(module, "NODE_CLASS_MAPPINGS") is not None:
            for name, node_cls in module.NODE_CLASS_MAPPINGS.items():
                if name not in ignore:
                    node_names.append(name)
        else:
            logging.warning(f"Skip {module_path} module for custom nodes due to the lack of NODE_CLASS_MAPPINGS.")
    except Exception as e:
        logging.warning(traceback.format_exc())
        logging.warning(f"Cannot import {module_path} module for custom nodes: {e}")
    
    for name in node_names:
        if module_parent == "custom_nodes":
            repo = module_name
        elif module_parent == "comfy_extras":
            repo = "ComfyUI extras"
        global_map[name] = repo

    return len(node_names) > 0


if __name__ == "__main__":
    # Setup PromptServer instance since many custom nodes try to use it during module import
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server_instance = server.PromptServer(loop)
    execution.PromptQueue(server_instance)

    # Load the core built-in nodes
    for node_name in nodes.NODE_CLASS_MAPPINGS.keys():
        global_map[node_name] = "ComfyUI core"

    # Monkey-patch Comfy with our function that will collect that mapping
    nodes.load_custom_node = load_custom_node
    # Call Comfy to collect the built-in extras as well as all custom nodes
    nodes.init_extra_nodes()

    filepath = "nodes_repo_map.json"
    with open(filepath, "w") as f:
        json.dump(global_map, f)
    print(f"Saved {len(global_map.keys())} nodes to {filepath}")
