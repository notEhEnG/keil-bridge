import os
import re
import subprocess
import sys
from typing import Optional
from rich.console import Console

from keil_bridge.parser import KeilProject, KeilTarget

class Linter:
    """Runs clang-tidy on the Keil project C/C++ files."""

    def __init__(self, project: KeilProject, console: Console):
        self.project = project
        self.console = console

    def lint(self, target_name: Optional[str] = None):
        target = self.project.get_target(target_name)
        
        # Gather all C/C++ files
        source_files = []
        for group in target.groups:
            for f in group.files:
                if f.type_name in ["C", "C++"]:
                    source_files.append(f.absolute_path)
        
        if not source_files:
            self.console.print(f"[yellow]No C or C++ source files found in target '{target.name}'.[/yellow]")
            return

        # Construct compiler flags for clang-tidy
        compiler_args = []
        for define in target.defines:
            compiler_args.append(f"-D{define}")
        for inc in target.include_paths:
            # Resolve include path relative to project dir
            abs_inc = os.path.normpath(os.path.join(self.project.project_dir, inc))
            compiler_args.append(f"-I{abs_inc}")

        # Derive CPU flag from target CPU string
        cpu_match = re.search(r'Cortex-M\d+?', target.cpu, re.IGNORECASE)
        mcpu = cpu_match.group(0).lower() if cpu_match else "cortex-m3"

        compiler_args.extend([
            f"-mcpu={mcpu}",
            "-mthumb",
            "-ffreestanding"
        ])

        # Clang-tidy command
        cmd = ["clang-tidy"]
        # Add source files
        cmd.extend(source_files)
        # Add compiler arguments after --
        cmd.append("--")
        cmd.extend(compiler_args)

        self.console.print(f"[bold cyan]Running clang-tidy on {len(source_files)} files...[/bold cyan]")
        try:
            # We use subprocess.Popen to stream the output directly to the console
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project.project_dir
            )

            for line in process.stdout:
                if "error:" in line:
                    self.console.print(f"[red]{line.strip()}[/red]")
                elif "warning:" in line:
                    self.console.print(f"[yellow]{line.strip()}[/yellow]")
                elif "note:" in line:
                    self.console.print(f"[blue]{line.strip()}[/blue]")
                else:
                    self.console.print(line.strip())

            process.wait()
            if process.returncode == 0:
                self.console.print("[bold green]✓ Linting passed![/bold green]")
            else:
                self.console.print(f"[bold red]✗ Linting failed with exit code {process.returncode}[/bold red]")
                sys.exit(process.returncode)

        except FileNotFoundError:
            self.console.print("[bold red]Error:[/bold red] 'clang-tidy' is not installed or not in PATH.")
            self.console.print("Please install clang-tidy (e.g. `sudo apt install clang-tidy` or via LLVM on Windows).")
            sys.exit(1)
