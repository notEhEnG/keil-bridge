import argparse
import os
import sys
from collections import Counter
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from keil_bridge.parser import KeilProject
from keil_bridge.builder import KeilBuilder
from keil_bridge.lsp_generator import LspGenerator
from keil_bridge.cmake_exporter import CMakeExporter
from keil_bridge.flash_uploader import FlashUploader
from keil_bridge.watcher import FileWatcher
from keil_bridge.target_diff import TargetDiff
from keil_bridge.map_analyzer import MapAnalyzer
from keil_bridge.vscode_generator import VSCodeGenerator
from keil_bridge.linter import Linter
from keil_bridge.ci_generator import CIGenerator
from keil_bridge.cleaner import ProjectCleaner

console = Console()


def find_uvprojx_files() -> List[str]:
    """Finds all .uvprojx files in the current directory."""
    files = []
    for f in os.listdir("."):
        if f.endswith(".uvprojx"):
            files.append(f)
    return files


def interactive_menu(project_path: str, initial_target: Optional[str] = None):
    """Presents a number-based interactive menu for the project."""
    try:
        project = KeilProject(project_path)
    except Exception as e:
        console.print(Panel(f"[bold red]Error parsing project file:[/bold red]\n{e}", title="Parser Error"))
        return

    console.print(Panel(
        f"[bold blue]Project Directory:[/bold blue] {project.project_dir}\n"
        f"[bold blue]Available Targets:[/bold blue] {', '.join(project.targets.keys())}",
        title="uvision-bridge Interactive Mode",
        border_style="blue"
    ))

    # Target selection if multiple targets exist
    targets = list(project.targets.keys())
    selected_target = targets[0]

    if initial_target and initial_target in project.targets:
        selected_target = initial_target
    elif len(targets) > 1:
        console.print("\n[bold]Select Target:[/bold]")
        for idx, t in enumerate(targets):
            console.print(f"  [cyan]{idx + 1}[/cyan]) {t}")
        try:
            choice = input("\nEnter number (default 1): ").strip()
            if choice:
                val = int(choice) - 1
                if 0 <= val < len(targets):
                    selected_target = targets[val]
        except (ValueError, KeyboardInterrupt):
            console.print("[yellow]Invalid input. Using default target.[/yellow]")

    while True:
        console.print(f"\n[bold]Selected Target:[/bold] [green]{selected_target}[/green]\n")
        console.print("[bold]Select Action:[/bold]")
        console.print("  [cyan]1[/cyan])  Change Target")
        console.print("  [cyan]2[/cyan])  View Project Target Info")
        console.print("  [cyan]3[/cyan])  Build Target")
        console.print("  [cyan]4[/cyan])  Clean & Rebuild Target")
        console.print("  [cyan]5[/cyan])  Generate compile_commands.json (LSP)")
        console.print("  [cyan]6[/cyan])  Export to CMakeLists.txt")
        console.print("  [cyan]7[/cyan])  Flash Firmware to MCU")
        console.print("  [cyan]8[/cyan])  Watch & Auto-Build")
        console.print("  [cyan]9[/cyan])  Compare Two Targets")
        console.print("  [cyan]10[/cyan]) Memory Usage Analysis (.map)")
        console.print("  [cyan]11[/cyan]) Generate VS Code debug config")
        console.print("  [cyan]12[/cyan]) Run Static Analysis (lint)")
        console.print("  [cyan]13[/cyan]) Generate CI Workflow")
        console.print("  [cyan]14[/cyan]) Smart Clean")
        console.print("  [cyan]15[/cyan]) Exit")

        try:
            action = input("\nEnter action number: ").strip()
            if not action:
                continue

            if action == "1":
                if len(targets) == 1:
                    console.print("[yellow]Only one target is available.[/yellow]")
                    continue

                console.print("\n[bold]Select Target:[/bold]")
                for idx, t in enumerate(targets):
                    console.print(f"  [cyan]{idx + 1}[/cyan]) {t}")
                choice = input("\nEnter number (default 1): ").strip()
                if not choice:
                    continue

                try:
                    val = int(choice) - 1
                except ValueError:
                    console.print("[red]Invalid target selection.[/red]")
                    continue

                if 0 <= val < len(targets):
                    selected_target = targets[val]
                else:
                    console.print("[red]Invalid target selection.[/red]")
            elif action == "2":
                show_info(project, selected_target)
            elif action == "3":
                builder = KeilBuilder(project, console=console)
                builder.build(selected_target, rebuild=False)
            elif action == "4":
                builder = KeilBuilder(project, console=console)
                builder.build(selected_target, rebuild=True)
            elif action == "5":
                generator = LspGenerator(project)
                out_file = generator.write_to_file(target_name=selected_target)
                console.print(f"[bold green]✓[/bold green] Generated compilation database at: [cyan]{out_file}[/cyan]")
            elif action == "6":
                exporter = CMakeExporter(project)
                out_file = exporter.export(target_name=selected_target)
                console.print(f"[bold green]✓[/bold green] Exported CMakeLists.txt at: [cyan]{out_file}[/cyan]")
            elif action == "7":
                uploader = FlashUploader(project, console=console)
                uploader.flash(target_name=selected_target)
            elif action == "8":
                watcher = FileWatcher(project, console=console)
                watcher.watch(target_name=selected_target)
            elif action == "9":
                if len(targets) < 2:
                    console.print("[yellow]Need at least 2 targets to compare.[/yellow]")
                    continue
                console.print("\n[bold]Select Target A:[/bold]")
                for idx, t in enumerate(targets):
                    console.print(f"  [cyan]{idx + 1}[/cyan]) {t}")
                try:
                    choice_a = int(input("Enter number for Target A: ").strip()) - 1
                    choice_b = int(input("Enter number for Target B: ").strip()) - 1
                    if 0 <= choice_a < len(targets) and 0 <= choice_b < len(targets):
                        differ = TargetDiff(project, console=console)
                        differ.diff(targets[choice_a], targets[choice_b])
                    else:
                        console.print("[red]Invalid target selection.[/red]")
                except (ValueError, KeyboardInterrupt):
                    console.print("[red]Invalid input.[/red]")
            elif action == "10":
                analyzer = MapAnalyzer(project, console)
                analyzer.parse_and_show(selected_target)
            elif action == "11":
                generator = VSCodeGenerator(project, console)
                generator.generate(selected_target, "stlink")
            elif action == "12":
                linter = Linter(project, console)
                linter.lint(selected_target)
            elif action == "13":
                generator = CIGenerator(project, console)
                generator.generate("github")
            elif action == "14":
                cleaner = ProjectCleaner(project, console)
                cleaner.clean(selected_target)
            elif action == "15":
                console.print("[blue]Exiting.[/blue]")
                return
            else:
                console.print("[red]Invalid action selection.[/red]")
        except KeyboardInterrupt:
            console.print("\n[blue]Cancelled.[/blue]")
            return


