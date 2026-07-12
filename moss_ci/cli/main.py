import typer, asyncio, uuid, yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from moss_ci.parser.yaml_parser import parse_suite, parse_suite_string
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.engine.diff import DiffEngine
from moss_ci.runner.base import MossRunner
from moss_ci.storage.db import get_db
from moss_ci.storage.repository import RunRepository

app = typer.Typer(name="moss-ci", help="Moss CI — AI Agent Evaluation Platform")
console = Console()


@app.command()
def run(
    path: str = typer.Argument("./suites", help="Suite file or directory"),
    test_name: str = typer.Option(None, "--test", help="Run a specific test"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    concurrency: int = typer.Option(10, "--concurrency", "-c"),
    mock: bool = typer.Option(False, "--mock", help="Use mock Moss output (no real Moss invoked)"),
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

    # mock=False (default) invokes a real MossRunner that auto-detects the
    # backend from env (MOSS_CLI_COMMAND / MOSS_API_URL / moss SDK).
    # --mock keeps the scaffold behavior ([mock] Moss: <prompt>) for runs
    # where no Moss instance is available.
    runner = None if mock else MossRunner()

    async def _run():
        engine = PipelineEngine(PipelineConfig(fail_fast=fail_fast, max_concurrency=concurrency), runner=runner)
        return await engine.run(suites)

    console.print(f"\nRunning {sum(len(s.tests) for s in suites)} tests across {len(suites)} suites...\n")
    result = asyncio.run(_run())

    # Persist the run so `history`/`status`/`diff` can read it back.
    run_id = result.run_id or uuid.uuid4().hex[:8]
    result.run_id = run_id

    async def _save():
        db = get_db()
        await db.init()
        await RunRepository(db).save(result)

    asyncio.run(_save())

    table = Table(title="Results")
    table.add_column("Suite", style="cyan")
    table.add_column("Passed", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Error", style="yellow")
    for s in result.suites:
        table.add_row(s.suite_name, str(s.passed), str(s.failed), str(s.error))
    console.print(table)
    console.print(f"\n[bold]{result.summary}[/bold]")
    console.print(f"[dim]run_id: {run_id}  (use `moss-ci diff <prev> {run_id}` to compare)[/dim]")
    if result.status.value == "failed":
        raise typer.Exit(1)


@app.command()
def status(run_id: str = typer.Argument(..., help="Run ID")):
    """Show run status."""
    async def _get():
        db = get_db()
        await db.init()
        return await RunRepository(db).get(run_id)
    result = asyncio.run(_get())
    if result is None:
        console.print(f"[red]Run not found:[/red] {run_id}")
        raise typer.Exit(1)
    console.print(f"[bold]{run_id}[/bold]  {result.status.value}  {result.summary}")
    for s in result.suites:
        console.print(f"  {s.suite_name}: {s.passed}/{s.total} passed")
        for t in s.tests:
            color = "green" if t.status == "pass" else ("red" if t.status == "fail" else "yellow")
            console.print(f"    [{color}]{t.status:6}[/] {t.test_name}")


@app.command()
def logs(run_id: str = typer.Argument(..., help="Run ID"), test_name: str = typer.Option(None, "--test")):
    """Show run logs."""
    async def _get():
        db = get_db()
        await db.init()
        return await RunRepository(db).get(run_id)
    result = asyncio.run(_get())
    if result is None:
        console.print(f"[red]Run not found:[/red] {run_id}")
        raise typer.Exit(1)
    for s in result.suites:
        for t in s.tests:
            if test_name and t.test_name != test_name:
                continue
            console.print(f"[bold]{t.test_name}[/bold] ({t.status}):")
            console.print(t.moss_output[:500])


@app.command()
def history(limit: int = typer.Option(20, "--limit", "-n")):
    """Show run history."""
    async def _list():
        db = get_db()
        await db.init()
        return await RunRepository(db).list(limit=limit)
    runs = asyncio.run(_list())
    if not runs:
        console.print("[yellow]No runs yet.[/yellow]")
        return
    table = Table(title="Run History")
    table.add_column("Run ID", style="cyan")
    table.add_column("Pipeline")
    table.add_column("Status")
    table.add_column("Summary")
    for r in runs:
        color = "green" if r.status.value == "success" else "red"
        table.add_row(r.run_id, r.pipeline_name, f"[{color}]{r.status.value}[/]", r.summary)
    console.print(table)


@app.command()
def diff(run_id_1: str = typer.Argument(..., help="Previous run ID"),
         run_id_2: str = typer.Argument(..., help="Current run ID")):
    """Compare two runs (regression analysis)."""
    async def _get():
        db = get_db()
        await db.init()
        repo = RunRepository(db)
        return await repo.get(run_id_1), await repo.get(run_id_2)
    prev, curr = asyncio.run(_get())
    if prev is None:
        console.print(f"[red]Previous run not found:[/red] {run_id_1}")
        raise typer.Exit(1)
    if curr is None:
        console.print(f"[red]Current run not found:[/red] {run_id_2}")
        raise typer.Exit(1)
    d = DiffEngine().compare(curr, prev)
    console.print(f"[bold]Regression diff[/bold]: {run_id_1} (prev)  vs  {run_id_2} (curr)\n")
    if not (d.new_failures or d.fixed or d.improved or d.degraded):
        console.print("[green]No changes — same results in both runs.[/green]")
        return
    if d.new_failures:
        console.print(f"[red]⚠ {len(d.new_failures)} new failure(s):[/red]")
        for it in d.new_failures:
            console.print(f"    {it.test_name}  {it.previous_status} → {it.current_status}")
    if d.fixed:
        console.print(f"[green]✓ {len(d.fixed)} fixed:[/green]")
        for it in d.fixed:
            console.print(f"    {it.test_name}  {it.previous_status} → {it.current_status}")
    if d.improved:
        console.print(f"[green]↑ {len(d.improved)} improved:[/green]")
        for it in d.improved:
            console.print(f"    {it.test_name}  {it.previous_score} → {it.current_score}")
    if d.degraded:
        console.print(f"[red]↓ {len(d.degraded)} degraded:[/red]")
        for it in d.degraded:
            console.print(f"    {it.test_name}  {it.previous_score} → {it.current_score}")


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
