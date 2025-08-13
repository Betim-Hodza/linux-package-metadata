import pandas as pd
import argparse

# is this the most efficient way ? no.
# i dont care its temporary 
def update_url_in_csv(url, state, csv_file):
    """
    Updates a specific line in the csv_file based on the given URL and state.

    Args:
        url (str): The URL to update.
        state (str): The state to update.
        csv_file (str, optional): The path to the csv file. Defaults to 'urls.csv'.
    """

    # Define the output file and write header only once
    df = pd.read_csv(csv_file)

    # find the row where urls match
    if url in df['urls'].values:
        df.loc[df['urls'] == url, 'state'] = state
        print(f"Updated {url} to state '{state}")

        df.to_csv(csv_file, index=False)
    else:
        print(f"URL {url} not found in CSV")
        return


def main():
    parser = argparse.ArgumentParser(description='Update URL in CSV file')
    parser.add_argument('-u', '--url', required=True, help='The URL to update')
    parser.add_argument('-s', '--state', required=True, help='The state to update')
    parser.add_argument('-c', '--csv_file', default='urls.csv', help='The path to the csv file')
    args = parser.parse_args()

    update_url_in_csv(args.url, args.state, args.csv_file)

if __name__ == '__main__':
    main()