def show_info(project: KeilProject, target_name: Optional[str] = None):
    """Prints target settings, source files, and file count summary."""
    target = project.get_target(target_name)

    # Print general target settings
    info_table = Table(title=f"Keil Target Profile: {target.name}", show_header=False, box=None)
    info_table.add_row("[bold cyan]Device (MCU):[/bold cyan]", target.device)
    info_table.add_row("[bold cyan]CPU Architecture:[/bold cyan]", target.cpu)
    info_table.add_row("[bold cyan]Define flags:[/bold cyan]", " ".join(target.defines) if target.defines else "None")
    info_table.add_row("[bold cyan]Optimization:[/bold cyan]", target.optimization or "Default")
    info_table.add_row("[bold cyan]Output Name:[/bold cyan]", target.output_name or "N/A")
    info_table.add_row("[bold cyan]Output Directory:[/bold cyan]", target.output_dir or "N/A")
    info_table.add_row("[bold cyan]Linker Script:[/bold cyan]", target.linker_script or "N/A")
    console.print(info_table)

    # Print include paths
    if target.include_paths:
        console.print("\n[bold cyan]Include Paths:[/bold cyan]")
        for path in target.include_paths:
            console.print(f"  • {path}")

    # Print file groups
    console.print("\n[bold cyan]Source Groups and Files:[/bold cyan]")
    file_type_counter: Counter = Counter()
    total_files = 0

    for group in target.groups:
        if not group.files:
            continue
        console.print(f"  📂 [bold yellow]{group.name}[/bold yellow]")
        for file in group.files:
            console.print(f"    📄 {file.name} [dim]({file.type_name})[/dim]")
            file_type_counter[file.type_name] += 1
            total_files += 1

    # File count summary table
    if total_files > 0:
        summary_table = Table(title="\nFile Summary", show_header=True, header_style="bold cyan")
        summary_table.add_column("Type", style="bold")
        summary_table.add_column("Count", justify="center")

        for file_type, count in file_type_counter.most_common():
            summary_table.add_row(file_type, str(count))
        summary_table.add_row("[bold]Total[/bold]", f"[bold]{total_files}[/bold]")

        console.print(summary_table)


