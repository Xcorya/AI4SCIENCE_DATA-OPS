"""Include canonical source configs in wheels without maintaining duplicate files."""
from pathlib import Path
from shutil import copyfile
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
CONFIGS = ("policy.json", "taxonomy.json")


class BuildWithConfigs(build_py):
    def run(self):
        super().run()
        directory = Path(self.build_lib) / "visual_flywheel" / "data"
        directory.mkdir(parents=True, exist_ok=True)
        for name in CONFIGS:
            copyfile(ROOT / "configs" / name, directory / name)

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        return outputs + [str(Path(self.build_lib) / "visual_flywheel" / "data" / name)
                          for name in CONFIGS]


setup(cmdclass={"build_py": BuildWithConfigs})
