import typer, asyncio, yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from moss_ci.parser.yaml_parser import parse_suite, parse_suite_string
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig

app = typer.Typer(name="moss-ci", help="Moss CI — AI Agent Evaluation Platform")
console = Console()


@app.command()
def run(
    path: str = typer.Argument("./suites", help="Suite file or directory"),
    test_name: str = typer.Option(None, "--test", help="Run a specific test"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    concurrency: int = typer.Option(10, "--concurrency", "-c"),
):
    """Run test suites."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    suite_files = [p] if p.is_file() else sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
    if not suite_files:
        console.print(f"[red]Error:[/red] No YAML files found in {path}")
        raise typer.Exit(1)

    suites = []
    for f in suite_files:
        try:
            suites.append(parse_suite(str(f)))
            console.print(f"[green]✓[/green] Loaded: {f.name}")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed: {f.name} — {e}")

    if not suites:
        raise typer.Exit(1)

    async def _run():
        engine = PipelineEngine(PipelineConfig(fail_fast=fail_fast, max_concurrency=concurrency))
        return await engine.run(suites)

    console.print(f"\nRunning {sum(len(s.tests) for s in suites)} tests across {len(suites)} suites...\n")
    result = asyncio.run(_run())

    table = Table(title="Results")
    table.add_column("Suite", style="cyan")
    table.add_column("Passed", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Error", style="yellow")
    for s in result.suites:
        table.add_row(s.suite_name, str(s.passed), str(s.failed), str(s.error))
    console.print(table)
    console.print(f"\n[bold]{result.summary}[/bold]")
    if result.status.value == "failed":
        raise typer.Exit(1)


@app.command()
def status(run_id: str = typer.Argument(..., help="Run ID")):
    """Show run status."""
    console.print(f"[yellow]Status for {run_id}:[/yellow] not available (API not running)")


@app.command()
def logs(run_id: str = typer.Argument(..., help="Run ID"), test_name: str = typer.Option(None, "--test")):
    """Show run logs."""
    console.print(f"[yellow]Logs for {run_id}:[/yellow] not available (API not running)")


@app.command()
def history(limit: int = typer.Option(20, "--limit", "-n")):
    """Show run history."""
    console.print("[yellow]History:[/yellow] not available (API not running)")


@app.command()
def diff(run_id_1: str = typer.Argument(...), run_id_2: str = typer.Argument(...)):
    """Compare two runs."""
    console.print(f"[yellow]Diff {run_id_1} vs {run_id_2}:[/yellow] not available (API not running)")


@app.command()
def init():
    """Initialize a moss-ci project."""
    config = {"version": "1.0", "suites_dir": "./suites"}
    p = Path("moss-ci.yaml")
    if p.exists():
        console.print("[yellow]moss-ci.yaml already exists[/yellow]")
        return
    p.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")
    Path("./suites").mkdir(exist_ok=True)
    console.print("[green]✓[/green] Created moss-ci.yaml and suites/")


@app.command()
def validate(path: str = typer.Argument("./suites", help="Suite file or directory")):
    """Validate suite YAML files."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    files = [p] if p.is_file() else sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
    if not files:
        console.print(f"[red]Error:[/red] No YAML files found")
        raise typer.Exit(1)

    errors = 0
    for f in files:
        try:
            parse_suite(str(f))
            console.print(f"[green]✓[/green] {f.name}")
        except Exception as e:
            console.print(f"[red]✗[/red] {f.name}: {e}")
            errors += 1
    if errors:
        console.print(f"\n[red]{errors} file(s) failed validation[/red]")
        raise typer.Exit(1)
    console.print(f"\n[green]All {len(files)} file(s) valid[/green]")


if __name__ == "__main__":
    app()
