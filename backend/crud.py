import re
import csv
import hashlib
import datetime
import time
import os
import uuid
import random
from pathlib import Path
from typing import Optional
from typing import List
from typing import Dict
from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy import exc
from sqlalchemy import select
from sqlalchemy import insert
from sqlalchemy import update
from sqlalchemy.engine.base import Engine
import pandas as pd
import yaml

from backend import database as db
from backend import queries
from backend import checks

folder_path = "./banking_csvs/"
yml_file_path = "./vendors.yml"
session = db.init_db()


def is_bank(first_row: List[str], profile_columns: Dict) -> bool:
    """
    Used when importing banks to check that the file we're looking at is in fact from a bank export
    Check if the given row matches the expected column names for a bank profile
    """
    for key in profile_columns:
        # Get the index and name of the current column
        col_index = profile_columns[key]["index"]
        col_name = profile_columns[key]["name"]

        # Check if the value in the given row for the current column matches the expected column name
        if first_row[col_index] != col_name:
            return False

    # If all columns match the expected names, return True
    return True


def detect_bank(first_row, bank_profiles: dict) -> dict | None:
    """
    Used when importing banks to determine which bank
    Detect which bank we're importing by matching to a bank profile
    """
    for key, value in bank_profiles.items():
        # Get the column names for the current bank profile
        cols = bank_profiles[key]["columns"]

        # Check if the given row matches the expected column names for the current bank profile
        if is_bank(first_row, cols):
            # If it matches, return the bank profile
            return value

    # If no bank profile matches the given row, return None
    return None


def clean_money(amount_string: str, bank_profile: dict) -> str:
    """
    Used because some banks have different characters around their numbers
    Clean the given amount string by removing any unwanted characters and applying the bank's value flipping setting
    """
    # Create a new string to store the cleaned amount
    new_string = ""

    # Iterate over the characters in the given amount string
    for char in amount_string:
        # Skip any unwanted characters
        if char != "$" and char != ",":
            # Add any other characters to the new string
            new_string += char

    # Check if the bank's value flipping setting is enabled
    if bank_profile["flip_values"] == True:
        # If it is, multiply the cleaned amount by -1 to flip its sign
        new_string = str(float(new_string) * -1)

    # Return the cleaned amount
    return new_string


def process_date(bank_profile: dict, date: str) -> str:
    """
    Use this because we're storing dates
    Convert the raw date string from the transaction report to a ISO 8601
    """

    # Get the date string format definition
    format_def = bank_profile["columns"]["date"]["date_format"]

    # Parse the date using the format definition to a Python time_struct
    time_struct = time.strptime(date, format_def)

    # Get a datetime object from the time struct
    dt = datetime.datetime.fromtimestamp(time.mktime(time_struct))

    # Represent the datetime as an ISO 8601 string
    return dt.isoformat()


def import_transactions(
    storage_folder_path: str, bank_profiles: dict, engine: Engine
) -> None:
    """
    Use this to import transactions.
    Imports all default information about transactions from new transaction imports from a bank
    """
    bank_profile = None
    for file_path in get_latest_export_paths(storage_folder_path):
        with open(file_path, newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=",", quotechar='"')
            # Detect the bank
            row_1 = next(reader)
            bank_profile = detect_bank(row_1, bank_profiles)
            # Handle the case where bank_profile is None
            if bank_profile is None:
                continue
            print(f"Detected {bank_profile['bank_name']}.")
            col_map = bank_profile["columns"]
            import_new_expense_imports(file_path, engine)
            for row in reader:
                Date = process_date(bank_profile, row[col_map["date"]["index"]])
                Transaction = row[col_map["transaction"]["index"]]
                Name = row[col_map["name"]["index"]]
                Memo = row[col_map["memo"]["index"]]
                Amount = clean_money(row[col_map["amount"]["index"]], bank_profile)
                Hash = hash_transaction(Date, Transaction, Name, Memo, Amount)
                VendorUUID = queries.vendorizer(Name)
                row = insert(db.Transactions).values(
                    Date=Date,
                    Transaction=Transaction,
                    Name=Name,
                    Memo=Memo,
                    Amount=Amount,
                    VendorUUID=VendorUUID,
                    Hash=Hash,
                )
                with engine.connect() as conn:
                    try:
                        conn.execute(row)
                    except exc.IntegrityError:
                        session.rollback()
                        print(f"{Hash} is a duplicate expense")
        if bank_profile is None:
            # Handle the case where no bank profile was detected
            print(f"Error: No bank profile detected for {file_path}")
            return None
        else:
            name = file_path.rsplit("/", maxsplit=1)[-1]
            print(f"Successfully imported all transactions from {name}")


