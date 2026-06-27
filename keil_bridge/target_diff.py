from typing import Optional, Set, Tuple
from rich.console import Console
from rich.table import Table

from keil_bridge.parser import KeilProject



class TargetDiff:
    """Compares two build targets within the same Keil project."""

    def __init__(self, project: KeilProject, console: Optional[Console] = None):
        self.project = project
        self.console = console or Console()

    def _get_file_set(self, target_name: str) -> Set[str]:
        """Returns a set of all source file paths in the target."""
        target = self.project.get_target(target_name)
        files = set()
        for group in target.groups:
            for file in group.files:
                files.add(f"{group.name}/{file.name} ({file.type_name})")
        return files

    def diff(self, target_a: str, target_b: str):
        """Prints a side-by-side comparison of two targets."""
        try:
            ta = self.project.get_target(target_a)
        except ValueError:
            self.console.print(f"[bold red]Error:[/bold red] Target '{target_a}' not found.")
            return
        try:
            tb = self.project.get_target(target_b)
        except ValueError:
            self.console.print(f"[bold red]Error:[/bold red] Target '{target_b}' not found.")
            return

        self.console.print(f"\n[bold]Comparing:[/bold] [cyan]{target_a}[/cyan] vs [cyan]{target_b}[/cyan]\n")

        # --- Device & CPU ---
        props_table = Table(title="Device & Build Configuration", show_header=True, header_style="bold cyan")
        props_table.add_column("Property", style="bold")
        props_table.add_column(target_a, justify="center")
        props_table.add_column(target_b, justify="center")

        def _diff_row(table: Table, label: str, val_a: str, val_b: str):
            if val_a == val_b:
                table.add_row(label, val_a, val_b)
            else:
                table.add_row(label, f"[red]{val_a}[/red]", f"[green]{val_b}[/green]")

        _diff_row(props_table, "Device", ta.device, tb.device)
        _diff_row(props_table, "CPU", ta.cpu, tb.cpu)
        _diff_row(props_table, "Output Name", ta.output_name or "N/A", tb.output_name or "N/A")
        _diff_row(props_table, "Output Dir", ta.output_dir or "N/A", tb.output_dir or "N/A")
        _diff_row(props_table, "Optimization", ta.optimization or "N/A", tb.optimization or "N/A")
        _diff_row(props_table, "Linker Script", ta.linker_script or "N/A", tb.linker_script or "N/A")

        self.console.print(props_table)

        # --- Preprocessor Defines ---
        defines_a = set(ta.defines)
        defines_b = set(tb.defines)
        shared_defines = defines_a & defines_b
        only_a_defines = defines_a - defines_b
        only_b_defines = defines_b - defines_a

        defines_table = Table(title="\nPreprocessor Defines", show_header=True, header_style="bold cyan")
        defines_table.add_column("Define", style="bold")
        defines_table.add_column("Status", justify="center")

        for d in sorted(shared_defines):
            defines_table.add_row(d, "[dim]shared[/dim]")
        for d in sorted(only_a_defines):
            defines_table.add_row(f"[red]{d}[/red]", f"[red]only in {target_a}[/red]")
        for d in sorted(only_b_defines):
            defines_table.add_row(f"[green]{d}[/green]", f"[green]only in {target_b}[/green]")

        self.console.print(defines_table)

        # --- Include Paths ---
        includes_a = set(ta.include_paths)
        includes_b = set(tb.include_paths)
        shared_includes = includes_a & includes_b
        only_a_includes = includes_a - includes_b
        only_b_includes = includes_b - includes_a

        includes_table = Table(title="\nInclude Paths", show_header=True, header_style="bold cyan")
        includes_table.add_column("Path", style="bold")
        includes_table.add_column("Status", justify="center")

        for p in sorted(shared_includes):
            includes_table.add_row(p, "[dim]shared[/dim]")
        for p in sorted(only_a_includes):
            includes_table.add_row(f"[red]{p}[/red]", f"[red]only in {target_a}[/red]")
        for p in sorted(only_b_includes):
            includes_table.add_row(f"[green]{p}[/green]", f"[green]only in {target_b}[/green]")

        self.console.print(includes_table)

        # --- Source Files ---
        files_a = self._get_file_set(target_a)
        files_b = self._get_file_set(target_b)
        shared_files = files_a & files_b
        only_a_files = files_a - files_b
        only_b_files = files_b - files_a

        files_table = Table(title="\nSource Files", show_header=True, header_style="bold cyan")
        files_table.add_column("File", style="bold")
        files_table.add_column("Status", justify="center")

        for f in sorted(shared_files):
            files_table.add_row(f, "[dim]shared[/dim]")
        for f in sorted(only_a_files):
            files_table.add_row(f"[red]{f}[/red]", f"[red]only in {target_a}[/red]")
        for f in sorted(only_b_files):
            files_table.add_row(f"[green]{f}[/green]", f"[green]only in {target_b}[/green]")

        self.console.print(files_table)

        # Summary
        total_diffs = (
            (0 if ta.device == tb.device else 1)
            + len(only_a_defines) + len(only_b_defines)
            + len(only_a_includes) + len(only_b_includes)
            + len(only_a_files) + len(only_b_files)
        )
        if total_diffs == 0:
            self.console.print("\n[bold green]✓ Targets are identical.[/bold green]")
        else:
            self.console.print(f"\n[bold yellow]⚠ {total_diffs} difference(s) found.[/bold yellow]")
