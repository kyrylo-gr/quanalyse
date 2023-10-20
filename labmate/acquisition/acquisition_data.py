import logging
import os
from typing import Dict, List, Optional, Union

from dh5 import DH5
from ..utils.parse import parse_str

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class NotebookAcquisitionData(DH5):
    """It's a DH5 that has information about the configs file and the cell.

    `configs` is a list of the paths to the files that saved by `save_config_files` function.
    `cell` is a str. It saves using `save_cell` function that will save it to `..._CELL.py` file
    """

    def __init__(
        self,
        filepath: str,
        configs: Optional[Union[Dict[str, str], List[str]]] = None,
        cell: Optional[str] = "none",
        overwrite: Optional[bool] = True,
        save_on_edit: bool = True,
        save_files: bool = True,
        experiment_name: Optional[str] = None,
    ):
        """Create file.
        This class is a DH5 object that saves code and config files.

        Args:
            filepath (str): path to the file to be saved.
            configs (dict[str, str] | list[str], optional): List of the files to read or dictionary
             with a filename as a key and a value as the context of the file. Defaults to None.
            cell (str, optional): string of the cell to be saved under `acquisition_cell` key.
             Defaults to "none". If equals to None or empty string, then warning will be displayed.
            overwrite (bool, optional): True if the existed file should be overwritten.
             Defaults to True.
            save_on_edit (bool, optional): If file is saved every time any changes has made.
             Defaults to True. If False, the file should be saved either with method .save() or
             with method .save_acquisition(...).
            save_files (bool, optional): If config files should be saved as a files and not only
             inside h5 file. Defaults to True.
            experiment_name (Optional[str], optional): Completely optional property for
             external use. Never used internally. Defaults to None.
        """
        super().__init__(
            filepath=filepath,
            save_on_edit=save_on_edit,
            read_only=False,
            overwrite=overwrite,
        )

        if isinstance(configs, list):
            configs = read_config_files(configs)

        self._save_files = save_files

        self._config = configs
        self.save_configs()

        self._cell = cell
        self.save_cell(cell=cell)

        self.experiment_name = experiment_name

        self["useful"] = False

    def save_configs(
        self, configs: Optional[Dict[str, str]] = None, filepath: Optional[str] = None
    ):
        """Save the configuration files to the h5 file and possibly to files.

        If `save_files` during init was set to True, then it will create copy of the files near
         the h5 file.

        Args:
            configs (dict[str, str], optional): Dictionary that contains config files with keys as
             names of the files. Defaults to self._config that was set during init.
            filepath (str, optional): Path+file_prefix to the desired location, i.e. it should end
             with the file prefix to which the config file name and extension will be added. Needed
             if config files are saved as files. Defaults to save filepath as h5 file.
        """
        configs = configs or self._config
        if configs is None:
            return

        self["configs"] = configs

        if not self._save_files:
            return

        filepath = self._check_if_filepath_was_set(filepath, self._filepath)

        for name, value in configs.items():
            with open(filepath + "_" + name, "w", encoding="utf-8") as file:
                file.write(value)

    def save_cell(self, cell: Optional[str] = None, filepath: Optional[str] = None):
        """Save the cell code to the h5 file and possibly to a file.

        If `save_files` during init was set to True, then it will create a '.py' file near
         the h5 file.

        Args:
            cel (str, optional): String that contains code of the cell. Defaults to self._cell that
             was set during init.
            filepath (str, optional): Needed if the code is saved as a file. Path+file_prefix to
             the desired location, i.e. it should end with the file prefix to which the suffix and
             'py' extension will be added. Defaults to save filepath as h5 file.
        """
        cell = cell or self._cell
        if cell == "none":
            return
        if cell is None or cell == "":
            logger.warning("Acquisition cell is not set. Nothing to save")
            return

        self["acquisition_cell"] = cell

        if not self._save_files:
            return

        filepath = self._check_if_filepath_was_set(filepath, self._filepath)
        with open(filepath + "_CELL.py", "w", encoding="utf-8") as file:
            file.write(cell)

    def save_additional_info(self):
        """Save all additional information, i.e. cell code, configs. Put useful key to True."""
        self["useful"] = True

        if not self._save_files:
            return
        self.save_cell()
        self.save_configs()

    def save_acquisition(self, **kwds) -> "NotebookAcquisitionData":
        """Save kwds and all additional information (configs, code, ...)."""
        self.update(**kwds)
        self.save_additional_info()
        if self.save_on_edit is False:
            self.save()
        return self


def read_file(file: str) -> str:
    if not os.path.isfile(file):
        raise ValueError(
            "Cannot read a file if it doesn't exist or it's not a file."
            f"Path: {os.path.abspath(file)}"
        )

    with open(file, "r", encoding="utf-8") as file_opened:
        return file_opened.read()


def read_config_files(config_files: List[str]) -> Dict[str, str]:
    configs: Dict[str, str] = {}
    for config_file in config_files:
        config_file_name = os.path.basename(config_file)
        if config_file_name in configs:
            raise ValueError(
                "Some of the files have the same name. So it cannot be pushed into dictionary to"
                " preserve unique key"
            )
        configs[config_file_name] = read_file(config_file)
    return configs


def eval_config_files(configs: Dict[str, str], evals_modules: dict) -> Dict[str, str]:
    for file, module in evals_modules.items():
        configs[file] = eval_config_file(configs[file], module)
    return configs


def eval_config_file(body, module):
    variables = vars(module)
    lines = body.split("\n")
    for i, line in enumerate(lines):
        for key, (val, _) in parse_str(line).items():
            real_val = variables.get(key, "")
            if (
                isinstance(val, str) and isinstance(real_val, str) and real_val != val.strip("\"'")
            ) or (
                isinstance(val, str)
                and isinstance(real_val, (float, int, complex))
                and not isinstance(real_val, bool)
            ):
                lines[i] += f"  # value: {real_val}"
                # print(f"{val}!={real_val}")
                # print(f"{type(val)}!={type(real_val)}")

    return "\n".join(lines)