def import_new_expense_imports(file_path: str, engine: Engine) -> None:
    """
    Used so that we can import the files we read from so later we don't look at the same file twice.
    Imports the file names of new transaction imports from a bank.
    """
    name = file_path.rsplit("/", maxsplit=1)[-1]
    expense_import = insert(db.ExpenseImports).values(Filename=name)
    with engine.connect() as conn:
        conn.execute(expense_import)
        print(f"Added {name} to list of known files")


def make_children(
    engine: Engine, id: int, rows: List[Tuple[float, str, str, str]]
) -> None:
    """
    Use this to make sub transactions, this is useful for if you buy from a place like amazon
    and the items would actually go to another tag and/or need to be split.
    Create child transactions for the parent transaction with the given ID, using the given rows.
    children = [
        (20.00, "vendor1", "Books", "Book 1"),
        (12.00, "vendor2", "Books", "Book 2"),
        (amount, vendor, tag, description)
    ]
    """
    with engine.connect() as conn:
        # Check that the given rows satisfy the amount and tag checks
        if (queries.amount_check(rows, id)) and (queries.tag_check(rows)) == True:
            # If they do, iterate over the rows
            for row in rows:
                # Get the parent transaction's information
                parent_query = (
                    select(
                        db.Transactions.Date,
                        db.Transactions.Transaction,
                        db.Transactions.Name,
                        db.Transactions.Memo,
                    )
                ).where(db.Transactions.id == id)
                parent_columns = pd.read_sql(parent_query, conn)
                parent_id = id
                date = parent_columns["Date"].values[0]  # type: ignore
                transaction = parent_columns["Transaction"].values[0]  # type: ignore
                name = parent_columns["Name"].values[0]  # type: ignore
                memo = parent_columns["Memo"].values[0]  # type: ignore

                # Get the information for the current row
                amount = row[0]
                vendor_uuid = queries.vendor_to_uuid(row[1])
                tag = row[2]
                desc = row[3]

                # Used to show when the child transaction was initialized
                current_time = datetime.datetime.now().isoformat()

                # Insert the current row into the ChildTransactions table
                row = insert(db.ChildTransactions).values(
                    Parent_id=parent_id,
                    Date=date,
                    Transaction=transaction,
                    Name=name,
                    Memo=memo,
                    Amount=amount,
                    VendorUUID=vendor_uuid[0],
                    Description=desc,
                    Tag=tag,
                    Initialized=current_time,
                )

                # Try to execute the query
                try:
                    conn.execute(row)
                    print("You have beautiful baby expenses")
                except exc.IntegrityError:
                    session.rollback()
                    print("Did not make children")
                else:
                    # If the query is successful, update the parent transaction to indicate that it has children
                    label_parent = (
                        update(db.Transactions)
                        .where(db.Transactions.id == id)
                        .values(Has_Child="True")
                    )
                    conn.execute(label_parent)
        else:
            # If the checks fail, return the output of amount_check and tag_check
            print(
                f"amount_check: {queries.amount_check(rows, id)}, tag_check: {queries.tag_check(rows)}"
            )


def hash_transaction(
    Date: str, Transaction: str, Name: str, Memo: str, Amount: str
) -> object:
    """
    Creates of hash of all transactions. Note that this still isn't perfect for determining
    unique transactions as it is possible to have exact duplicate transactions, although veryyy rare.
    If transaction date includes more grainular information like hour or minute, this wouldn't be an issue.
    """
    row = [Date, Transaction, Name, Memo, Amount]
    joined = "".join(row)
    return hashlib.md5(joined.lower().encode("utf-8")).hexdigest()


