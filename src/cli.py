import json
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

app = typer.Typer(name="agent", help="Autonomous GitHub Platform Agent")
console = Console()


@app.command()
def run(instruction: str = typer.Argument(..., help="Natural language instruction to execute")):
    """Execute a natural language instruction on GitHub."""
    from src.agent.core import AgentCore

    console.print(Panel(f"[bold]{instruction}[/bold]", title="Instruction", border_style="blue"))

    agent = AgentCore()
    report = agent.run(instruction)

    _display_report(report)


@app.command()
def learn(pattern: str = typer.Argument("", help="Instruction pattern to analyze")):
    """Show the learning report — measurable improvement over time."""
    from src.agent.core import AgentCore

    agent = AgentCore()
    report = agent.get_learning_report(pattern)

    console.print(Panel("[bold]Learning Report[/bold]", border_style="green"))

    stats = report["execution_stats"]
    if stats["total_runs"] == 0:
        console.print("[yellow]No executions recorded yet.[/yellow]")
        return

    table = Table(title="Execution Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Runs", str(stats["total_runs"]))
    table.add_row("Avg Time (ms)", str(stats["avg_time_ms"]))
    table.add_row("Avg API Calls", str(stats["avg_api_calls"]))
    table.add_row("Success Rate", f"{stats['success_rate']:.0%}")
    table.add_row("First Run Time", f"{stats['first_run_time_ms']}ms")
    table.add_row("Latest Run Time", f"{stats['latest_run_time_ms']}ms")
    table.add_row("First Run API Calls", str(stats["first_run_api_calls"]))
    table.add_row("Latest Run API Calls", str(stats["latest_run_api_calls"]))
    console.print(table)

    caps = report["capabilities"]
    console.print(f"\n[bold]Capabilities:[/bold] {caps['total']} total, {caps['synthesized_at_runtime']} synthesized at runtime")

    if report["improvement_signals"]:
        console.print("\n[bold green]Improvement Signals:[/bold green]")
        for signal in report["improvement_signals"]:
            console.print(f"  ✓ {signal}")
    else:
        console.print("\n[yellow]No improvement signals yet (need more runs).[/yellow]")


@app.command()
def capabilities():
    """List all registered capabilities."""
    from src.agent.core import AgentCore

    agent = AgentCore()
    state = agent.get_memory_state()

    table = Table(title="Registered Capabilities")
    table.add_column("Name", style="cyan")
    table.add_column("Method", style="yellow")
    table.add_column("Endpoint", style="white")
    table.add_column("Success Rate", style="green")
    table.add_column("Synthesized", style="magenta")

    for cap in state["capabilities"]:
        table.add_row(
            cap["name"],
            cap["http_method"],
            cap["endpoint_template"],
            f"{cap['success_rate']:.0%}",
            "Yes" if cap["synthesized"] else "No",
        )

    console.print(table)


@app.command()
def seed():
    """Seed the initial base capabilities into memory."""
    from src.capabilities.seed import seed_base_capabilities

    count = seed_base_capabilities()
    console.print(f"[green]Seeded {count} base capabilities.[/green]")


def _display_report(report):
    status_color = {"success": "green", "partial_success": "yellow", "failed": "red"}.get(report.status, "white")

    console.print(f"\n[bold {status_color}]Status: {report.status.upper()}[/bold {status_color}]")
    console.print(f"Steps: {report.steps_succeeded}/{report.steps_total} succeeded")
    console.print(f"Time: {report.execution_time_ms}ms | API Calls: {report.api_calls}")

    if report.synthesized_capabilities:
        console.print(f"[magenta]Synthesized: {', '.join(report.synthesized_capabilities)}[/magenta]")

    if report.optimization_applied:
        console.print("[cyan]Optimization from prior runs applied.[/cyan]")

    if report.error_summary:
        console.print(f"[red]Errors: {report.error_summary}[/red]")

    console.print("\n[bold]Step Details:[/bold]")
    for i, sr in enumerate(report.step_results, 1):
        step = sr["step"]
        result = sr["result"]
        icon = {"success": "[green]✓[/green]", "failed": "[red]✗[/red]", "skipped": "[dim]○[/dim]"}.get(result["status"], "?")
        console.print(f"  {icon} Step {i}: {step['description']} [{result['status']}]")
        if result.get("error"):
            console.print(f"    [red]→ {result['error'][:120]}[/red]")
        if result.get("data"):
            _display_data(result["data"])


def _display_data(data):
    """Display API response data in a readable format."""
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        data = data["items"]
    if isinstance(data, list):
        if not data:
            console.print("\n  [yellow]No results found.[/yellow]")
            return
        console.print(f"\n  [bold]Results ({len(data)} items):[/bold]")
        for item in data[:20]:
            if isinstance(item, dict):
                if "title" in item and "number" in item:
                    state = item.get("state", "")
                    labels = ", ".join(l["name"] for l in item.get("labels", []) if isinstance(l, dict))
                    label_str = f" [dim]\\[{labels}][/dim]" if labels else ""
                    console.print(f"    #{item['number']} {item['title']} [dim]({state}){label_str}[/dim]")
                elif "name" in item and "full_name" in item:
                    console.print(f"    {item['full_name']} [dim]({item.get('visibility', '')})[/dim]")
                elif "name" in item:
                    console.print(f"    {item['name']}")
                else:
                    console.print(f"    {json.dumps(item, indent=2)[:200]}")
            else:
                console.print(f"    {item}")
    elif isinstance(data, dict):
        if "title" in data and "number" in data:
            console.print(f"\n  #{data['number']} {data['title']}")
            if data.get("body"):
                console.print(f"  [dim]{data['body'][:200]}[/dim]")
        else:
            console.print(Syntax(json.dumps(data, indent=2)[:1000], "json", theme="monokai"))


if __name__ == "__main__":
    app()
