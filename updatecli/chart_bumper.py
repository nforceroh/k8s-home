#!/usr/bin/python3 

"""
Simple python script that is used in github actions to
automatically bump chart dependencies using the updatecli CLI tool.
From: https://blog.promaton.com/how-to-set-up-automated-helm-chart-upgrades-e292192a9aad
https://gist.github.com/nielstenboom/8b1116f7fd00a98aace28d826518e86f#file-chart_bumper-py
"""

from pathlib import Path
import subprocess
import os
import logging
from typing import Any
import argparse
import re
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
    path = Path(os.path.abspath(directory))
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
    kind: helmchart
    spec:
      url: "{dependency["repository"]}"
      name: "{dependency["name"]}"
      version: "{version}"
conditions: {{}}
targets:
  chart:
    name: Bump Chart dependencies
    kind: helmchart
    spec:
      Name: "{path_to_chart}"
      file: "Chart.yaml"
      key: "$.dependencies[{index}].version"
      versionIncrement: "patch"
"""
    return manifest


def update_chart(path_chart: Path, apply: bool = False) -> None:
    """
    Given a path to a helm chart. Bump the version of the dependencies of this chart
    if any newer versions exist.
    """
    path_to_chart = Path(path_chart).parent
    with open(path_chart, encoding="utf-8") as f:
        text = f.read()

    chart: dict[str, Any] = yaml.safe_load(text)
    if "dependencies" not in chart:
        return
    mode = "apply" if apply else "diff"
    for i, dependency in enumerate(chart["dependencies"]):
        if dependency["name"] in EXCLUDED_CHARTS:
            print(f"Skipping {dependency['name']} because it is excluded..")
            continue

        manifest = generate_updatecli_manifest(dependency, i, path_to_chart)
        updatecli_yaml_file = f"{path_to_chart}/updatecli.yaml"
        with open(updatecli_yaml_file, "w+", encoding="utf-8") as f:
            f.write(manifest)
            f.flush()

        logging.info(
            "Generated updatecli manifest for %s, located at %s",
            dependency["name"],
            updatecli_yaml_file,
        )
        try:
            output = subprocess.check_output(
                ["updatecli", mode, "--config", updatecli_yaml_file],
                cwd=path_to_chart,
                stderr=subprocess.STDOUT,
            )
            # Regex to match the updatecli output line for version bump
            pattern = re.compile(
                r'\*\skey "\$\.dependencies\[(\d+)\]\.version" should be updated from "([^"]+)" to "([^"]+)", in file "([^"]+)"'
            )
            matches = pattern.findall(output.decode())
            for match in matches:
                dep_index, current_version, next_version, chart_file = match
                logging.info(
                    "Dependency at index %s in %s: version will be bumped from %s to %s",
                    dep_index,
                    chart_file,
                    current_version,
                    next_version,
                )
            logging.info(
                "Successfully ran updatecli %s for %s.\n\n", mode, dependency["name"]
            )
        except subprocess.CalledProcessError as e:
            logging.error(
                "Failed to update %s: %s", dependency["name"], e.output.decode()
            )
            raise RuntimeError(f"Failed to update {dependency['name']}") from e


def main():
    """
    Main function to process and update Helm chart files.

    This function searches for all 'Chart.yaml' files within the specified directory,
    iterates over each found chart file, and attempts to update it using the 'update_chart'
    function. If an error occurs during the update of a chart, it logs the failure and
    prints the exception traceback for debugging purposes.
    """
    parser = argparse.ArgumentParser(
        description="Bump Helm chart dependencies using updatecli."
    )
    parser.add_argument(
        "--charts-root",
        type=str,
        default=".",
        help="Root directory to search for Helm charts (default: current directory).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the updates to the charts. If not set, only show the diff.",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO).",
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)
    logging.info("Starting chart dependency bump process")
    logging.debug("Arguments: %s", args)
    logging.info("Searching for Helm charts in %s", args.charts_root)

    charts = [
        chart
        for chart in find_files(args.charts_root, ".yaml")
        if chart.name == "Chart.yaml"
    ]
    logging.info("Found %d Chart.yaml files", len(charts))
    if not charts:
        logging.warning("No Chart.yaml files found in %s", args.charts_root)

    for chart in charts:
        logging.info("Processing chart: %s", chart)
        try:
            update_chart(chart, apply=args.apply)
            logging.info("Finished processing chart: %s", chart)
        except (OSError, RuntimeError, yaml.YAMLError) as e:
            logging.error("Failed processing chart %s: %s", chart, e)
            logging.exception("Exception occurred during chart processing")

    logging.info("Chart dependency bump process completed")


if __name__ == "__main__":
    main()