def get_all_export_names(storage_folder_path: str) -> list:
    """
    Used in the get_latest_export_paths function so that we can then figure out which ones are new
    Return a list of all file names of CSV files in the given storage folder.
    """
    # Get a list of file paths of all CSV files in the given storage folder
    export_file_paths = Path(storage_folder_path).glob("*.[cC][sS][vV]")

    # Convert the file paths to strings
    string_file_paths = [str(ef) for ef in export_file_paths]

    # Create an empty list to store the file names
    string_file_names = []

    # Iterate over the file paths
    for sfp in string_file_paths:
        # Split the file path at the last slash, and get the last part (the file name)
        split_list = sfp.rsplit("/", maxsplit=1)[-1]

        # Add the file name to the list of file names
        string_file_names.append(split_list)

    # Return the list of file names
    return string_file_names


def get_latest_export_paths(storage_folder_path: str) -> list:
    """
    Return the paths of the new CSV files in the given storage folder that have not yet been imported.
    This function is used when importing transactions, so that only new files are iterated through.
    """
    # Get a list of all file names in the given storage folder
    all_file_names = get_all_export_names(storage_folder_path)

    # Create an empty list to store the names of the files that have been imported
    imported_files = []

    # Query the ExpenseImports table for the names of the files that have been imported
    imported_files_query = select(db.ExpenseImports.Filename)

    # Create an empty list to store the paths of the new files
    new_file_paths = []

    # Connect to the database
    with db.engine.connect() as conn:
        # Iterate over the query results
        for row in conn.execute(imported_files_query):
            # Add the name of each imported file to the imported_files list
            imported_files.append(row[0])

    # Get the list of new files by taking the set difference between all_file_names and imported_files
    new_files = list(set(all_file_names) - set(imported_files))

    # If there are any new files, append their paths to the new_file_paths list
    if len(new_files) >= 1:
        [new_file_paths.append(storage_folder_path + file) for file in new_files]
    else:
        print("no new bank files to import")

    # Return the list of new file paths
    return new_file_paths


def add_vendor(
    vendors: List[Dict[str, str]], engine: Engine, session, yml_file_path: str
) -> None:
    """
    Adds a vendor and pattern to Vendor table, use this to add a new vendor.
    If you want to rebrand a vendor, like time warner cable to spectrum, just provide the UUID in the dictonary.
    If you do that, instead of generating a new one, it'll use the one passed in. In a case like this, you must provide
    a name, but don't need to provide a pattern (although you probably want to udpate the pattern) or tag, it'll use
    the old one.
    vendors=[
        {
            "UUID": "2a519362-12fe-4d15-aab4-5ae7af6e73e9",
            "Vendor": "Vendor1",
            "Pattern": "vendor1",
            "Tag": "Travel",
        },
        {
            "Vendor": "Vendor2",
            "Pattern": "vendor2",
            "Tag": "Entertainment",
        }
    ]
    """

    # Declare the new_vendor variable outside the for loop
    new_vendor = None

    # Counter to track what key we're on, so if there's a duplicate, we can hand back the name
    duplicate_vendor_key = -1

    conn = engine.connect()

    # Begin a transaction block
    with session.begin():
        try:
            # Iterate over the input vendors
            for vendor in vendors:
                # Flip the counter to zero, start tracking what key we're on
                duplicate_vendor_key += 1

                # This is so we can do a print statement acknowledging if a vendor was truly added or one was rebranded
                UUID_generated = False

                # Generate a UUID for the vendor if one is not provided
                if "UUID" not in vendor:
                    vendor["UUID"] = str(uuid.uuid4())
                    UUID_generated = True

                # Get the current time
                current_time = datetime.datetime.now().isoformat()

                # Add the current time to the vendor dictionary
                vendor["Initialized"] = current_time

                # Set the new vendor's information to new_vendor
                new_vendor = insert(db.Vendors).values(**vendor)

                # Execute the query to insert the new vendor
                session.execute(new_vendor)

                if UUID_generated == False:
                    print(f"{vendor[0]['Vendor']} rebranded")

            # If all operations are successful, commit the transaction
            session.commit()
            if UUID_generated == True:
                print(f"{vendors[0]['Vendor']} added")

        except exc.IntegrityError:
            # If there's an IntegrityError, roll back the transaction
            session.rollback()
            print(f"{vendors[duplicate_vendor_key]['Vendor']} is a duplicate vendor")
            return
        except Exception as e:
            # If there's any other error, roll back the transaction
            session.rollback()
            print(f"Error from {vendors[duplicate_vendor_key]['Vendor']}: {e}")
            return

        # Update the YAML file with the new vendors' information
        add_vendor_yaml_file(yml_file_path, vendors)

        for vendor in vendors:
            revendorizer(vendor)