def main():
    parser = argparse.ArgumentParser(
        description="A modern cross-platform CLI tool for compiling, configuring LSP, and exporting Keil uVision projects."
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "-t",
        "--target",
        dest="default_target",
        help="Default target name to use when starting interactive mode or when a subcommand does not specify one.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Command: info
    p_info = subparsers.add_parser("info", help="Show project configuration information")
    p_info.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_info.add_argument("-t", "--target", help="Name of target (defaults to first/active)")

    # Command: build
    p_build = subparsers.add_parser("build", help="Compile target using Keil uVision compiler")
    p_build.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_build.add_argument("-t", "--target", help="Name of target to compile")
    p_build.add_argument("-r", "--rebuild", action="store_true", help="Rebuild all files")
    p_build.add_argument("-w", "--wine-path", help="Custom path to Keil compiler UV4.exe executable")

    # Command: lsp
    p_lsp = subparsers.add_parser("lsp", help="Generate compile_commands.json for LSP support")
    p_lsp.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_lsp.add_argument("-o", "--output", help="Custom output path (defaults to compile_commands.json)")
    p_lsp.add_argument("-t", "--target", help="Name of target to generate for")
    p_lsp.add_argument("-c", "--compiler", default="arm-none-eabi-gcc", help="Compiler name for LSP (default: arm-none-eabi-gcc)")

    # Command: cmake
    p_cmake = subparsers.add_parser("cmake", help="Export project configuration to CMakeLists.txt")
    p_cmake.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_cmake.add_argument("-o", "--output", help="Custom output path (defaults to CMakeLists.txt)")
    p_cmake.add_argument("-t", "--target", help="Name of target to export")

    # Command: flash
    p_flash = subparsers.add_parser("flash", help="Upload compiled firmware to MCU")
    p_flash.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_flash.add_argument("-t", "--target", help="Name of target to flash")
    p_flash.add_argument("--tool", default="auto", choices=["auto", "stlink", "openocd", "jlink"],
                         help="Flash tool to use (default: auto-detect)")
    p_flash.add_argument("--address", default="0x08000000", help="Flash base address (default: 0x08000000)")

    # Command: watch
    p_watch = subparsers.add_parser("watch", help="Watch source files and auto-rebuild on change")
    p_watch.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_watch.add_argument("-t", "--target", help="Name of target to build")
    p_watch.add_argument("-r", "--rebuild", action="store_true", help="Full rebuild on change (default: incremental)")
    p_watch.add_argument("-w", "--wine-path", help="Custom path to Keil compiler UV4.exe executable")

    # Command: diff
    p_diff = subparsers.add_parser("diff", help="Compare two build targets side-by-side")
    p_diff.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_diff.add_argument("--target-a", required=True, help="First target name")
    p_diff.add_argument("--target-b", required=True, help="Second target name")

    # Command: size
    p_size = subparsers.add_parser("size", help="Analyze Memory Usage from .map file")
    p_size.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_size.add_argument("-t", "--target", help="Name of target to analyze")

    # Command: vscode
    p_vscode = subparsers.add_parser("vscode", help="Generate VS Code launch.json and tasks.json")
    p_vscode.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_vscode.add_argument("-t", "--target", help="Name of target")
    p_vscode.add_argument("--debugger", default="stlink", choices=["stlink", "openocd", "jlink"], help="Debugger to use in launch.json (default: stlink)")

    # Command: lint
    p_lint = subparsers.add_parser("lint", help="Run clang-tidy static analysis on project files")
    p_lint.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_lint.add_argument("-t", "--target", help="Name of target to analyze")

    # Command: ci
    p_ci = subparsers.add_parser("ci", help="Generate CI workflow templates")
    p_ci.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_ci.add_argument("--provider", default="github", choices=["github"], help="CI Provider to target")

    # Command: clean
    p_clean = subparsers.add_parser("clean", help="Smart clean compilation artifacts")
    p_clean.add_argument("-p", "--project", help="Path to .uvprojx project file")
    p_clean.add_argument("-t", "--target", help="Name of target to clean")
    p_clean.add_argument("-a", "--all", action="store_true", help="Clean all targets")

    args = parser.parse_args()

    # Auto-detection of project file if not specified
    project_path = getattr(args, "project", None)
    if not project_path:
        uvprojx_files = find_uvprojx_files()
        if len(uvprojx_files) == 1:
            project_path = uvprojx_files[0]
            console.print(f"[dim]Auto-detected project file: {project_path}[/dim]")
        elif len(uvprojx_files) > 1 and not args.command:
            console.print("[bold yellow]Multiple .uvprojx files found in current directory:[/bold yellow]")
            for idx, f in enumerate(uvprojx_files):
                console.print(f"  [cyan]{idx + 1}[/cyan]) {f}")
            try:
                choice = input("\nEnter number to select project: ").strip()
                if choice:
                    val = int(choice) - 1
                    if 0 <= val < len(uvprojx_files):
                        project_path = uvprojx_files[val]
            except (ValueError, KeyboardInterrupt):
                pass

    # No command & no project file -> interactive mode scan or show help
    if not args.command:
        if not project_path:
            console.print("[yellow]No project file specified and none auto-detected. Use -h for help.[/yellow]")
            try:
                project_path = input("Enter path to .uvprojx file: ").strip()
            except KeyboardInterrupt:
                return
            if not project_path or not os.path.exists(project_path):
                console.print("[red]Project file not found.[/red]")
                sys.exit(1)
        
        interactive_menu(project_path, initial_target=args.default_target)
        return

    # Process subcommands
    if not project_path:
        console.print("[red]Error: Project file (-p/--project) is required.[/red]")
        sys.exit(1)

    try:
        project = KeilProject(project_path)
    except Exception as e:
        console.print(Panel(f"[bold red]Failed to load project file:[/bold red]\n{e}", title="Error"))
        sys.exit(1)

    try:
        if args.command == "info":
            show_info(project, args.target or args.default_target)

        elif args.command == "build":
            builder = KeilBuilder(project, wine_path=args.wine_path, console=console)
            exit_code = builder.build(args.target or args.default_target, rebuild=args.rebuild)
            sys.exit(exit_code)

        elif args.command == "lsp":
            generator = LspGenerator(project)
            try:
                out_file = generator.write_to_file(args.output, args.target or args.default_target, args.compiler)
                console.print(f"[bold green]✓[/bold green] Generated compilation database at: [cyan]{out_file}[/cyan]")
            except Exception as e:
                console.print(f"[bold red]Failed to generate compilation database:[/bold red] {e}")
                sys.exit(1)

        elif args.command == "cmake":
            exporter = CMakeExporter(project)
            try:
                out_file = exporter.export(args.output, args.target or args.default_target)
                console.print(f"[bold green]✓[/bold green] Exported CMakeLists.txt at: [cyan]{out_file}[/cyan]")
            except Exception as e:
                console.print(f"[bold red]Failed to export to CMakeLists.txt:[/bold red] {e}")
                sys.exit(1)

        elif args.command == "flash":
            uploader = FlashUploader(project, console=console)
            exit_code = uploader.flash(
                target_name=args.target or args.default_target,
                tool=args.tool,
                address=args.address,
            )
            sys.exit(exit_code)

        elif args.command == "watch":
            watcher = FileWatcher(project, wine_path=getattr(args, "wine_path", None), console=console)
            watcher.watch(
                target_name=args.target or args.default_target,
                rebuild=args.rebuild,
            )

        elif args.command == "diff":
            differ = TargetDiff(project, console=console)
            differ.diff(args.target_a, args.target_b)

        elif args.command == "size":
            analyzer = MapAnalyzer(project, console)
            analyzer.parse_and_show(args.target or args.default_target)

        elif args.command == "vscode":
            generator = VSCodeGenerator(project, console)
            generator.generate(args.target or args.default_target, args.debugger)

        elif args.command == "lint":
            linter = Linter(project, console)
            linter.lint(args.target or args.default_target)

        elif args.command == "ci":
            generator = CIGenerator(project, console)
            generator.generate(args.provider)

        elif args.command == "clean":
            cleaner = ProjectCleaner(project, console)
            cleaner.clean(args.target or args.default_target, all_targets=args.all)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
