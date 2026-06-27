import os
import glob
import shutil
from typing import Optional
from rich.console import Console

from keil_bridge.parser import KeilProject

class ProjectCleaner:
    """Smart project cleaner that removes compilation artifacts natively without invoking Keil/Wine."""

    def __init__(self, project: KeilProject, console: Console):
        self.project = project
        self.console = console

        self.EXTENSIONS_TO_CLEAN = [
            "*.o", "*.d", "*.crf", "*.map", "*.htm", "*.lnp", 
            "*.axf", "*.hex", "*.bin", "*.sct", "*.dep", "*.build_log.htm"
        ]

    def clean(self, target_name: Optional[str] = None, all_targets: bool = False):
        if all_targets:
            targets_to_clean = list(self.project.targets.values())
        else:
            targets_to_clean = [self.project.get_target(target_name)]

        cleaned_files = 0
        cleaned_dirs = 0

        for target in targets_to_clean:
            dirs_to_clean = set()
            if target.output_dir:
                dirs_to_clean.add(os.path.normpath(os.path.join(self.project.project_dir, target.output_dir)))
            if target.listing_dir:
                dirs_to_clean.add(os.path.normpath(os.path.join(self.project.project_dir, target.listing_dir)))

            for d in dirs_to_clean:
                if not os.path.exists(d):
                    continue

                # Remove specific artifact extensions
                for ext in self.EXTENSIONS_TO_CLEAN:
                    pattern = os.path.join(d, ext)
                    for filepath in glob.glob(pattern):
                        try:
                            os.remove(filepath)
                            cleaned_files += 1
                        except OSError as e:
                            self.console.print(f"[yellow]Warning: Could not delete {filepath} - {e}[/yellow]")
                
                # Check if directory is empty after cleaning, if so delete it
                if not os.listdir(d):
                    try:
                        os.rmdir(d)
                        cleaned_dirs += 1
                    except OSError:
                        pass

        if cleaned_files == 0:
            self.console.print("[green]Project is already clean.[/green]")
        else:
            self.console.print(f"[bold green]✓ Clean complete![/bold green] Removed {cleaned_files} files and {cleaned_dirs} empty directories.")