def revendorizer(vendor: dict) -> None:
    # Update transactions with "No Vendor Found" with the new vendor's information
    with db.engine.connect() as conn:
        # Find transactions with "No Vendor Found" as the vendor
        no_vendor_found_transactions_query = select([db.Transactions]).where(
            db.Transactions.VendorUUID == "No Vendor Found"
        )

        no_vendor_found_transactions = conn.execute(
            no_vendor_found_transactions_query
        ).fetchall()

        # If the expense name matches the pattern of the current vendor, return the vendor name
        for transaction in no_vendor_found_transactions:
            if re.search(vendor["Pattern"], transaction["Name"]):
                update_vendor_query = (
                    update(db.Transactions)
                    .where(db.Transactions.id == transaction["id"])
                    .values(VendorUUID=vendor["UUID"])
                )
                conn.execute(update_vendor_query)


def update_vendor(
    engine: Engine,
    session: session,
    yml_file_path: str,
    UUID: str,
    new_vendor_name: Optional[str] = None,
    new_pattern: Optional[str] = None,
) -> None:
    """
    Updates the vendor name and/or pattern for the vendor with the given ID in the database.
    This is useful if you mistype or need to update a pattern
    """

    # Start a transaction block
    with session.begin():
        with engine.connect() as conn:
            # Query for the UUID of the vendor with the given ID
            query = select([db.Vendors.UUID]).where(db.Vendors.UUID == UUID)
            result = conn.execute(query).fetchone()
            if result:
                UUID = result[0]
            else:
                print(f"Vendor with UUID {UUID} not found in the database")
                return

            # Build the update query
            update_query = update(db.Vendors).where(db.Vendors.UUID == UUID)
            if new_vendor_name:
                # Update the vendor name if provided
                update_query = update_query.values(Vendor=new_vendor_name)
            if new_pattern:
                # Update the pattern if provided
                update_query = update_query.values(Pattern=new_pattern)
            try:
                conn.execute(update_query)
                print(f"Vendor with UUID {UUID} has been updated in the database")
            except exc.IntegrityError:
                session.rollback()
                print(
                    f"Failed to update vendor with UUID {UUID} in the database: integrity error"
                )
                return
            except Exception as e:
                session.rollback()
                print(f"Failed to update vendor in file: {e}")
                return

            # Update the vendor in the YAML file using the UUID
            try:
                update_vendor_yaml_file(
                    yml_file_path,
                    UUID,
                    new_vendor_name=new_vendor_name,
                    new_pattern=new_pattern,
                )
            except Exception as e:
                session.rollback()
                print(f"Failed to update vendor in file: {e}")
                return

            # If both operations are successful, commit the transaction
            session.commit()


def add_vendor_yaml_file(yml_file_path: str, vendors: List[Dict[str, str]]):
    """
    This is used to make sure that *if* you ever needed to delete your database, you're vendors would live on
    """
    # Check if the YAML file exists
    if not os.path.exists(yml_file_path):
        # If the files does not exist, create an empty list of entries
        yaml_entries = []
    else:
        # If the file exists, read the existing entries from the YAML file
        with open(yml_file_path, "r") as yaml_file:
            yaml_entries = yaml.safe_load(yaml_file)

    # Initialize yaml_entries as an empty list if it does not exist
    yaml_entries = yaml_entries or []

    # Iterate over the input vendors
    for vendor in vendors:
        # Create a dictionary for the entry in the YAML file
        yaml_entry = {
            "UUID": vendor["UUID"],
            "Vendor": vendor["Vendor"],
            "Pattern": vendor["Pattern"],
            "Tag": vendor["Tag"],
            "Initialized": vendor["Initialized"],
        }

        # Add the vendor to the list of vendors
        yaml_entries.append(yaml_entry)

    # Write the vendors to the YAML file
    with open(yml_file_path, "w") as yaml_file:
        yaml.dump(yaml_entries, yaml_file, default_flow_style=False)


