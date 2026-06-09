import json
import os
from typing import List, Optional
from keil_bridge.parser import KeilProject, KeilTarget


class LspGenerator:
    """Generates compile_commands.json (compilation database) for Clangd LSP."""

    def __init__(self, project: KeilProject):
        self.project = project

    def generate(self, target_name: Optional[str] = None, compiler_path: str = "arm-none-eabi-gcc") -> List[dict]:
        """Generates the compilation database entries for the specified target."""
        target = self.project.get_target(target_name)
        
        # Build compilation flags
        defines_flags = [f"-D{d}" for d in target.defines]
        
        # Resolve all include paths to absolute paths
        include_flags = []
        for path in target.include_paths:
            if os.path.isabs(path):
                abs_path = os.path.normpath(path)
            else:
                abs_path = os.path.normpath(os.path.join(self.project.project_dir, path))
            include_flags.append(f"-I{abs_path.replace(os.sep, '/')}")

        # Add embedded target flag by default for arm projects
        base_flags = [compiler_path, "-c"]
        if "arm" in target.cpu.lower() or "cortex" in target.cpu.lower():
            # Add target triple for clangd to find standard headers if using clang
            base_flags.append("-target")
            base_flags.append("arm-none-eabi")

        commands = []
        
        # Iterate over all groups and their files
        for group in target.groups:
            for file in group.files:
                # Only include C (1) and C++ (2) source files in compile_commands.json
                if file.file_type_code not in (1, 2):
                    continue

                abs_file_path = file.absolute_path.replace(os.sep, "/")
                
                # Formulate compilation command line
                cmd_parts = base_flags + defines_flags + include_flags + [
                    "-o",
                    f"{os.path.splitext(file.name)[0]}.o",
                    abs_file_path
                ]
                
                command_str = " ".join(cmd_parts)
                
                entry = {
                    "directory": self.project.project_dir.replace(os.sep, "/"),
                    "command": command_str,
                    "file": abs_file_path
                }
                commands.append(entry)

        return commands

    def write_to_file(self, output_path: Optional[str] = None, target_name: Optional[str] = None, compiler_path: str = "arm-none-eabi-gcc") -> str:
        """Writes the compilation database to a file."""
        if not output_path:
            output_path = os.path.join(self.project.project_dir, "compile_commands.json")
        
        commands = self.generate(target_name, compiler_path)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(commands, f, indent=2)
            
        return output_path
