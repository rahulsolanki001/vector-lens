"""
vlens.cli — Command-line interface.

Entry point for the `vlens` command installed by pip.

Commands:
    vlens serve   Start the debug UI server
    vlens check   Run a quick health check on configured backends
    vlens eval    Run an evaluation job from the CLI (no UI)
    vlens dev     Development mode: server + Vite hot-reload in parallel
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="vlens",
    help="Vector Lens — Vector database debugger and visualizer.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def serve(
    config: str = typer.Option("vlens.yaml", "--config", "-c", help="Path to vlens.yaml"),
    port: int = typer.Option(7842, "--port", "-p", help="Server port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open browser on start"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev only)"),
) -> None:
    """Start the Vector Lens debug UI server."""
    import uvicorn

    if not Path(config).exists():
        console.print(
            f"[red]Config file not found:[/red] {config}\n"
            "Copy the example and fill in your backends:\n"
            "  cp vlens.yaml.example vlens.yaml",
            highlight=False,
        )
        raise typer.Exit(code=1)

    url = f"http://localhost:{port}"
    console.print(f"[bold green]Vector Lens[/bold green] starting on {url}")

    if not no_browser:

        def _open() -> None:
            import time

            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    if reload:
        # reload=True requires a string import path, not an app object
        os.environ["VLENS_CONFIG"] = config
        uvicorn.run(
            "vlens.server.app:app",
            host="0.0.0.0",
            port=port,
            reload=True,
        )
    else:
        from vlens.server.app import create_app

        uvicorn.run(create_app(config_path=config), host="0.0.0.0", port=port)


@app.command()
def check(
    config: str = typer.Option("vlens.yaml", "--config", "-c", help="Path to vlens.yaml"),
    backend: str = typer.Option("", "--backend", "-b", help="Check specific backend only"),
) -> None:
    """Run health checks on all configured backends and print a report."""
    from vlens.adapters import build_adapter
    from vlens.config.loader import get_adapter_configs, load_config
    from vlens.core.health import health_check

    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    adapter_configs = get_adapter_configs(cfg)

    async def _run() -> None:
        for adapter_cfg in adapter_configs:
            if backend and adapter_cfg.name != backend:
                continue

            adapter = build_adapter(adapter_cfg)
            try:
                await adapter.connect()
            except Exception as exc:
                console.print(f"[red]Failed to connect to '{adapter_cfg.name}':[/red] {exc}")
                continue

            collections = await adapter.list_collections()
            if not collections:
                console.print(f"[yellow]{adapter_cfg.name}[/yellow]: no collections found")
                await adapter.disconnect()
                continue

            for coll in collections:
                report = await health_check(adapter, coll.name)
                _print_health_report(adapter_cfg.name, coll.name, report)

            await adapter.disconnect()

    asyncio.run(_run())


@app.command(name="eval")
def eval_cmd(
    dataset: str = typer.Argument(..., help="Path to dataset CSV"),
    backend: str = typer.Option(..., "--backend", "-b", help="Backend name from vlens.yaml"),
    collection: str = typer.Option(..., "--collection", help="Collection name"),
    config: str = typer.Option("vlens.yaml", "--config", "-c", help="Path to vlens.yaml"),
    output: str = typer.Option("vlens_eval_results.json", "--output", "-o", help="Output JSON file"),
    k: int = typer.Option(10, "--k", help="Ranking cutoff depth"),
) -> None:
    """Run an evaluation job from the command line and write results to JSON."""
    from vlens.adapters import build_adapter
    from vlens.config.loader import get_adapter_configs, load_config
    from vlens.eval.loaders import CSVLoader
    from vlens.eval.runner import run_eval

    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        eval_dataset = CSVLoader().load(dataset)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Dataset error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    adapter_cfg = next((a for a in get_adapter_configs(cfg) if a.name == backend), None)
    if adapter_cfg is None:
        console.print(f"[red]Backend '{backend}' not found in config.[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        adapter = build_adapter(adapter_cfg)
        await adapter.connect()

        final = None
        with console.status(f"Evaluating {eval_dataset.query_count} queries…"):
            async for progress in run_eval(eval_dataset, collection, adapter, k=k):
                final = progress

        await adapter.disconnect()

        if final is None:
            console.print("[yellow]No results produced.[/yellow]")
            return

        result = {
            "dataset": eval_dataset.name,
            "backend": backend,
            "collection": collection,
            "k": k,
            "total_queries": final.total,
            "metrics": final.metrics,
            "latency_ms": final.latency_ms,
        }
        Path(output).write_text(json.dumps(result, indent=2))
        console.print(f"[green]Results written to[/green] {output}")
        _print_eval_summary(result)

    asyncio.run(_run())


@app.command()
def dev() -> None:
    """Development mode: server with --reload and Vite dev server in parallel."""
    ui_dir = Path("ui")
    if not ui_dir.exists():
        console.print("[red]ui/ directory not found. Run from the project root.[/red]")
        raise typer.Exit(code=1)

    console.print("[bold green]Vector Lens dev mode[/bold green] — Ctrl+C to stop")

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vlens.server.app:app", "--reload", "--port", "7842"],
        env={**os.environ, "VLENS_CONFIG": "vlens.yaml"},
    )
    vite_proc = subprocess.Popen(["npm", "run", "dev"], cwd=str(ui_dir))

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server_proc.terminate()
        vite_proc.terminate()


# ── Pretty-print helpers ──────────────────────────────────────────────────────


def _print_health_report(backend_name: str, collection: str, report: object) -> None:
    from vlens.adapters.base import HealthReport

    if not isinstance(report, HealthReport):
        return

    status_color = {
        "healthy": "green",
        "degraded": "yellow",
        "unhealthy": "red",
    }.get(report.status, "white")

    console.print(
        f"\n[bold]{backend_name}[/bold] / [cyan]{collection}[/cyan]  "
        f"[{status_color}]{report.status.upper()}[/{status_color}]  "
        f"({report.latency_ms:.0f} ms)"
    )

    if not report.findings:
        console.print("  [dim]No findings.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Severity", style="dim", width=10)
    table.add_column("Code", width=32)
    table.add_column("Message")

    severity_colors = {"error": "red", "warning": "yellow", "info": "blue"}
    for finding in report.findings:
        color = severity_colors.get(finding.severity, "white")
        table.add_row(
            f"[{color}]{finding.severity}[/{color}]",
            finding.code,
            finding.message,
        )

    console.print(table)


def _print_eval_summary(result: dict[str, Any]) -> None:
    table = Table(title="Eval Results", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    for key, value in result["metrics"].items():
        table.add_row(key, f"{value:.4f}")

    for key, value in result["latency_ms"].items():
        table.add_row(f"latency {key}", f"{value:.1f} ms")

    console.print(table)


if __name__ == "__main__":
    app()
