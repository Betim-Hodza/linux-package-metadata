import json
import csv
import argparse
import os

# Cyclonedx library
from typing import TYPE_CHECKING

from packageurl import PackageURL
from cyclonedx.builder.this import this_component as cdx_lib_component
from cyclonedx.model.bom import Bom
from cyclonedx.output import make_outputter
from cyclonedx.schema import OutputFormat, SchemaVersion

matches=0

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
        package_hash = component.hashes

     

        for row in csv_data:
            if package_hash == row['sha256']:
                component.purl = PackageURL.from_string(row['purl'])
                matches = matches + 1
                print(f"Found matching hash for: {package_hash}")



    return sbom


def load_csv_data_in_chunks(file_path: str, chunk_size: int = 1000) -> list[dict]:
    """
    Load the data from the CSV file in chunks.

    Args:
    - file_path (str): The path to the CSV file.
    - chunk_size (int): The size of each chunk. Defaults to 1000.

    Yields:
    - list[dict]: A chunk of data from the CSV file.
    """
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        chunk = []
        for row in reader:
            chunk.append(row)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


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

    # Load the JSON string into a Python dictionary
    sbom_dict = json.loads(json_string)

    # Define the order of the fields according to the CycloneDX format schema
    field_order = [
        'bomFormat',
        'specVersion',
        'version',
        'metadata',
        'components'
    ]

    # Reorder the fields in the SBOM dictionary according to the field order
    sorted_sbom_dict = {key: sbom_dict[key] for key in field_order if key in sbom_dict}

    # Reorder the fields in the metadata dictionary
    if 'metadata' in sorted_sbom_dict:
        metadata_field_order = [
            'timestamp',
            'tools',
            'component'
        ]
        sorted_sbom_dict['metadata'] = {key: sorted_sbom_dict['metadata'][key] for key in metadata_field_order if key in sorted_sbom_dict['metadata']}

        # Remove the bom-ref field from the component dictionary
        if 'component' in sorted_sbom_dict['metadata']:
            component = sorted_sbom_dict['metadata']['component']
            component.pop('bom-ref', None)

        # Reorder the fields in the tools dictionary
        if 'tools' in sorted_sbom_dict['metadata']:
            tools = sorted_sbom_dict['metadata']['tools']
            for tool in tools:
                tool_field_order = [
                    'vendor',
                    'name',
                    'version'
                ]
                tool = {key: tool[key] for key in tool_field_order if key in tool}

    # Reorder the fields in the components dictionary
    if 'components' in sorted_sbom_dict:
        component_field_order = [
            'type',
            'name',
            'version',
            'description',
            'supplier',
            'hashes',
            'purl',
            'externalReferences',
            'properties',
            'evidence'
        ]
        sorted_sbom_dict['components'] = [{key: component[key] for key in component_field_order if key in component} for component in sorted_sbom_dict['components']]

    # Remove the dependencies section
    sorted_sbom_dict.pop('dependencies', None)

    # Add the sourceFiles and compileUnits fields to the components dictionary
    if 'components' in sorted_sbom_dict:
        for component in sorted_sbom_dict['components']:
            if component['name'] == 'pthread_test_lld':
                component['sourceFiles'] = ['pthread_test.c']
                component['compileUnits'] = ['pthread_test.c', 'pthread_test.c']

    # Serialize the sorted SBOM dictionary to a JSON string
    sorted_json_string = json.dumps(sorted_sbom_dict, indent=2)

    with open(file_path, 'w') as file:
        file.write(sorted_json_string)

def main() -> None:
    parser = argparse.ArgumentParser(description='Update PURL in SBOM using CSV data')
    parser.add_argument('--sbom', help='Users sbom', required=True)
    parser.add_argument('-a', '--all', action='store_true', help='Use all csv files to find matching has')
    parser.add_argument('-d', '--distro', help='Pick from a distro specific of csv')
    parser.add_argument('-v', '--version', help='Pick an explicit file with its path')

    parser.add_argument('-o', '--output', default='updated_sbom.json', help='Path to output SBOM file')
    args = parser.parse_args()

    # Load the SBOM
    sbom = load_sbom(args.sbom)

    # Load the CSV data
    if args.all:
        # Define all paths to check
        paths_to_check = [
            'output/alpine/alpine_packages.csv',
            'output/arch/arch_packages.csv',
            'output/centos/',
            'output/debian/',
            'output/fedora/fedora_packages.csv',
            'output/rocky/',
            'output/ubuntu/'
        ]

        for path in paths_to_check:
            if os.path.isfile(path):
                for chunk in load_csv_data_in_chunks(path):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            elif os.path.isdir(path):
                for file in os.listdir(path):
                    if file.endswith('.csv'):
                        for chunk in load_csv_data_in_chunks(os.path.join(path, file)):
                            updated_sbom = update_purl(sbom, chunk)
                            sbom = updated_sbom
    elif args.distro:
        match args.distro:
            case 'ubuntu':
                for chunk in load_csv_data_in_chunks('output/ubuntu/ubuntu_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'debian':
                for chunk in load_csv_data_in_chunks('output/debian/debian_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'fedora':
                for chunk in load_csv_data_in_chunks('output/fedora/fedora_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'rocky':
                for chunk in load_csv_data_in_chunks('output/rocky/rocky_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'centos':
                for chunk in load_csv_data_in_chunks('output/centos/centos_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'arch':
                for chunk in load_csv_data_in_chunks('output/arch/arch_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
            case 'alpine':
                for chunk in load_csv_data_in_chunks('output/alpine/alpine_packages.csv'):
                    updated_sbom = update_purl(sbom, chunk)
                    sbom = updated_sbom
    elif args.version:
        for chunk in load_csv_data_in_chunks(args.version):
            updated_sbom = update_purl(sbom, chunk)
            sbom = updated_sbom

    # Save the updated SBOM
    save_sbom(sbom, args.output)

    print(f"Found {matches} matches")

if __name__ == '__main__':
    main()
