import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional


class KeilFile:
    """Represents a source, header, or library file in a Keil project."""

    TYPE_MAP = {
        1: "C",
        2: "C++",
        3: "Assembly",
        4: "Header",
        5: "Object",
        7: "Library",
    }

    def __init__(self, file_name: str, file_path: str, file_type: int, project_dir: str):
        self.name = file_name
        # Clean the windows relative path
        self.raw_path = file_path.replace("\\", "/")
        self.file_type_code = file_type
        self.type_name = self.TYPE_MAP.get(file_type, "Unknown")
        self.project_dir = project_dir

    @property
    def absolute_path(self) -> str:
        """Resolves the file path to an absolute path."""
        if os.path.isabs(self.raw_path):
            return os.path.normpath(self.raw_path)
        # Handle relative path resolution from project directory
        return os.path.normpath(os.path.join(self.project_dir, self.raw_path))

    @property
    def relative_path(self) -> str:
        """Returns path relative to project directory with forward slashes."""
        abs_p = self.absolute_path
        try:
            return os.path.relpath(abs_p, self.project_dir).replace("\\", "/")
        except ValueError:
            return self.raw_path

    def __repr__(self) -> str:
        return f"<KeilFile {self.name} ({self.type_name}) path={self.raw_path}>"


class KeilGroup:
    """Represents a file group (virtual folder) in a Keil project."""

    def __init__(self, name: str):
        self.name = name
        self.files: List[KeilFile] = []

    def add_file(self, keil_file: KeilFile):
        self.files.append(keil_file)

    def __repr__(self) -> str:
        return f"<KeilGroup {self.name} files={len(self.files)}>"


class KeilTarget:
    """Represents a build target in a Keil project."""

    OPTIMIZATION_MAP = {
        "0": "-O0 (None)",
        "1": "-O1",
        "2": "-O2",
        "3": "-O3 (Maximum)",
        "4": "-Oz (Size)",
    }

    def __init__(self, name: str, device: str, cpu: str = ""):
        self.name = name
        self.device = device
        self.cpu = cpu
        self.include_paths: List[str] = []
        self.defines: List[str] = []
        self.groups: List[KeilGroup] = []
        self.linker_script: str = ""
        self.output_name: str = ""
        self.output_dir: str = ""
        self.listing_dir: str = ""
        self.optimization: str = ""

    def __repr__(self) -> str:
        return (
            f"<KeilTarget {self.name} device={self.device} "
            f"groups={len(self.groups)} defines={len(self.defines)}>"
        )


