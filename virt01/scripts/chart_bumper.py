"""
Simple python script that is used in github actions to
automatically bump chart dependencies using the updatecli CLI tool.
From: https://blog.promaton.com/how-to-set-up-automated-helm-chart-upgrades-e292192a9aad
https://gist.github.com/nielstenboom/8b1116f7fd00a98aace28d826518e86f#file-chart_bumper-py
"""

from pathlib import Path
import subprocess
import os
import traceback
import logging
from typing import Any
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Add charts here where it is known that higher versions are not
# yet stable or that you would like to disable automatic upgrades for
EXCLUDED_CHARTS = []

# Inject a BUMP_MAJOR env variable if you would like the script to automatically
# bump major chart versions too. Make sure you inspect the upgrade instructions before merging!
BUMP_MAJOR = os.environ.get("BUMP_MAJOR") == "true"


def find_files(directory, extension) -> list[Path]:
    """
    Recursively find all files with a given extension in a specified directory.

    Args:
        directory (str or Path): The root directory to search in.
        extension (str): The file extension to search for (e.g., '.txt').

    Returns:
        list[Path]: A list of Path objects representing files that match the given extension.
    """
    # Create a Path object for the given directory
    path = Path(directory)
    # Finding all files matching the extension recursively
    return list(path.rglob(f"*{extension}"))


def generate_updatecli_manifest(
    dependency: dict, index: int, path_to_chart: Path
) -> str:
    """
    Generate an updatecli manifest for a given dependency.

    Args:
        dependency (dict): The dependency dictionary from Chart.yaml.
        index (int): The index of the dependency in the dependencies list.
        path_to_chart (Path): The path to the chart directory.

    Returns:
        str: The updatecli manifest as a YAML string.
    """
    # bump major or minor depending on set env variable
    if not BUMP_MAJOR:
        version = f"{dependency['version'].split('.')[0]}.*.*"
    else:
        version = "*.*.*"
    manifest = f"""
sources:
lastMinorRelease:
    kind: helmChart
    spec:
        url: "{dependency["repository"]}"
        name: "{dependency["name"]}"
        version: "{version}"
conditions: {{}}
targets:
chart:
    name: Bump Chart dependencies
    kind: helmChart
    spec:
        Name: "{path_to_chart}"
        file: "Chart.yaml"
        key: "dependencies[{index}].version"
        versionIncrement: "patch"
"""
    return manifest


def update_chart(path_chart: str):
    """
    Given a path to a helm chart. Bump the version of the dependencies of this chart
    if any newer versions exist.
    """
    path_to_chart = Path(path_chart).parent
    with open(path_chart) as f:
        text = f.read()

    chart: dict[str, Any] = yaml.safe_load(text)
    if "dependencies" not in chart:
        return

    for i, dependency in enumerate(chart["dependencies"]):
        if dependency["name"] in EXCLUDED_CHARTS:
            print(f"Skipping {dependency['name']} because it is excluded..")
            continue

        manifest = generate_updatecli_manifest(dependency, i, path_to_chart)
        updatecli_yaml_file = f"{path_to_chart}/updatecli.yaml"
        with open(updatecli_yaml_file, "w+") as f:
            f.write(manifest)
            f.flush()
            
        logging.info("Generated updatecli manifest for %s, located at %s", dependency["name"], updatecli_yaml_file)
        try:
            subprocess.check_output(
                ["updatecli", "apply", "--config", updatecli_yaml_file],
                cwd=path_to_chart,
            )
            logging.info("Updated %s to latest version", dependency["name"])
        except subprocess.CalledProcessError as e:
            logging.error("Failed to update %s: %s", dependency["name"], e.output.decode())
            raise RuntimeError(f"Failed to update {dependency['name']}") from e


def main():
    """
    Main function to process and update Helm chart files.

    This function searches for all 'Chart.yaml' files within the specified directory,
    iterates over each found chart file, and attempts to update it using the 'update_chart'
    function. If an error occurs during the update of a chart, it logs the failure and
    prints the exception traceback for debugging purposes.
    """
    charts = find_files("/home/sylvain/gitdev/k8s-home/virt01", "Chart.yaml")
    for chart in charts:
        logging.info("Processing %s", chart)
        try:
            update_chart(chart)
        except (OSError, RuntimeError, yaml.YAMLError) as e:
            print(f"Failed processing chart {chart}: {e}")
            print(traceback.format_exc())


if __name__ == "__main__":
    main()
