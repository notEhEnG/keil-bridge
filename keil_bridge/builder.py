import os
import re
import sys
import time
import subprocess
from typing import Optional, Tuple
from rich.console import Console

from keil_bridge.parser import KeilProject


class KeilBuilder:
    """Executes the Keil uVision compilation tool (UV4.exe) and colorizes output."""

    def __init__(self, project: KeilProject, wine_path: Optional[str] = None, console: Optional[Console] = None):
        self.project = project
        self.is_windows = sys.platform.startswith("win")
        self.wine_path = wine_path or self._find_compiler()
        self.console = console or Console()

    def _find_compiler(self) -> str:
        """Finds the Keil UV4.exe compiler in standard locations."""
        if self.is_windows:
            # Check common Windows directories
            common_paths = [
                r"C:\Keil_v5\UV4\UV4.exe",
                r"C:\Keil\UV4\UV4.exe",
                r"D:\Keil_v5\UV4\UV4.exe",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
            return "UV4.exe"  # Fallback to system path
        else:
            # Check common Wine installation directories
            home = os.path.expanduser("~")
            common_paths = [
                os.path.join(home, ".wine/drive_c/Keil_v5/UV4/UV4.exe"),
                os.path.join(home, ".wine/drive_c/Keil/UV4/UV4.exe"),
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
            return "UV4.exe"  # Fallback to wine system path

    def _to_windows_path(self, path: str) -> str:
        """Converts a Unix path to a Wine/Windows path."""
        abs_p = os.path.abspath(path)
        if self.is_windows:
            return abs_p
        # Standard Wine path translation (e.g. /home/user -> Z:\home\user)
        return "Z:" + abs_p.replace("/", "\\")

    def _translate_log_line(self, line: str) -> str:
        """Translates Windows/Wine paths in log output back to standard Unix paths."""
        if self.is_windows:
            return line

        # Replace absolute Wine drive paths (e.g., Z:\home\user\project -> /home/user/project)
        # Matches drive letters like Z: or C: followed by backslashes and directories
        def replace_drive_path(match):
            drive_path = match.group(0)
            # Remove the drive letter (e.g., "Z:")
            unix_style = drive_path[2:].replace("\\", "/")
            return unix_style

        # Regex for Z:\... or C:\...
        line = re.sub(r"(?i)[a-z]:\\[a-z0-9_.\-\\/]+", replace_drive_path, line)

        # Replace Windows-style relative paths (e.g. ..\Src\main.c -> ../Src/main.c)
        # We target backslashes in paths by matching alphanumeric parts separated by backslashes
        # but avoid touching windows line endings (\r\n)
        def replace_relative_backslashes(match):
            return match.group(0).replace("\\", "/")

        line = re.sub(r"(?:\.\.?\\[a-z0-9_.\-\\]+)+", replace_relative_backslashes, line, flags=re.IGNORECASE)

        return line

    def _print_colorized(self, line: str):
        """Prints a log line with appropriate syntax highlighting based on content."""
        clean_line = line.rstrip("\r\n")
        if not clean_line:
            return

        # Translate paths first
        translated = self._translate_log_line(clean_line)

        # Determine colors
        if "error:" in translated.lower() or "error -" in translated.lower() or "fatal error" in translated.lower():
            self.console.print(f"[bold red]{translated}[/bold red]")
        elif "warning:" in translated.lower() or "warning -" in translated.lower():
            self.console.print(f"[yellow]{translated}[/yellow]")
        elif translated.startswith("compiling") or translated.startswith("assembling"):
            self.console.print(f"[cyan]{translated}[/cyan]")
        elif "error(s)," in translated and "warning(s)" in translated:
            # Summary line (e.g. "Target 1" - 0 Error(s), 0 Warning(s).)
            if "0 Error(s)" in translated:
                self.console.print(f"[bold green]{translated}[/bold green]")
            else:
                self.console.print(f"[bold red]{translated}[/bold red]")
        else:
            self.console.print(translated)

    def build(self, target_name: Optional[str] = None, rebuild: bool = False) -> int:
        """Triggers the Keil compilation process and streams output."""
        target = self.project.get_target(target_name)
        self.console.print(f"[bold blue]Starting Keil Build for Target:[/bold blue] '{target.name}'")
        self.console.print(f"[blue]Device:[/blue] {target.device} | [blue]CPU:[/blue] {target.cpu}")
        self.console.print(f"[blue]Compiler Executable:[/blue] {self.wine_path}")
        if not self.is_windows:
            self.console.print("[blue]Execution Environment:[/blue] Linux/macOS (via Wine)")

        # Create temporary log file in the project directory
        log_file_name = f".uvision_build_{int(time.time())}.log"
        log_file_path = os.path.join(self.project.project_dir, log_file_name)
        
        # Format paths for Keil CLI
        proj_win_path = self._to_windows_path(self.project.project_path)
        log_win_path = self._to_windows_path(log_file_path)

        # Build command array
        build_flag = "-r" if rebuild else "-b"
        
        if self.is_windows:
            cmd = [
                self.wine_path,
                build_flag,
                proj_win_path,
                "-t",
                target.name,
                "-j0",
                "-o",
                log_win_path
            ]
        else:
            cmd = [
                "wine",
                self.wine_path,
                build_flag,
                proj_win_path,
                "-t",
                target.name,
                "-j0",
                "-o",
                log_win_path
            ]

        # Clean old log file if it exists
        if os.path.exists(log_file_path):
            os.remove(log_file_path)

        try:
            # Launch compilation
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                universal_newlines=True
            )
        except FileNotFoundError:
            self.console.print(
                f"[bold red]Error:[/bold red] Could not launch build process. "
                f"Make sure compiler executable or 'wine' is installed and in PATH."
            )
            return -1

        # Stream the log file in real-time as Keil writes to it
        log_opened = False
        log_file_handle = None
        last_position = 0

        # Wait for the log file to be created by Keil
        timeout = 10.0
        start_time = time.time()

        try:
            while process.poll() is None:
                if not log_opened:
                    if os.path.exists(log_file_path):
                        try:
                            log_file_handle = open(log_file_path, "r", encoding="utf-8", errors="replace")
                            log_opened = True
                        except IOError:
                            pass
                    else:
                        if time.time() - start_time > timeout:
                            self.console.print("[yellow]Warning: Keil log file creation timed out. Waiting for build to finish...[/yellow]")
                            break
                        time.sleep(0.2)
                        continue

                # Stream new lines
                if log_file_handle:
                    log_file_handle.seek(last_position)
                    lines = log_file_handle.readlines()
                    if lines:
                        for line in lines:
                            self._print_colorized(line)
                        last_position = log_file_handle.tell()
                time.sleep(0.1)

            # Wait for process to fully exit and read any remaining lines
            process.wait()

            # Read final lines
            if os.path.exists(log_file_path):
                if not log_file_handle:
                    try:
                        log_file_handle = open(log_file_path, "r", encoding="utf-8", errors="replace")
                    except IOError:
                        pass

                if log_file_handle:
                    log_file_handle.seek(last_position)
                    lines = log_file_handle.readlines()
                    for line in lines:
                        self._print_colorized(line)
        finally:
            if log_file_handle:
                log_file_handle.close()

            # Clean up log file
            try:
                os.remove(log_file_path)
            except OSError:
                pass

        exit_code = process.returncode
        
        # Map uVision CLI exit codes
        # 0: Success
        # 1: Warnings
        # 2: Errors
        # 3: Fatal Errors
        if exit_code == 0:
            self.console.print("\n[bold green]✓ Build Succeeded![/bold green]")
        elif exit_code == 1:
            self.console.print("\n[bold yellow]⚠ Build Finished with Warnings.[/bold yellow]")
        elif exit_code == 2:
            self.console.print("\n[bold red]✗ Build Failed with Errors.[/bold red]")
        elif exit_code == 3:
            self.console.print("\n[bold red]✗ Build Failed with Fatal Errors.[/bold red]")
        else:
            self.console.print(f"\n[bold red]✗ Build finished with exit code {exit_code}[/bold red]")

        return exit_code