class KeilProject:
    """Parses and exposes structure of a Keil uVision project (.uvprojx)."""

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.project_dir = os.path.dirname(self.project_path)
        self.targets: Dict[str, KeilTarget] = {}
        self.active_target_name: Optional[str] = None
        self._parse()

    def _parse(self):
        """Parses the XML structure of the Keil project."""
        if not os.path.exists(self.project_path):
            raise FileNotFoundError(f"Project file not found: {self.project_path}")

        try:
            tree = ET.parse(self.project_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML from project file: {e}")

        # In .uvprojx, targets are under <Targets>/<Target>
        targets_node = root.find("Targets")
        if targets_node is None:
            return

        for target_node in targets_node.findall("Target"):
            target_name_node = target_node.find("TargetName")
            if target_name_node is None or not target_name_node.text:
                continue

            target_name = target_name_node.text.strip()

            # Parse device and options
            device = ""
            cpu = ""
            target_option = target_node.find("TargetOption")
            if target_option is not None:
                common_option = target_option.find("TargetCommonOption")
                if common_option is not None:
                    device_node = common_option.find("Device")
                    if device_node is not None and device_node.text:
                        device = device_node.text.strip()
                    
                    cpu_node = common_option.find("Cpu")
                    if cpu_node is not None and cpu_node.text:
                        cpu = cpu_node.text.strip()

            target = KeilTarget(target_name, device, cpu)

            # Parse output configuration from TargetCommonOption
            if target_option is not None:
                common_option = target_option.find("TargetCommonOption")
                if common_option is not None:
                    output_name_node = common_option.find("OutputName")
                    if output_name_node is not None and output_name_node.text:
                        target.output_name = output_name_node.text.strip()

                    output_dir_node = common_option.find("OutputDirectory")
                    if output_dir_node is not None and output_dir_node.text:
                        target.output_dir = output_dir_node.text.strip().replace("\\", "/")

                    listing_path_node = common_option.find("ListingPath")
                    if listing_path_node is not None and listing_path_node.text:
                        target.listing_dir = listing_path_node.text.strip().replace("\\", "/")

            # Parse compiler flags (defines & includes)
            if target_option is not None:
                # Typically under <TargetArmAds>/<Cads>/<VariousControls>
                arm_ads = target_option.find("TargetArmAds")
                if arm_ads is not None:
                    cads = arm_ads.find("Cads")
                    if cads is not None:
                        controls = cads.find("VariousControls")
                        if controls is not None:
                            # Parse defines
                            define_node = controls.find("Define")
                            if define_node is not None and define_node.text:
                                # Keil defines are separated by commas or spaces
                                raw_defines = define_node.text.strip()
                                # Clean up comma separators
                                target.defines = [
                                    d.strip()
                                    for d in raw_defines.replace(",", " ").split()
                                    if d.strip()
                                ]

                            # Parse optimization level
                            optimize_node = cads.find("Optimize")
                            if optimize_node is not None and optimize_node.text:
                                raw_opt = optimize_node.text.strip()
                                target.optimization = KeilTarget.OPTIMIZATION_MAP.get(raw_opt, f"Level {raw_opt}")

                            # Parse include paths
                            include_node = controls.find("IncludePath")
                            if include_node is not None and include_node.text:
                                raw_includes = include_node.text.strip()
                                # Keil include paths are separated by semicolons
                                paths = raw_includes.split(";")
                                for p in paths:
                                    p = p.strip()
                                    if p:
                                        target.include_paths.append(p.replace("\\", "/"))

                    # Parse linker script from LDads
                    ldads = arm_ads.find("LDads")
                    if ldads is not None:
                        scatter_node = ldads.find("ScatterFile")
                        if scatter_node is not None and scatter_node.text:
                            target.linker_script = scatter_node.text.strip().replace("\\", "/")

            # Parse source groups & files
            groups_node = target_node.find("Groups")
            if groups_node is not None:
                for group_node in groups_node.findall("Group"):
                    group_name_node = group_node.find("GroupName")
                    if group_name_node is None or not group_name_node.text:
                        continue
                    
                    group_name = group_name_node.text.strip()
                    group = KeilGroup(group_name)

                    files_node = group_node.find("Files")
                    if files_node is not None:
                        for file_node in files_node.findall("File"):
                            file_name_node = file_node.find("FileName")
                            file_path_node = file_node.find("FilePath")
                            file_type_node = file_node.find("FileType")

                            if (
                                file_name_node is not None
                                and file_path_node is not None
                                and file_name_node.text
                                and file_path_node.text
                            ):
                                f_name = file_name_node.text.strip()
                                f_path = file_path_node.text.strip()
                                f_type = 1
                                if file_type_node is not None and file_type_node.text:
                                    try:
                                        f_type = int(file_type_node.text.strip())
                                    except ValueError:
                                        pass

                                k_file = KeilFile(
                                    f_name, f_path, f_type, self.project_dir
                                )
                                group.add_file(k_file)

                    target.groups.append(group)

            self.targets[target_name] = target
            if self.active_target_name is None:
                self.active_target_name = target_name

    def get_target(self, name: Optional[str] = None) -> KeilTarget:
        """Retrieves a target by name. Defaults to the active/first target."""
        if not self.targets:
            raise ValueError("No targets found in the project.")
        
        target_name = name or self.active_target_name
        if not target_name or target_name not in self.targets:
            # Fallback to the first target if the specified one doesn't exist
            first_target = list(self.targets.keys())[0]
            return self.targets[first_target]
        
        return self.targets[target_name]
