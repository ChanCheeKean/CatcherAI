"""Generate the default evidence world and load it into LadybugDB."""

from pathlib import Path

from world import build_world, stats

import graph_store


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    output = root / "data" / "generated"
    graph_dir = output / "graph"
    graph = build_world()
    graph.write(graph_dir)
    store = graph_store.load(graph_dir, output / "evidence.lbug")
    store.close()
    stats(graph)


if __name__ == "__main__":
    main()
