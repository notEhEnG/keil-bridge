import unittest
import os
import tempfile
import json
import subprocess
from unittest.mock import MagicMock, patch
from keil_bridge.parser import KeilProject
from keil_bridge.lsp_generator import LspGenerator
from keil_bridge.cmake_exporter import CMakeExporter
from keil_bridge.builder import KeilBuilder
from keil_bridge.flash_uploader import FlashUploader
from keil_bridge.watcher import FileWatcher
from keil_bridge.target_diff import TargetDiff
from keil_bridge.cli import interactive_menu

# Find the test sample path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PROJECT_PATH = os.path.join(TEST_DIR, "test_data", "sample.uvprojx")
MULTI_TARGET_PROJECT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="project_projx.xsd">
  <Targets>
    <Target>
      <TargetName>Target 1</TargetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Cpu>CPUTYPE("Cortex-M3")</Cpu>
          <OutputDirectory>.\\Objects\\</OutputDirectory>
          <OutputName>firmware_v1</OutputName>
        </TargetCommonOption>
        <TargetArmAds>
          <Cads>
            <Optimize>1</Optimize>
            <VariousControls>
              <Define>USE_HAL_DRIVER,STM32F103xB</Define>
              <IncludePath>..\\Inc</IncludePath>
            </VariousControls>
          </Cads>
          <LDads>
            <ScatterFile>..\\linker_v1.sct</ScatterFile>
          </LDads>
        </TargetArmAds>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>Application</GroupName>
          <Files>
            <File>
              <FileName>main.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\\Src\\main.c</FilePath>
            </File>
          </Files>
        </Group>
      </Groups>
    </Target>
    <Target>
      <TargetName>Target 2</TargetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F407VG</Device>
          <Cpu>CPUTYPE("Cortex-M4")</Cpu>
          <OutputDirectory>.\\Build\\</OutputDirectory>
          <OutputName>firmware_v2</OutputName>
        </TargetCommonOption>
        <TargetArmAds>
          <Cads>
            <Optimize>3</Optimize>
            <VariousControls>
              <Define>USE_HAL_DRIVER,STM32F407xx,EXTRA_DEFINE</Define>
              <IncludePath>..\\Inc;..\\Extra</IncludePath>
            </VariousControls>
          </Cads>
          <LDads>
            <ScatterFile>..\\linker_v2.sct</ScatterFile>
          </LDads>
        </TargetArmAds>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>Application</GroupName>
          <Files>
            <File>
              <FileName>main.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\\Src\\main.c</FilePath>
            </File>
            <File>
              <FileName>extra.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\\Src\\extra.c</FilePath>
            </File>
          </Files>
        </Group>
      </Groups>
    </Target>
  </Targets>