def update_vendor_yaml_file(
    yml_file_path: str,
    UUID: str,
    new_vendor_name: Optional[str] = None,
    new_pattern: Optional[str] = None,
) -> None:
    """
    Updates the vendor name and/or pattern for the vendor with the given pattern in the YAML file at the given file path
    This makes sure that if you update a vendor it's applied here so that if you need to delete the db, these changes are saved
    """
    # Load the YAML file
    with open(yml_file_path, "r") as f:
        data = yaml.safe_load(f)

    # Check that data is a list
    if isinstance(data, list):
        # Find the entry with the given UUID
        for entry in data:
            if entry["UUID"] == UUID:
                # Update the vendor name if provided
                if new_vendor_name:
                    entry["Vendor"] = new_vendor_name
                # Update the pattern if provided
                if new_pattern:
                    entry["Pattern"] = new_pattern
                break
    else:
        print(f"Invalid data format: data must be a list of vendor entries")
        return

    # Write the updated data back to the YAML file
    with open(yml_file_path, "w") as f:
        yaml.dump(data, f)
    print(f"Vendor with pattern {UUID} has been updated in file {yml_file_path}")


def load_vendors(vendors) -> None:
    """Initializes a database with patterns to match expenses to vendors"""
    with db.engine.connect() as conn:
        try:
            conn.execute(insert(db.Vendors), vendors)
        except exc.IntegrityError:
            session.rollback()
            print("Vendors are loaded")


def generate_example_data(
    num_rows: int, account_type: str = None, save_path: str = "banking_csvs/"
) -> pd.DataFrame:
    """
    This is used in case someone would like to generate test data before
    """
    # List of names
    names = [
        "COSTCO",
        "TOM THUMB",
        "SCOOTER'S COFFEE",
        "VELVET TACO",
        "NANDOS",
        "Coffee Shop",
        "ATM withdrawl",
        "CVS",
        "CASH APP",
        "Taco Deli",
        "WHATABURG",
        "GEICO",
    ]
    data = []
    month = 1
    day = 1
    for i in range(num_rows):
        if day > 28:
            month += 1
            day = 1
        date = "2022-{:02d}-{:02d}".format(
            month, day
        )  # Generate a date in the format "YYYY-MM-DD"
        transaction = random.choice(
            ["Debit", "Credit"]
        )  # Choose a random transaction type
        name = random.choice(names)  # Choose a random name from the list of names
        memo = "this is test data"  # Set the memo to a fixed string
        amount = round(
            random.uniform(-1000, 0), 2
        )  # Generate a random amount between -1000 and 1000
        data.append(
            {
                "Date": date,
                "Transaction": transaction,
                "Name": name,
                "Memo": memo,
                "Amount": amount,
            }
        )
        day += 1
    test_data = pd.DataFrame(data)

    # Choose a random account type if none was specified
    if account_type is None:
        account_type = random.choice(["Checking", "Credit Card"])

    # Generate a filename for the CSV file using the current date and time and the specified account type
    now = datetime.datetime.now()
    filename = f"TEST DATA: {account_type} - {now.strftime('%Y-%m-%d %H-%M-%S')}.csv"

    # Save the data to default unless otherwise specified
    if save_path == "banking_csvs/":
        # Save the file to the specified location if a save path was provided
        test_data.to_csv(f"{save_path}/{filename}", index=False)
    else:
        # Otherwise, save the file to the current working directory
        test_data.to_csv(filename, index=False)

    return test_data


def main():
    folder_path = "./banking_csvs/"
    engine = create_engine("sqlite:///budget.db")

    # Load bank profiles
    with open("bank_profiles.yml", "r") as bp:
        bank_profiles = yaml.safe_load(bp)

    # Load budget plans
    with open("budget_plans.yml", "r") as budp:
        budget_plans = yaml.safe_load(budp)

    # Load vendors
    with open("vendors.yml", "r") as budp:
        vendors = yaml.safe_load(budp)

    load_vendors(vendors)
    import_transactions(folder_path, bank_profiles, engine)

    check_list = [
        (checks.check_no_duplicates, "Has no duplicates"),
        (checks.check_percentages_add_to_100, "Category percents add to 100"),
        (checks.check_tag_list_match, "All avaliable tags used"),
    ]

    checks.check_budget_plans(budget_plans, check_list)
