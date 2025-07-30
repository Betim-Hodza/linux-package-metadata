import json
import csv
import cyclonedx
import argparse
import difflib

# Cyclonedx library
from typing import TYPE_CHECKING

from packageurl import PackageURL

from cyclonedx.builder.this import this_component as cdx_lib_component
from cyclonedx.exception import MissingOptionalDependencyException
from cyclonedx.factory.license import LicenseFactory
from cyclonedx.model import XsUri
from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.model.tool import Tool
from cyclonedx.model.contact import OrganizationalEntity
from cyclonedx.output import make_outputter
from cyclonedx.output.json import JsonV1Dot6
from cyclonedx.schema import OutputFormat, SchemaVersion
from cyclonedx.validation import make_schemabased_validator
from cyclonedx.validation.json import JsonStrictValidator


def update_purl(sbom: Bom, csv_data: list[dict]) -> Bom:
    """
    Update the PURL in the SBOM using the data from the CSV file.

    Args:
    - sbom (Bom): The CycloneDX SBOM to update.
    - csv_data (list[Dict]): The data from the CSV file.

    Returns:
    - Bom: The updated SBOM.
    """
    for component in sbom.components:
        # Get the package name and version
        package_name = component.name
        package_version = component.version

        # Look up the package in the CSV file
        closest_match = None
        closest_match_ratio = 0
        for row in csv_data:
            match_ratio = difflib.SequenceMatcher(None, package_name.lower(), row['package'].lower()).ratio()
            if match_ratio > closest_match_ratio:
                closest_match = row
                closest_match_ratio = match_ratio

        if closest_match and closest_match_ratio > 0.6:  # adjust the threshold as needed
            print(f"Matched row: {closest_match} against package name: {package_name}")
            # Update the PURL in the SBOM
            component.purl = PackageURL.from_string(closest_match['purl'])

    return sbom


def load_csv_data(file_path: str) -> list[dict]:
    """
    Load the data from the CSV file.

    Args:
    - file_path (str): The path to the CSV file.

    Returns:
    - list[dict]: The data from the CSV file.
    """
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        return [row for row in reader]

def load_sbom(file_path: str) -> Bom:
    """
    Load the CycloneDX SBOM from a file.

    Args:
    - file_path (str): The path to the SBOM file.

    Returns:
    - Bom: The loaded SBOM.
    """
    with open(file_path, 'r') as file:
        input_json = file.read()
        return Bom.from_json(data=json.loads(input_json))

def save_sbom(sbom: Bom, file_path: str) -> None:
    """
    Save the CycloneDX SBOM to a file.

    Args:
    - sbom (Bom): The SBOM to save.
    - file_path (str): The path to save the SBOM to.
    """
    # Create a JSON outputter
    outputter = make_outputter(sbom, OutputFormat.JSON, SchemaVersion.V1_6)
    json_string = outputter.output_as_string(indent=2)

    with open(file_path, 'w') as file:
        file.write(json_string)

def main() -> None:
    parser = argparse.ArgumentParser(description='Update PURL in SBOM using CSV data')
    parser.add_argument('-c', '--csv', required=True, help='Path to CSV file')
    parser.add_argument('-s', '--sbom', required=True, help='Path to SBOM file')
    parser.add_argument('-o', '--output', default='updated_sbom.json', help='Path to output SBOM file')
    args = parser.parse_args()

    # Load the CSV data
    csv_data = load_csv_data(args.csv)

    # Load the SBOM
    sbom = load_sbom(args.sbom)

    # Update the PURL in the SBOM
    updated_sbom = update_purl(sbom, csv_data)

    # Save the updated SBOM
    save_sbom(updated_sbom, args.output)

if __name__ == '__main__':
    main()