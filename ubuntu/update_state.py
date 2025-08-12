import csv
import argparse

# is this the most efficient way ? no.
# i dont care its temporary 
def update_url_in_csv(url, state, csv_file='temp/urls.csv'):
    """
    Updates a specific line in the csv_file based on the given URL and state.

    Args:
        url (str): The URL to update.
        state (str): The state to update.
        csv_file (str, optional): The path to the csv file. Defaults to 'urls.csv'.
    """
    # Read the csv file
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        data = list(reader)

    # Find the row to update
    for i, row in enumerate(data):
        if row[0] == url:
            # Update the state
            data[i][1] = state
            break
    else:
        # If the URL is not found, add a new row
        print(f"[ERROR]: URL not found: {url} ")

    # Write the updated data back to the csv file
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)

def main():
    parser = argparse.ArgumentParser(description='Update URL in CSV file')
    parser.add_argument('-u', '--url', required=True, help='The URL to update')
    parser.add_argument('-s', '--state', required=True, help='The state to update')
    parser.add_argument('-c', '--csv_file', default='urls.csv', help='The path to the csv file')
    args = parser.parse_args()

    update_url_in_csv(args.url, args.state, args.csv_file)

if __name__ == '__main__':
    main()
