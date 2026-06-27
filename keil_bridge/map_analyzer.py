import os
import re
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


from keil_bridge.parser import KeilProject, KeilTarget

class MapAnalyzer:
    def __init__(self, project: KeilProject, console: Console):
        self.project = project
        self.console = console

    def find_map_file(self, target: KeilTarget) -> str:
        """Attempts to locate the .map file for the target."""
        if not target.output_name:
            raise FileNotFoundError(f"Target '{target.name}' does not specify an OutputName.")

        possible_dirs = []
        if target.listing_dir:
            possible_dirs.append(os.path.join(self.project.project_dir, target.listing_dir))
        if target.output_dir:
            possible_dirs.append(os.path.join(self.project.project_dir, target.output_dir))
        
        # Fallback to current project dir
        possible_dirs.append(self.project.project_dir)

        map_filename = f"{target.output_name}.map"
        for d in possible_dirs:
            path = os.path.normpath(os.path.join(d, map_filename))
            if os.path.exists(path):
                return path

        raise FileNotFoundError(f"Could not find map file '{map_filename}' in Listing or Output directories.")

    def parse_and_show(self, target_name: Optional[str] = None):
        target = self.project.get_target(target_name)
        try:
            map_file = self.find_map_file(target)
        except FileNotFoundError as e:
            self.console.print(f"[bold red]Error:[/bold red] {e}")
            return

        with open(map_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_ro = 0
        total_rw = 0
        total_rom = 0

        # Regex for bottom totals
        re_ro = re.compile(r"Total RO\s+Size\s*\(Code\s*\+\s*RO Data\)\s+(\d+)")
        re_rw = re.compile(r"Total RW\s+Size\s*\(RW Data\s*\+\s*ZI Data\)\s+(\d+)")
        re_rom = re.compile(r"Total ROM\s+Size\s*\(Code\s*\+\s*RO Data\s*\+\s*RW Data\)\s+(\d+)")

        functions = []
        parsing_sizes = False

        for line in lines:
            if "Image component sizes" in line:
                parsing_sizes = True
                continue
            
            if parsing_sizes:
                m_ro = re_ro.search(line)
                if m_ro:
                    total_ro = int(m_ro.group(1))
                m_rw = re_rw.search(line)
                if m_rw:
                    total_rw = int(m_rw.group(1))
                m_rom = re_rom.search(line)
                if m_rom:
                    total_rom = int(m_rom.group(1))
                
                # Parse function sizes: Code (inc. data) RO Data RW Data ZI Data Debug Object Name
                # Usually look like:
                #    402       10         0         0         0     509   main.o
                # We can't perfectly parse all functions here without heavy regex, but we can try simple split
                parts = line.split()
                if len(parts) >= 7 and parts[0].isdigit() and parts[1].isdigit():
                    try:
                        code_size = int(parts[0])
                        obj_name = parts[-1]
                        if obj_name.endswith(".o") and code_size > 0:
                            functions.append((obj_name, code_size))
                    except ValueError:
                        pass

        table = Table(title=f"Memory Usage: {target.name}", show_header=True, header_style="bold magenta")
        table.add_column("Region", style="cyan")
        table.add_column("Size (Bytes)", justify="right", style="green")
        table.add_column("Size (KB)", justify="right", style="yellow")

        table.add_row("Total RO (Flash/ROM)", str(total_ro), f"{total_ro/1024:.2f} KB")
        table.add_row("Total RW (RAM)", str(total_rw), f"{total_rw/1024:.2f} KB")
        table.add_row("Total ROM Image", str(total_rom), f"{total_rom/1024:.2f} KB")

        self.console.print(table)

        if functions:
            func_table = Table(title="Largest Object Files", show_header=True, header_style="bold blue")
            func_table.add_column("Object Name", style="cyan")
            func_table.add_column("Code Size (Bytes)", justify="right", style="green")
            
            functions.sort(key=lambda x: x[1], reverse=True)
            for name, size in functions[:10]:
                func_table.add_row(name, str(size))
            
            self.console.print(func_table)
