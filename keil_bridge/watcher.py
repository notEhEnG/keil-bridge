import os
import time
from typing import Dict, Optional
from rich.console import Console

from keil_bridge.parser import KeilProject
from keil_bridge.builder import KeilBuilder



class FileWatcher:
    """Watches project source files for changes and auto-triggers a rebuild."""

    def __init__(self, project: KeilProject, wine_path: Optional[str] = None, console: Optional[Console] = None):
        self.project = project
        self.wine_path = wine_path
        self.console = console or Console()
        self._debounce_window = 0.3  # seconds

    def _collect_source_paths(self, target_name: Optional[str] = None) -> Dict[str, float]:
        """Collects all source file absolute paths and their modification times."""
        target = self.project.get_target(target_name)
        file_mtimes: Dict[str, float] = {}

        for group in target.groups:
            for file in group.files:
                abs_path = file.absolute_path
                if os.path.exists(abs_path):
                    file_mtimes[abs_path] = os.path.getmtime(abs_path)

        return file_mtimes

    def watch(self, target_name: Optional[str] = None, rebuild: bool = False, poll_interval: float = 0.5):
        """
        Polls source files and triggers a build when a change is detected.
        
        Args:
            target_name: The build target to compile.
            rebuild: If True, does a full rebuild on change. Otherwise incremental.
            poll_interval: Seconds between each filesystem poll cycle.
        """
        target = self.project.get_target(target_name)
        self.console.print(f"[bold blue]Watching target:[/bold blue] '{target.name}'")
        self.console.print(f"[blue]Device:[/blue] {target.device}")
        self.console.print(f"[blue]Mode:[/blue] {'Full Rebuild' if rebuild else 'Incremental Build'}")

        # Initial scan
        file_mtimes = self._collect_source_paths(target_name)
        self.console.print(f"[blue]Tracking:[/blue] {len(file_mtimes)} source files")
        self.console.print("[dim]Press Ctrl+C to stop watching.[/dim]\n")

        try:
            while True:
                time.sleep(poll_interval)
                changed_files = []

                for path, old_mtime in file_mtimes.items():
                    if not os.path.exists(path):
                        continue
                    try:
                        current_mtime = os.path.getmtime(path)
                    except OSError:
                        continue

                    if current_mtime != old_mtime:
                        changed_files.append(path)
                        file_mtimes[path] = current_mtime

                # Also check for new files that may have been added
                new_mtimes = self._collect_source_paths(target_name)
                for path, mtime in new_mtimes.items():
                    if path not in file_mtimes:
                        changed_files.append(path)
                        file_mtimes[path] = mtime

                if changed_files:
                    # Debounce: wait briefly for rapid successive saves
                    time.sleep(self._debounce_window)

                    self.console.print(f"\n[bold yellow]⚡ Change detected in {len(changed_files)} file(s):[/bold yellow]")
                    for cf in changed_files:
                        basename = os.path.basename(cf)
                        self.console.print(f"  → [cyan]{basename}[/cyan]")

                    self.console.print("")
                    builder = KeilBuilder(self.project, wine_path=self.wine_path)
                    builder.build(target_name, rebuild=rebuild)
                    self.console.print("\n[dim]Watching for changes...[/dim]")

        except KeyboardInterrupt:
            self.console.print("\n[blue]Watcher stopped.[/blue]")
