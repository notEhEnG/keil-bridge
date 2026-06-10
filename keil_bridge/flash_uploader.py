import os
import shutil
import subprocess
import sys
from typing import Optional
from rich.console import Console

from keil_bridge.parser import KeilProject

console = Console()


class FlashUploader:
    """Uploads compiled firmware to an MCU using ST-Link, OpenOCD, or J-Link."""

    SUPPORTED_TOOLS = {
        "stlink": {
            "commands": ["st-flash"],
            "description": "STMicroelectronics ST-Link",
        },
        "openocd": {
            "commands": ["openocd"],
            "description": "Open On-Chip Debugger",
        },
        "jlink": {
            "commands": ["JLinkExe", "jlink", "JLink"],
            "description": "SEGGER J-Link",
        },
    }

    def __init__(self, project: KeilProject):
        self.project = project

    def _find_tool(self, tool_name: str) -> Optional[str]:
        """Checks if a specific flash tool is available on the system PATH."""
        tool_info = self.SUPPORTED_TOOLS.get(tool_name)
        if not tool_info:
            return None
        for cmd in tool_info["commands"]:
            if shutil.which(cmd):
                return cmd
        return None

    def _auto_detect_tool(self) -> Optional[str]:
        """Attempts to find any supported flash tool on the system."""
        for tool_name in self.SUPPORTED_TOOLS:
            cmd = self._find_tool(tool_name)
            if cmd:
                return tool_name
        return None

    def _resolve_firmware_path(self, target_name: Optional[str] = None) -> Optional[str]:
        """Resolves the path to the compiled .hex or .bin firmware file."""
        target = self.project.get_target(target_name)

        if target.output_dir and target.output_name:
            output_dir = target.output_dir
            if not os.path.isabs(output_dir):
                output_dir = os.path.join(self.project.project_dir, output_dir)
            output_dir = os.path.normpath(output_dir)

            # Try common firmware extensions in order of preference
            for ext in [".hex", ".bin", ".axf", ".elf"]:
                candidate = os.path.join(output_dir, target.output_name + ext)
                if os.path.exists(candidate):
                    return candidate

        # Fallback: search the project directory for common firmware files
        for root, _dirs, files in os.walk(self.project.project_dir):
            for f in files:
                if f.endswith((".hex", ".bin")):
                    return os.path.join(root, f)

        return None

    def _flash_stlink(self, firmware_path: str, address: str = "0x08000000") -> int:
        """Flashes firmware using st-flash."""
        cmd_name = self._find_tool("stlink")
        if not cmd_name:
            console.print("[bold red]Error:[/bold red] st-flash not found in PATH.")
            return -1

        if firmware_path.endswith(".hex"):
            cmd = [cmd_name, "--format", "ihex", "write", firmware_path]
        else:
            cmd = [cmd_name, "write", firmware_path, address]

        console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=False)
            return result.returncode
        except Exception as e:
            console.print(f"[bold red]Flash failed:[/bold red] {e}")
            return -1

    def _flash_openocd(self, firmware_path: str, target_device: str = "") -> int:
        """Flashes firmware using OpenOCD."""
        cmd_name = self._find_tool("openocd")
        if not cmd_name:
            console.print("[bold red]Error:[/bold red] openocd not found in PATH.")
            return -1

        # Auto-detect interface and target config
        interface = "interface/stlink.cfg"
        target_cfg = "target/stm32f1x.cfg"

        device_lower = target_device.lower()
        if "stm32f4" in device_lower:
            target_cfg = "target/stm32f4x.cfg"
        elif "stm32f7" in device_lower:
            target_cfg = "target/stm32f7x.cfg"
        elif "stm32l4" in device_lower:
            target_cfg = "target/stm32l4x.cfg"
        elif "stm32h7" in device_lower:
            target_cfg = "target/stm32h7x.cfg"
        elif "stm32g0" in device_lower:
            target_cfg = "target/stm32g0x.cfg"
        elif "stm32g4" in device_lower:
            target_cfg = "target/stm32g4x.cfg"

        cmd = [
            cmd_name,
            "-f", interface,
            "-f", target_cfg,
            "-c", "program {} verify reset exit".format(firmware_path),
        ]

        console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=False)
            return result.returncode
        except Exception as e:
            console.print(f"[bold red]Flash failed:[/bold red] {e}")
            return -1

    def _flash_jlink(self, firmware_path: str, target_device: str = "STM32F103C8") -> int:
        """Flashes firmware using J-Link Commander."""
        cmd_name = self._find_tool("jlink")
        if not cmd_name:
            console.print("[bold red]Error:[/bold red] JLinkExe not found in PATH.")
            return -1

        # Create a temporary JLink command script
        jlink_script = os.path.join(self.project.project_dir, ".jlink_flash.tmp")
        script_content = (
            f"device {target_device}\n"
            "si SWD\n"
            "speed 4000\n"
            "connect\n"
            f"loadfile {firmware_path}\n"
            "r\n"
            "g\n"
            "exit\n"
        )

        try:
            with open(jlink_script, "w") as f:
                f.write(script_content)

            cmd = [cmd_name, "-CommandFile", jlink_script]
            console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=False)
            return result.returncode
        except Exception as e:
            console.print(f"[bold red]Flash failed:[/bold red] {e}")
            return -1
        finally:
            if os.path.exists(jlink_script):
                os.remove(jlink_script)

    def flash(
        self,
        target_name: Optional[str] = None,
        tool: str = "auto",
        address: str = "0x08000000",
    ) -> int:
        """Main flash method. Detects tool and firmware, then uploads."""
        target = self.project.get_target(target_name)
        console.print(f"[bold blue]Preparing to flash target:[/bold blue] '{target.name}'")
        console.print(f"[blue]Device:[/blue] {target.device}")

        # Resolve firmware path
        firmware_path = self._resolve_firmware_path(target_name)
        if not firmware_path:
            console.print(
                "[bold red]Error:[/bold red] Could not find compiled firmware "
                "(.hex/.bin). Please build the project first."
            )
            return -1

        console.print(f"[blue]Firmware:[/blue] {firmware_path}")

        # Resolve flash tool
        if tool == "auto":
            detected = self._auto_detect_tool()
            if not detected:
                console.print(
                    "[bold red]Error:[/bold red] No supported flash tool found. "
                    "Install one of: st-flash, openocd, JLinkExe"
                )
                return -1
            tool = detected
            tool_desc = self.SUPPORTED_TOOLS[tool]["description"]
            console.print(f"[blue]Flash Tool:[/blue] {tool_desc} (auto-detected)")
        else:
            if tool not in self.SUPPORTED_TOOLS:
                console.print(f"[bold red]Error:[/bold red] Unknown tool '{tool}'. Use: stlink, openocd, jlink")
                return -1
            if not self._find_tool(tool):
                tool_desc = self.SUPPORTED_TOOLS[tool]["description"]
                console.print(f"[bold red]Error:[/bold red] {tool_desc} not found in PATH.")
                return -1

        console.print("")

        # Execute flash
        if tool == "stlink":
            exit_code = self._flash_stlink(firmware_path, address)
        elif tool == "openocd":
            exit_code = self._flash_openocd(firmware_path, target.device)
        elif tool == "jlink":
            exit_code = self._flash_jlink(firmware_path, target.device)
        else:
            exit_code = -1

        if exit_code == 0:
            console.print("\n[bold green]✓ Flash Succeeded![/bold green]")
        else:
            console.print(f"\n[bold red]✗ Flash Failed (exit code {exit_code})[/bold red]")

        return exit_code