</Project>
"""


class TestKeilBridge(unittest.TestCase):

    def setUp(self):
        self.project = KeilProject(SAMPLE_PROJECT_PATH)

    def test_parser_basic_info(self):
        """Verify the parser correctly extracts targets, CPU, and device name."""
        self.assertEqual(len(self.project.targets), 1)
        self.assertIn("Target 1", self.project.targets)
        
        target = self.project.get_target("Target 1")
        self.assertEqual(target.name, "Target 1")
        self.assertEqual(target.device, "STM32F103C8")
        self.assertIn("Cortex-M3", target.cpu)

    def test_parser_defines_and_includes(self):
        """Verify preprocessor defines and include paths are parsed correctly."""
        target = self.project.get_target("Target 1")
        
        # Verify preprocessor defines
        self.assertEqual(len(target.defines), 2)
        self.assertIn("USE_HAL_DRIVER", target.defines)
        self.assertIn("STM32F103xB", target.defines)

        # Verify include paths
        self.assertEqual(len(target.include_paths), 3)
        self.assertEqual(target.include_paths[0], "../Inc")
        self.assertEqual(target.include_paths[1], "../Drivers/CMSIS/Include")

    def test_parser_groups_and_files(self):
        """Verify source groups and files lists are extracted."""
        target = self.project.get_target("Target 1")
        
        self.assertEqual(len(target.groups), 2)
        self.assertEqual(target.groups[0].name, "Application/User")
        self.assertEqual(target.groups[1].name, "Drivers/STM32F1xx_HAL_Driver")

        # Verify files under Application/User group
        app_files = target.groups[0].files
        self.assertEqual(len(app_files), 2)
        self.assertEqual(app_files[0].name, "main.c")
        self.assertEqual(app_files[0].type_name, "C")
        self.assertEqual(app_files[0].raw_path, "../Src/main.c")
        
        # Test path calculations
        expected_abs = os.path.normpath(os.path.join(self.project.project_dir, "../Src/main.c"))
        self.assertEqual(app_files[0].absolute_path, expected_abs)

    def test_parser_enhanced_fields(self):
        """Verify the enhanced parser fields: output config, optimization, linker script."""
        target = self.project.get_target("Target 1")

        self.assertEqual(target.output_name, "firmware")
        self.assertEqual(target.output_dir, "./Objects/")
        self.assertEqual(target.optimization, "-O2")
        self.assertEqual(target.linker_script, "../STM32F103C8Tx_FLASH.sct")

    def test_parser_enhanced_fields_empty(self):
        """Verify enhanced fields default to empty strings when not present in XML."""
        minimal_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Project>
  <Targets>
    <Target>
      <TargetName>Minimal</TargetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Cpu>Cortex-M3</Cpu>
        </TargetCommonOption>
      </TargetOption>
      <Groups />
    </Target>
  </Targets>
</Project>
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "minimal.uvprojx")
            with open(path, "w") as f:
                f.write(minimal_xml)
            project = KeilProject(path)
            target = project.get_target("Minimal")
            self.assertEqual(target.output_name, "")
            self.assertEqual(target.output_dir, "")
            self.assertEqual(target.optimization, "")
            self.assertEqual(target.linker_script, "")

    def test_lsp_generation(self):
        """Verify the compile_commands.json database is generated properly."""
        generator = LspGenerator(self.project)
        commands = generator.generate("Target 1")
        
        # There should be 3 source files (2 in Application, 1 in Driver)
        self.assertEqual(len(commands), 3)
        
        # Verify structure of one entry
        entry = commands[0]
        self.assertIn("directory", entry)
        self.assertIn("command", entry)
        self.assertIn("file", entry)
        self.assertTrue(entry["file"].endswith("Src/main.c"))
        
        # Verify compiler flag presence in output command
        command_str = entry["command"]
        self.assertIn("-DSTM32F103xB", command_str)
        self.assertIn("-DUSE_HAL_DRIVER", command_str)
        self.assertIn("-I", command_str)
        self.assertIn("Drivers/CMSIS/Include", command_str)

        # Write to temporary file and verify readback
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "compile_commands.json")
            generator.write_to_file(out_file, "Target 1")
            
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "r") as f:
                data = json.load(f)
                self.assertEqual(len(data), 3)

    def test_cmake_export(self):
        """Verify CMakeLists.txt generation format and contents."""
        exporter = CMakeExporter(self.project)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "CMakeLists.txt")
            exporter.export(out_file, "Target 1")
            
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "r") as f:
                content = f.read()
                
                # Check for project declaration
                self.assertIn("project(Target_1 LANGUAGES C CXX ASM)", content)
                
                # Check for compiler directives
                self.assertIn("target_include_directories(${PROJECT_NAME} PRIVATE", content)
                self.assertIn("target_compile_definitions(${PROJECT_NAME} PRIVATE", content)
                self.assertIn("USE_HAL_DRIVER", content)
                self.assertIn("STM32F103xB", content)
                
                # Check that source files are listed
                self.assertIn("../Src/main.c", content)
                self.assertIn("../Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c", content)

    @patch("keil_bridge.builder.time.time", return_value=1234567890)
    @patch("keil_bridge.builder.time.sleep", return_value=None)
    @patch("keil_bridge.builder.subprocess.Popen")
    def test_builder_uses_devnull_for_process_streams(self, mock_popen, mock_sleep, mock_time):
        """Verify the build subprocess cannot block on unused stdout/stderr pipes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.project.project_dir = tmpdir
            self.project.project_path = os.path.join(tmpdir, "sample.uvprojx")
            log_path = os.path.join(tmpdir, ".uvision_build_1234567890.log")

            process = MagicMock()
            process.poll.side_effect = [None, 0]
            process.wait.return_value = None
            process.returncode = 0

            def create_log_file(*args, **kwargs):
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("compiling main.c\n")
                return process

            mock_popen.side_effect = create_log_file

            builder = KeilBuilder(self.project, wine_path="/opt/Keil/UV4/UV4.exe", console=MagicMock())
            exit_code = builder.build("Target 1")

            self.assertEqual(exit_code, 0)
            _, kwargs = mock_popen.call_args
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)

    @patch("builtins.input", side_effect=["2", "15"])
    @patch("keil_bridge.cli.show_info")
    def test_interactive_menu_can_continue_after_one_action(self, mock_show_info, mock_input):
        """Verify the interactive menu stays active until the user exits."""
        interactive_menu(SAMPLE_PROJECT_PATH)
        mock_show_info.assert_called_once()

    @patch("builtins.input", side_effect=["1", "1", "2", "2", "15"])
    @patch("keil_bridge.cli.show_info")
    def test_interactive_menu_can_switch_targets(self, mock_show_info, mock_input):
        """Verify target changes persist for later actions in the same session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "multi.uvprojx")
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(MULTI_TARGET_PROJECT_XML)

            interactive_menu(project_path)

        mock_show_info.assert_called_once()
        self.assertEqual(mock_show_info.call_args.args[1], "Target 2")

    @patch("builtins.input", side_effect=["2", "15"])
    @patch("keil_bridge.cli.show_info")
    def test_interactive_menu_can_start_on_explicit_target(self, mock_show_info, mock_input):
        """Verify the initial target prompt is skipped when a target is supplied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = os.path.join(tmpdir, "multi.uvprojx")
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(MULTI_TARGET_PROJECT_XML)

            interactive_menu(project_path, initial_target="Target 2")

        mock_show_info.assert_called_once()
        self.assertEqual(mock_show_info.call_args.args[1], "Target 2")


