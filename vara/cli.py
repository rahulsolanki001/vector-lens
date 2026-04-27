"""
vara.cli — Command-line interface.

Entry point for the `vara` command installed by pip.

Commands:
    vara serve   Start the debug UI server
    vara check   Run a quick health check on configured backends
    vara eval    Run an evaluation job from the CLI (no UI)
    vara dev     Development mode: server + Vite hot-reload in parallel
"""

import typer

app = typer.Typer(
    name="vara",
    help="Vara — Vector database debugger and visualizer.",
    no_args_is_help=True,
)


@app.command()
def serve(
    config: str = typer.Option("vara.yaml", "--config", "-c", help="Path to vara.yaml"),
    port: int = typer.Option(7842, "--port", "-p", help="Server port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open browser on start"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev only)"),
) -> None:
    """Start the Vara debug UI server."""
    raise NotImplementedError


@app.command()
def check(
    config: str = typer.Option("vara.yaml", "--config", "-c", help="Path to vara.yaml"),
    backend: str = typer.Option("", "--backend", "-b", help="Check specific backend only"),
) -> None:
    """Run health checks on all configured backends and print a report."""
    raise NotImplementedError


@app.command()
def eval_cmd(
    dataset: str = typer.Argument(..., help="Path to dataset (CSV or BEIR)"),
    backend: str = typer.Option(..., "--backend", "-b", help="Backend name to evaluate"),
    collection: str = typer.Option(..., "--collection", help="Collection name"),
    config: str = typer.Option("vara.yaml", "--config", "-c", help="Path to vara.yaml"),
    output: str = typer.Option("vara_eval_results.json", "--output", "-o", help="Output file"),
) -> None:
    """Run an evaluation job from the command line."""
    raise NotImplementedError


@app.command()
def dev() -> None:
    """Development mode: server with --reload and Vite dev server in parallel."""
    raise NotImplementedError


if __name__ == "__main__":
    app()