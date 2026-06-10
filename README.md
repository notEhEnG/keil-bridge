# Keil uVision Bridge (`uvision-bridge`)

[![License](https://img.shields.io/github/license/username/uvision-bridge?color=blue)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](#)

A modern, cross-platform CLI tool that brings Keil MDK (`.uvprojx`) project compilation and development tooling into the modern era. Developed to run seamlessly on Linux, macOS, and Windows.

## 🚀 Why uvision-bridge?

Keil uVision is the industry-standard IDE for developing ARM Cortex-M microcontrollers (STM32, NXP, Infineon, etc.). However, it is restricted to Windows, doesn't support modern compilers natively, lacks a stdout-friendly CLI, and doesn't output language server (LSP) files for modern editors like VS Code, Cursor, or Neovim.

`uvision-bridge` solves this by wrapping Keil's compiler executable (`UV4.exe`):
* 🍷 **Linux & macOS Support**: Compiles projects using Wine under the hood.
* 🖍️ **Real-Time Colorized Logs**: Redirects Keil's hidden compilation logs to stdout with warning highlighting (yellow), error highlighting (red), and target status updates.
* 🔗 **Path Translation**: Converts Wine-internal paths (like `Z:\home\user\project\main.c`) back to standard Unix paths, making compiler warnings and errors **clickable** in modern terminal/editor environments.
* 🔍 **LSP Integration**: Generates a high-fidelity `compile_commands.json` compilation database directly from the `.uvprojx` configuration.
* 🛠️ **CMake Export**: Converts your uVision project structure to a modern `CMakeLists.txt` targeting the `gcc-arm-none-eabi` cross-compiler.
* ⚡ **Flash Upload**: Upload compiled firmware directly to your MCU via ST-Link, OpenOCD, or J-Link.
* 👁️ **Watch Mode**: Auto-rebuild your project whenever a source file changes.
* 🔀 **Target Diff**: Compare two build targets side-by-side to see what's different.

---

## ✨ Features

- **Project Inspection (`info`)**: See target configurations, chip device profiles, preprocessor defines, include directories, files list, optimization level, output config, linker script, and a file count summary.
- **Modern Compilation (`build`)**: Compile your projects from any terminal, featuring automatic Wine translation, build output redirection, and real-time streaming.
- **Clangd Autocomplete (`lsp`)**: Generate a compiler database to enable code-navigation, syntax errors, and autocomplete inside VS Code, Cursor, or Neovim using clangd.
- **CMake Exporter (`cmake`)**: Instantly migrate Keil projects into GCC/CMake-based projects.
- **Flash Upload (`flash`)**: Upload compiled firmware to your microcontroller using ST-Link, OpenOCD, or J-Link with auto-detection.
- **Watch & Auto-Build (`watch`)**: Monitor source files and automatically trigger a rebuild when any file is saved.
- **Target Comparison (`diff`)**: Compare two build targets side-by-side showing differences in device, defines, includes, files, optimization, and linker scripts.
- **Interactive Target Selector**: Run `uvision-bridge` with no arguments to pick active build targets interactively using your keyboard.

---

## 📦 Installation

### From Source
```bash
# Clone the repository
git clone https://github.com/your-username/uvision-bridge.git
cd uvision-bridge

# Install the package in editable mode
pip install -e .
```

---

## 🛠️ Usage

### CLI Overview
```bash
# Show all available commands and global options
uvision-bridge -h

# Use a default target everywhere, including interactive mode
uvision-bridge -t "Target 2"

# Override the target for a single command
uvision-bridge build -p project.uvprojx -t "Target 1"
```

### 1. Show Project Information
Print the internal structure of your `.uvprojx` project with file count summary.
```bash
uvision-bridge info -p project.uvprojx
```

You can also set a default target once at the top level and let subcommands inherit it when they do not receive their own `-t/--target`:
```bash
uvision-bridge -t "Target 2" info -p project.uvprojx
uvision-bridge -t "Target 2" build -p project.uvprojx
```

### 2. Build the Project
Compile the Keil project from the command line. On Linux/macOS, it will run inside Wine.
```bash
# Build the default/active target
uvision-bridge build -p project.uvprojx

# Build a specific target and rebuild all files
uvision-bridge build -p project.uvprojx -t "Target 1" --rebuild
```

### 3. Generate Compilation Database (`compile_commands.json`)
Extract all include paths, definitions, and compilation flags into a JSON database so clangd LSP can understand the project:
```bash
uvision-bridge lsp -p project.uvprojx
```

### 4. Export to CMake
Create a generic `CMakeLists.txt` for compiling the project using the GNU ARM Embedded Toolchain (`gcc-arm-none-eabi`):
```bash
uvision-bridge cmake -p project.uvprojx
```

### 5. Flash Firmware to MCU
Upload compiled firmware directly to your microcontroller:
```bash
# Auto-detect flash tool and firmware
uvision-bridge flash -p project.uvprojx

# Use a specific flash tool
uvision-bridge flash -p project.uvprojx --tool stlink

# Specify flash base address
uvision-bridge flash -p project.uvprojx --tool openocd --address 0x08000000
```

Supported flash tools: `st-flash` (ST-Link), `openocd` (Open On-Chip Debugger), `JLinkExe` (SEGGER J-Link).

### 6. Watch & Auto-Build
Monitor source files and automatically rebuild when changes are detected:
```bash
# Watch and do incremental builds
uvision-bridge watch -p project.uvprojx

# Watch and do full rebuilds on change
uvision-bridge watch -p project.uvprojx --rebuild
```

### 7. Compare Two Targets
Compare two build targets side-by-side to identify differences:
```bash
uvision-bridge diff -p project.uvprojx --target-a "Target 1" --target-b "Target 2"
```

### 8. Start Interactive Mode on a Specific Target
If you run the CLI without a subcommand, you can preselect a target with the top-level option:
```bash
uvision-bridge -t "Target 2"
```
This skips the initial target chooser when the target exists in the project.

---

## ⚙️ Configuration (Wine Paths)

By default, the tool searches common paths for your Keil v5 installation under Wine:
* `~/.wine/drive_c/Keil_v5/UV4/UV4.exe`
* `C:\Keil_v5\UV4\UV4.exe`

If Keil is installed in a custom Wine prefix or path, you can specify it using the `--wine-path` or `-w` parameter:
```bash
uvision-bridge build -p project.uvprojx -w "/path/to/custom/prefix/drive_c/Keil_v5/UV4/UV4.exe"
```

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.