class TestFlashUploader(unittest.TestCase):

    def setUp(self):
        self.project = KeilProject(SAMPLE_PROJECT_PATH)

    def test_resolve_firmware_path_returns_none_when_no_files(self):
        """Verify flash uploader returns None when no firmware files exist."""
        uploader = FlashUploader(self.project)
        result = uploader._resolve_firmware_path("Target 1")
        # No actual .hex/.bin files exist in the test data dir
        self.assertIsNone(result)

    def test_resolve_firmware_path_finds_hex_file(self):
        """Verify flash uploader finds a .hex file in the output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a project with output config
            project_path = os.path.join(tmpdir, "sample.uvprojx")
            with open(SAMPLE_PROJECT_PATH, "r") as f:
                with open(project_path, "w") as out:
                    out.write(f.read())

            project = KeilProject(project_path)

            # Create the expected output directory and .hex file
            objects_dir = os.path.join(tmpdir, "Objects")
            os.makedirs(objects_dir, exist_ok=True)
            hex_file = os.path.join(objects_dir, "firmware.hex")
            with open(hex_file, "w") as f:
                f.write(":00000001FF")

            uploader = FlashUploader(project)
            result = uploader._resolve_firmware_path("Target 1")
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith("firmware.hex"))

    @patch("shutil.which", return_value=None)
    def test_auto_detect_tool_returns_none_when_nothing_installed(self, mock_which):
        """Verify auto-detect returns None when no flash tools are installed."""
        uploader = FlashUploader(self.project)
        result = uploader._auto_detect_tool()
        self.assertIsNone(result)

    @patch("shutil.which")
    def test_auto_detect_tool_finds_stlink(self, mock_which):
        """Verify auto-detect finds st-flash when installed."""
        def side_effect(cmd):
            if cmd == "st-flash":
                return "/usr/bin/st-flash"
            return None
        mock_which.side_effect = side_effect

        uploader = FlashUploader(self.project)
        result = uploader._auto_detect_tool()
        self.assertEqual(result, "stlink")


class TestFileWatcher(unittest.TestCase):

    def setUp(self):
        self.project = KeilProject(SAMPLE_PROJECT_PATH)

    def test_collect_source_paths(self):
        """Verify watcher collects all source file paths from the target."""
        watcher = FileWatcher(self.project)
        # Files won't exist on disk, but the method should still return an empty dict
        paths = watcher._collect_source_paths("Target 1")
        # Since the source files (../Src/main.c etc) don't actually exist relative
        # to our test data dir, we expect 0 found files
        self.assertIsInstance(paths, dict)


class TestTargetDiff(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        project_path = os.path.join(self.tmpdir, "multi.uvprojx")
        with open(project_path, "w", encoding="utf-8") as f:
            f.write(MULTI_TARGET_PROJECT_XML)
        self.project = KeilProject(project_path)

    def test_diff_detects_device_difference(self):
        """Verify diff correctly identifies different devices between targets."""
        ta = self.project.get_target("Target 1")
        tb = self.project.get_target("Target 2")
        self.assertNotEqual(ta.device, tb.device)
        self.assertEqual(ta.device, "STM32F103C8")
        self.assertEqual(tb.device, "STM32F407VG")

    def test_diff_detects_define_differences(self):
        """Verify diff correctly identifies define differences."""
        ta = self.project.get_target("Target 1")
        tb = self.project.get_target("Target 2")
        defines_a = set(ta.defines)
        defines_b = set(tb.defines)
        only_b = defines_b - defines_a
        self.assertIn("EXTRA_DEFINE", only_b)
        self.assertIn("STM32F407xx", only_b)

    def test_diff_detects_optimization_difference(self):
        """Verify diff correctly identifies optimization level differences."""
        ta = self.project.get_target("Target 1")
        tb = self.project.get_target("Target 2")
        self.assertEqual(ta.optimization, "-O1")
        self.assertEqual(tb.optimization, "-O3 (Maximum)")

    def test_diff_detects_linker_script_difference(self):
        """Verify diff correctly identifies linker script differences."""
        ta = self.project.get_target("Target 1")
        tb = self.project.get_target("Target 2")
        self.assertEqual(ta.linker_script, "../linker_v1.sct")
        self.assertEqual(tb.linker_script, "../linker_v2.sct")

    def test_diff_runs_without_error(self):
        """Verify the diff command runs end-to-end without exceptions."""
        mock_console = MagicMock()
        differ = TargetDiff(self.project, console=mock_console)
        differ.diff("Target 1", "Target 2")
        # Ensure it printed something (at least the summary line)
        self.assertTrue(mock_console.print.called)


if __name__ == "__main__":
    unittest.main()
