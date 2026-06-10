import os
from rich.console import Console

from keil_bridge.parser import KeilProject

class CIGenerator:
    """Generates CI workflow files (GitHub Actions) for headless Keil compilation via Wine."""

    def __init__(self, project: KeilProject, console: Console):
        self.project = project
        self.console = console

    def generate(self, provider: str = "github"):
        if provider == "github":
            self._generate_github_actions()
        else:
            self.console.print(f"[bold red]Error:[/bold red] Unknown CI provider '{provider}'.")

    def _generate_github_actions(self):
        github_dir = os.path.join(self.project.project_dir, ".github", "workflows")
        os.makedirs(github_dir, exist_ok=True)
        
        workflow_path = os.path.join(github_dir, "keil-build.yml")
        
        # Determine a target to build in CI
        target_name = self.project.active_target_name or list(self.project.targets.keys())[0]
        project_filename = os.path.basename(self.project.project_path)

        workflow_content = f"""name: Keil uVision Build

on:
  push:
    branches: [ "main", "master" ]
  pull_request:
    branches: [ "main", "master" ]

jobs:
  build:
    runs-on: ubuntu-latest
    
    # We use a community docker image that comes pre-installed with Wine and Keil v5
    # For a real pipeline, you would use a private image with your valid Keil license
    container:
      image: navia/keil-wine:v5
      
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Install uvision-bridge
        run: |
          pip install uvision-bridge

      - name: Build Firmware
        run: |
          uvision-bridge build -p {project_filename} -t "{target_name}"

      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: Firmware
          path: |
            **/*.axf
            **/*.hex
            **/*.bin
"""
        with open(workflow_path, "w", encoding="utf-8") as f:
            f.write(workflow_content)
        
        self.console.print(f"[bold green]✓[/bold green] Generated GitHub Actions workflow at: [cyan]{workflow_path}[/cyan]")
        self.console.print("[dim]Note: You may need to replace the docker image with your own licensed Keil container.[/dim]")
