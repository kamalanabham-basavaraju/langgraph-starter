"""Write the current LangGraph workflow as Mermaid source."""

from pathlib import Path

from app.graph.workflow import graph


def main() -> None:
    output = Path("docs/incident_workflow.mmd")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(graph.get_graph().draw_mermaid(), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
