from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def print_report(report: str, raw_data: list = None, show_raw: bool = False, collection: str = None):
    """Print the interpreted report and optionally the raw data table."""
    count = len(raw_data) if raw_data else 0
    subtitle = f"Collection: {collection} | Results: {count}" if collection else f"Results: {count}"
    panel = Panel(report, title="Report", subtitle=subtitle, border_style="green")
    console.print(panel)

    if show_raw and raw_data:
        if raw_data:
            table = Table(title="Raw Data")
            keys = list(raw_data[0].keys()) if raw_data else []
            for key in keys:
                table.add_column(str(key), style="cyan")
            for row in raw_data:
                table.add_row(*[str(row.get(k, "")) for k in keys])
            console.print(table)
        else:
            console.print("[yellow]No raw data to display.[/yellow]")

def print_error(message: str):
    """Print an error message in red."""
    console.print(f"[red]Error:[/red] {message}")

def print_info(message: str):
    """Print an info message in blue."""
    console.print(f"[blue]{message}[/blue]")
