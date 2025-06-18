"""
Simple python script that is used in github actions to
automatically bump chart dependencies using the updatecli CLI tool.
"""

from pathlib import Path
import subprocess
import yaml
import os
import traceback
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Add charts here where it is known that higher versions are not
# yet stable or that you would like to disable automatic upgrades for
EXCLUDED_CHARTS = []

# Inject a BUMP_MAJOR env variable if you would like the script to automatically
# bump major chart versions too. Make sure you inspect the upgrade instructions before merging!
BUMP_MAJOR = os.environ.get("BUMP_MAJOR") == "true"


def find_files(directory, extension):
    # Create a Path object for the given directory
    path = Path(directory)
    # Finding all files matching the extension recursively
    return list(path.rglob(f"*{extension}"))


def update_chart(path_chart: str):
    """
    Given a path to a helm chart. Bump the version of the dependencies of this chart
    if any newer versions exist.
    """
    path_to_chart = os.path.dirname(path_chart)
    with open(path_chart) as f:
        text = f.read()

    chart: dict = yaml.safe_load(text)

    if not "dependencies" in chart:
        return

    for i, dependency in enumerate(chart["dependencies"]):

        if dependency["name"] in EXCLUDED_CHARTS:
            print(f"Skipping {dependency['name']} because it is excluded..")
            continue

        # bump major or minor depending on set env variable
        version = (
            f"{dependency['version'].split('.')[0]}.*.*" if not BUMP_MAJOR else "*.*.*"
        )
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
           key: "dependencies[{i}].version"
           versionIncrement: "patch"
"""

        with open(f"{path_to_chart}/updatecli.yaml", "w") as f:
            f.write(manifest)


#       subprocess.check_output("updatecli apply --config updatecli.yaml".split(" "))


def main():
    charts = find_files("/home/sylvain/gitdev/k8s-home/virt01", "Chart.yaml")
    for chart in charts:
        logging.info("Processing %s", chart)
        try:
            update_chart(chart)
        except Exception as e:
            print(f"Failed processing chart {chart}")
            print(traceback.format_exc())

if __name__ == "__main__":
    main()
