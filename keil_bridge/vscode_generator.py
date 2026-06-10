import os
import json
from typing import Dict, Any
from rich.console import Console

from keil_bridge.parser import KeilProject, KeilTarget

class VSCodeGenerator:
    """Generates VS Code launch.json and tasks.json for debugging Keil projects with Cortex-Debug."""

    def __init__(self, project: KeilProject, console: Console):
        self.project = project
        self.console = console
        self.vscode_dir = os.path.join(self.project.project_dir, ".vscode")

    def generate(self, target_name: str = None, debugger: str = "stlink") -> None:
        target = self.project.get_target(target_name)
        
        # Ensure .vscode directory exists
        os.makedirs(self.vscode_dir, exist_ok=True)

        self._generate_tasks_json(target)
        self._generate_launch_json(target, debugger)

    def _get_executable_path(self, target: KeilTarget) -> str:
        """Determines the relative path to the compiled .axf or .elf file."""
        output_name = target.output_name or "image"
        # Most Keil projects output .axf
        filename = f"{output_name}.axf"
        
        if target.output_dir:
            return os.path.join(target.output_dir, filename).replace("\\", "/")
        return filename

    def _generate_tasks_json(self, target: KeilTarget):
        tasks_path = os.path.join(self.vscode_dir, "tasks.json")
        
        # Load existing if it exists to avoid overwriting user tasks
        tasks_data = {"version": "2.0.0", "tasks": []}
        if os.path.exists(tasks_path):
            try:
                with open(tasks_path, "r") as f:
                    tasks_data = json.load(f)
            except Exception:
                pass

        build_task = {
            "label": "Build Keil Target",
            "type": "shell",
            "command": "uvision-bridge",
            "args": [
                "build",
                "-p", os.path.basename(self.project.project_path),
                "-t", target.name
            ],
            "group": {
                "kind": "build",
                "isDefault": True
            },
            "problemMatcher": "$gcc" # uvision-bridge translates errors to look like GCC
        }

        # Replace existing build task if found
        for i, t in enumerate(tasks_data.get("tasks", [])):
            if t.get("label") == "Build Keil Target":
                tasks_data["tasks"][i] = build_task
                break
        else:
            tasks_data["tasks"].append(build_task)

        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f, indent=4)
        
        self.console.print(f"[bold green]✓[/bold green] Created [cyan]{tasks_path}[/cyan]")

    def _generate_launch_json(self, target: KeilTarget, debugger: str):
        launch_path = os.path.join(self.vscode_dir, "launch.json")

        launch_data = {"version": "0.2.0", "configurations": []}
        if os.path.exists(launch_path):
            try:
                with open(launch_path, "r") as f:
                    launch_data = json.load(f)
            except Exception:
                pass

        config_name = f"Debug {target.name} ({debugger})"
        executable = self._get_executable_path(target)
        
        # Parse device to give cortex-debug a hint
        device_hint = target.device
        if "STM32F" in device_hint:
            device_hint = device_hint.split("x")[0] + "xx" # E.g. STM32F103C8 -> STM32F103xx

        config = {
            "name": config_name,
            "cwd": "${workspaceFolder}",
            "executable": executable,
            "request": "launch",
            "type": "cortex-debug",
            "servertype": debugger,
            "device": device_hint,
            "runToEntryPoint": "main",
            "showDevDebugOutput": "none",
            "preLaunchTask": "Build Keil Target",
        }

        # Replace existing config with same name if found
        for i, c in enumerate(launch_data.get("configurations", [])):
            if c.get("name") == config_name:
                launch_data["configurations"][i] = config
                break
        else:
            launch_data["configurations"].append(config)

        with open(launch_path, "w", encoding="utf-8") as f:
            json.dump(launch_data, f, indent=4)

        self.console.print(f"[bold green]✓[/bold green] Created [cyan]{launch_path}[/cyan]")
        self.console.print("[dim]Note: Requires the 'marus25.cortex-debug' extension in VS Code.[/dim]")
