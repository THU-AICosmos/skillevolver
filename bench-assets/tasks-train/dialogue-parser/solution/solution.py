import sys
import re
import json
import os

# Add skill to path
sys.path.append('environment/skills/dialogue_graph/scripts')
sys.path.append('/root/.claude/skills/dialogue_graph/scripts')
from dialogue_graph import Graph, Node, Edge


def build_graph_from_script(script_file):
    """Read a dialogue script file and construct a Graph object."""
    graph = Graph()
    active_section = None

    with open(script_file, "r", encoding="utf-8") as fh:
        raw_lines = fh.readlines()

    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # Detect section headers like [NodeID]
        sec_match = re.match(r'^\[([^\]]+)\]$', stripped)
        if sec_match:
            active_section = sec_match.group(1)
            if active_section not in graph.nodes:
                graph.add_node(Node(id=active_section, text="", speaker="", type="line"))
            continue

        if active_section is None:
            continue

        current = graph.nodes[active_section]

        # Extract target after ->
        dest = None
        body = stripped
        if "->" in stripped:
            halves = stripped.rsplit("->", 1)
            body = halves[0].strip()
            dest = halves[1].strip()

        # Numbered choices: "N. text" or "N. [Tag] text"
        opt_match = re.match(r'^(\d+)\.\s+(.+)$', body)
        if opt_match:
            current.type = "choice"
            current.text = ""
            current.speaker = ""
            if dest:
                graph.add_edge(Edge(source=active_section, target=dest, text=body))
        elif ":" in body:
            colon_idx = body.index(":")
            who = body[:colon_idx].strip()
            what = body[colon_idx + 1:].strip()
            current.speaker = who
            current.text = what
            current.type = "line"
            if dest:
                graph.add_edge(Edge(source=active_section, target=dest, text=""))
        else:
            if dest:
                graph.add_edge(Edge(source=active_section, target=dest, text=""))

    return graph


def run():
    base = "/app" if os.path.exists("/app") else "."
    src = os.path.join(base, "script.txt")
    json_out = os.path.join(base, "dialogue.json")

    if not os.path.exists(src):
        src = "script.txt"
        json_out = "dialogue.json"

    g = build_graph_from_script(src)

    issues = g.validate()
    if issues:
        print("Validation notes:")
        for msg in issues:
            print(f"  * {msg}")

    with open(json_out, "w") as fp:
        fp.write(g.to_json())

    dot_base = os.path.join(base, "dialogue")
    try:
        g.visualize(dot_base, format='dot')
        candidate = dot_base + ".dot"
        if os.path.exists(candidate):
            pass  # already in place
    except Exception as exc:
        print(f"Viz warning: {exc}")

    print(f"Wrote {json_out}: {len(g.nodes)} nodes, {len(g.edges)} edges")


if __name__ == "__main__":
    run()
