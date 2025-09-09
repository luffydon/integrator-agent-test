import json, pathlib
BASE = pathlib.Path(__file__).resolve().parent / "configs"
def load_json(name: str):
    with open(BASE / name, "r", encoding="utf-8") as f: return json.load(f)
def load_configs():
    return {"aliases":load_json("aliases.json"),
            "weights":load_json("weights.json"),
            "negations":load_json("negations.json"),
            "slot_policies":load_json("slot_policies.json")}
