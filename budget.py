import re
import csv
import hashlib
import datetime
import time
import os
import uuid
import sys
import random
import calendar
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
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
import pandas as pd
import yaml


folder_path = "./banking_csvs/"
db_path = "budget.db"
yml_file_path = "./vendors.yml"
engine = create_engine("sqlite:///budget.db")
Base = declarative_base()


class Transactions(Base):
    __tablename__ = "Transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Date = Column(String)
    Transaction = Column(String)
    Name = Column(String)
    Memo = Column(String)
    Amount = Column(Float)
    VendorUUID = Column(String)
    Has_Child = Column("Has Child", String)
    Hash = Column(String, unique=True)


class ChildTransactions(Base):
    __tablename__ = "Child Transactions"

    id = Column(Integer, primary_key=True)
    Parent_id = Column(Integer, ForeignKey("Transactions.id"))
    Date = Column(String)
    Transaction = Column(String)
    Name = Column(String)
    Memo = Column(String)
    Amount = Column(Float)
    VendorUUID = Column(String)
    Tag = Column(String)
    Initialized = Column(String)
    Description = Column(String)


class BudgetTemplates(Base):
    __tablename__ = "Budget Templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Budget_Name = Column("Budget Name", String)
    Buckets = Column(String, unique=True)
    Percent = Column(Float)


class BankTemplates(Base):
    __tablename__ = "Bank Templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Bank_Name = Column("Bank Name", String)
    Row_Number = Column("Row Number", Integer)
    Column_Name = Column("Column Name", String)
    Match_To = Column("Match To", String)


class Vendors(Base):
    __tablename__ = "Vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Vendor = Column(String, unique=True)
    Pattern = Column(String)
    Tag = Column(String)
    UUID = Column(String)
    Initialized = Column(String)


class ExpenseImports(Base):
    __tablename__ = "Expense Imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Filename = Column(String, unique=True)


Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()


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
                VendorUUID = vendorizer(Name)
                row = insert(Transactions).values(
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
    expense_import = insert(ExpenseImports).values(Filename=name)
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
        if (amount_check(rows, id)) and (tag_check(rows)) == True:
            # If they do, iterate over the rows
            for row in rows:
                # Get the parent transaction's information
                parent_query = (
                    select(
                        Transactions.Date,
                        Transactions.Transaction,
                        Transactions.Name,
                        Transactions.Memo,
                    )
                ).where(Transactions.id == id)
                parent_columns = pd.read_sql(parent_query, conn)
                parent_id = id
                date = parent_columns["Date"].values[0]  # type: ignore
                transaction = parent_columns["Transaction"].values[0]  # type: ignore
                name = parent_columns["Name"].values[0]  # type: ignore
                memo = parent_columns["Memo"].values[0]  # type: ignore

                # Get the information for the current row
                amount = row[0]
                vendor_uuid = vendor_to_uuid(row[1])
                tag = row[2]
                desc = row[3]

                # Used to show when the child transaction was initialized
                current_time = datetime.datetime.now().isoformat()

                # Insert the current row into the ChildTransactions table
                row = insert(ChildTransactions).values(
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
                        update(Transactions)
                        .where(Transactions.id == id)
                        .values(Has_Child="True")
                    )
                    conn.execute(label_parent)
        else:
            # If the checks fail, return the output of amount_check and tag_check
            print(
                f"amount_check: {amount_check(rows, id)}, tag_check: {tag_check(rows)}"
            )


def amount_check(rows: list, id: int) -> bool | str:
    """
    Use this to make sure that when using the create children function,
    the rows sum to the amount of the parent.
    It uses the transaction ID to select the parent.
    Return True if they do, or a string with an error message if they don't.
    """
    with engine.connect() as conn:
        # Get the amount of the parent transaction
        parent_query_amount = (select(Transactions.Amount)).where(Transactions.id == id)
        parent_amount = pd.read_sql(parent_query_amount, conn)
        absolute_parent_amount = float(parent_amount["Amount"].values[0])  # type: ignore

        # Get the amounts of the child transactions from the given rows
        child_list_amounts = [float(row[0]) for row in rows]

        # Calculate the sum of the amounts of the child transactions
        absolute_child_amount = float(sum(child_list_amounts))

        # Calculate the difference between the parent transaction's amount and the sum of the child transactions' amounts
        diff_amount = absolute_child_amount - absolute_parent_amount

        # Check if the difference is zero
        if diff_amount == 0:
            # If it is, return True
            return True
        else:
            # If it isn't, return an error message
            return f"Amount doesn't add up. Absolute Parent Amount: {absolute_parent_amount}, Absolute Child Amount: {absolute_child_amount}"


def tag_check(rows: list) -> bool | str:
    """
    Check that the tags used in the given rows are present in the official list of tags stored in the Vendors table.
    Return True if they are, or a string with an error message if they aren't.
    Used to make sure that when using the making children function you don't put in a tag that doesn't exist
    """
    with engine.connect() as conn:
        # Get the official list of tags from the Vendors table
        tags_query_tag = select(Vendors.Tag)
        raw_tags_tag = pd.read_sql(tags_query_tag, conn)
        tags_tag = raw_tags_tag["Tag"].to_list()

        # Get the tags from the given rows
        child_tags = [row[2] for row in rows]

        # Check if each tag in the given rows is present in the official list of tags
        for tag in child_tags:
            if tag not in tags_tag:
                # If not, return an error message
                return f"One of these {child_tags} is not an official tag. Check spelling or add tag to official tag first"

        # If all tags in the given rows are present in the official list of tags, return True
        return True


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
    imported_files_query = select(ExpenseImports.Filename)

    # Create an empty list to store the paths of the new files
    new_file_paths = []

    # Connect to the database
    with engine.connect() as conn:
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


def vendorizer(name: str) -> str:
    """
    Return the vendor UUID associated with the given expense name.
    If no vendor is found, return "No Vendor Found".
    This is used on import so that we can assign a vendor UUID based on what regex pattern we've assigned in the database
    """
    # Query the Vendors table for the vendor UUID and their corresponding patterns
    vendor_query = select(Vendors.UUID, Vendors.Pattern)

    # Connect to the database
    with engine.connect() as conn:
        # Fetch the results of the query as a list of tuples
        updated_vendor_list = conn.execute(vendor_query).fetchall()

        # Convert the list of tuples to a dictionary
        dict_vendor_pattern = {}

        # Iterate over the updated_vendor_list
        for vendor in updated_vendor_list:
            # Get the vendor UUID and pattern from the current element
            vendor_uuid = vendor["UUID"]
            vendor_pattern = vendor["Pattern"]

            # Add the vendor UUID and pattern to the dictionary
            dict_vendor_pattern[vendor_uuid] = {
                "Pattern": vendor_pattern,
            }

        # Iterate over the dictionary
        for vendor in dict_vendor_pattern:
            # If the expense name matches the pattern of the current vendor, return the vendor UUID
            if re.search(dict_vendor_pattern[vendor]["Pattern"], name):
                return vendor

        # If no vendor is found, return "No Vendor Found"
        return "No Vendor Found"


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
                new_vendor = insert(Vendors).values(**vendor)

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
    with engine.connect() as conn:
        # Find transactions with "No Vendor Found" as the vendor
        no_vendor_found_transactions_query = select([Transactions]).where(
            Transactions.VendorUUID == "No Vendor Found"
        )

        no_vendor_found_transactions = conn.execute(
            no_vendor_found_transactions_query
        ).fetchall()

        # If the expense name matches the pattern of the current vendor, return the vendor name
        for transaction in no_vendor_found_transactions:
            if re.search(vendor["Pattern"], transaction["Name"]):
                update_vendor_query = (
                    update(Transactions)
                    .where(Transactions.id == transaction["id"])
                    .values(VendorUUID=vendor["UUID"])
                )
                conn.execute(update_vendor_query)


def update_vendor(
    engine: Engine,
    session: Session,  # type: ignore
    yml_file_path: str,
    UUID: str,
    new_vendor_name: Optional[str] = None,
    new_pattern: Optional[str] = None
) -> None:
    """
    Updates the vendor name and/or pattern for the vendor with the given ID in the database.
    This is useful if you mistype or need to update a pattern
    """

    # Start a transaction block
    with session.begin():
        with engine.connect() as conn:
            # Query for the UUID of the vendor with the given ID
            query = select([Vendors.UUID]).where(Vendors.UUID == UUID)
            result = conn.execute(query).fetchone()
            if result:
                UUID = result[0]
            else:
                print(f"Vendor with UUID {UUID} not found in the database")
                return

            # Build the update query
            update_query = update(Vendors).where(Vendors.UUID == UUID)
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


def uuid_to_tag(UUID: str) -> str:
    """
    Using this since we don't store vendor names directly on the transaction table.
    So when we need to get the most recent vendor name, we do it based on the UUID.
    This function is just a basic lookup and return
    """
    # Check if the UUID is "No Vendor Found"
    if UUID == "No Vendor Found":
        # If it is, simply return "No Vendor Found"
        return "No Vendor Found"

    with engine.connect() as conn:
        uuid_to_vendor_query = (select(Vendors.Tag, Vendors.Initialized)).where(
            Vendors.UUID == UUID
        )
        result = conn.execute(uuid_to_vendor_query).fetchall()

        # Pick the most recently added vendor
        most_recent_vendor = None
        most_recent_timestamp = None
        for vendor in result:
            # Check if the current vendor has a more recent timestamp than the previous ones
            if not most_recent_timestamp or vendor.Initialized > most_recent_timestamp:
                most_recent_vendor = vendor
                most_recent_timestamp = vendor.Initialized

        # Check if the most recent vendor was found
        if most_recent_vendor:
            return most_recent_vendor.Tag
        else:
            return "No Vendor Found"


def uuid_to_vendor(UUID: str) -> str:
    """
    Using this since we don't store vendor names directly on the transaction table.
    So when we need to get the most recent vendor name, we do it based on the UUID.
    This function is just a basic lookup and return
    """
    # Check if the UUID is "No Vendor Found"
    if UUID == "No Vendor Found":
        # If it is, simply return "No Vendor Found"
        return "No Vendor Found"

    with engine.connect() as conn:
        uuid_to_vendor_query = (select(Vendors.Vendor, Vendors.Initialized)).where(
            Vendors.UUID == UUID
        )
        result = conn.execute(uuid_to_vendor_query).fetchall()

        # Pick the most recently added vendor
        most_recent_vendor = None
        most_recent_timestamp = None
        for vendor in result:
            # Check if the current vendor has a more recent timestamp than the previous ones
            if not most_recent_timestamp or vendor.Initialized > most_recent_timestamp:
                most_recent_vendor = vendor
                most_recent_timestamp = vendor.Initialized

        # Check if the most recent vendor was found
        if most_recent_vendor:
            return most_recent_vendor.Vendor
        else:
            return "No Vendor Found"


def vendor_to_uuid(vendor: str) -> str:
    """
    Useful if you need to do something like rebrand a vendor, since you need to give the UUID. Simple query.
    """
    with engine.connect() as conn:
        vendor_to_uuid_query = (select(Vendors.UUID)).where(Vendors.Vendor == vendor)
        result = conn.execute(vendor_to_uuid_query).fetchone()
        if not result:
            return "Vendor did not match to any in database"
        else:
            return result


def get_tags_for_budget_plan(budget_plan: dict) -> list:
    """
    Returns all tags for a specified budget plan.
    There's a check that runs which uses this function to make sure there's no duplicates
    """
    # Keep track of category to vendor map
    categories = []

    # Give a flatter mapping of category to tags
    for category in budget_plan:
        tags = budget_plan[category]["tags"]
        if tags:
            categories.extend(tags)

    return categories


def get_budget_plan_tag_mapping(budget_plans: dict) -> dict:
    """
    Get a dictionary of all tags, regardless of category, for each budget plan

    Shaped like:
    {'plan' : [tag_1, tag_2, ..., tag_n]}
    This is used in a check to make sure there's no duplicates
    """
    plan_to_tag_map = {}
    for budget_plan in budget_plans:
        budget_plan_dict = budget_plans[budget_plan]

        # e.g. plan_to_tag_map['50/30/20_rule'] = {fifty: {...}, thirty: {...}
        tags_for_budget_plan = get_tags_for_budget_plan(budget_plan_dict)
        plan_to_tag_map[budget_plan] = tags_for_budget_plan

    return plan_to_tag_map


def check_no_duplicates(budget_plans: dict):
    """Used to check that there is no duplicate tags under any category for the budget plan"""
    # Get mapping of budget plans to all tags, regardless of category
    plan_to_tags = get_budget_plan_tag_mapping(budget_plans)

    failures = []
    pass_check = True

    for plan in plan_to_tags:
        # Get the tag list for this plan
        tag_list = plan_to_tags[plan]
        if len(tag_list) != len(set(tag_list)):
            failures.append(plan)
            pass_check = False

    return pass_check, failures


def check_tag_list_match(budget_plans: dict):
    """
    Check that the list of tags used in the budget plans matches the list of tags in the database.
    Returns a tuple containing a boolean indicating if the check passed and a list of plans that failed the check.
    """
    # Get a dictionary mapping budget plans to their corresponding tags
    plan_to_tags = get_budget_plan_tag_mapping(budget_plans)

    failures = {}
    db_tag_list_unique = []

    with engine.connect() as conn:
        # Query the Vendors table for the list of tags
        tag_query = select(Vendors.Tag)
        db_tag_list = set(conn.execute(tag_query).fetchall())

        # Iterate over the list of tags and add each tag to the list of unique tags
        for tag in db_tag_list:
            db_tag_list_unique.append(tag[0])

    # Initialize a variable to track if the check passed
    pass_check = True

    # Iterate over the dictionary of plan to tags mappings
    for plan in plan_to_tags:
        # Get the tag list for this plan
        tag_list = plan_to_tags[plan]
        # Transactions that couldn't find a vendor, will have "No Vendor Found" marked on them
        # remove this since the Vendor table doesn't (and shouldn't) have that as an entry
        try:
            tag_list.remove("No Vendor Found")
        except ValueError:
            pass
        # Check if the tag list for this plan is a unique, sorted list of all the tags in the database
        if sorted(tag_list) != sorted(list(set(db_tag_list_unique))):
            # If the check failed, add the plan to the list of failures and set pass_check to False
            failures[plan] = set(tag_list) ^ set(db_tag_list_unique)
            pass_check = False

    # Return a tuple containing a boolean indicating if the check passed and a list of plans that failed the check
    return pass_check, failures


def check_percentages_add_to_100(budget_plans: dict) -> tuple:
    """
    Run during main to check that each budget plan inside the budget plans yaml file have categories that add to 100%
    """
    # initialize variables
    pass_check = True
    failures = []

    # iterate over budget plans
    for plan in budget_plans:
        percent = 0
        budget_plan = budget_plans[plan]

        # iterate over categories in budget plan
        for category_name in budget_plan:
            percent += budget_plan[category_name]["percentage"]

        # if percentages don't add up to 100, set pass_check to False and append plan to failures list
        if percent != 100:
            pass_check = False
            failures.append(plan)

    # return tuple of pass_check and failures
    return pass_check, failures


def check_budget_plans(budget_plans: dict, check_list: list) -> dict:
    """
    Function used to apply other check functions run during main. These make sure several different things look good
    """
    # Initialize an empty dictionary to store the results of the check functions
    check_results = {}

    print("Below are checks that are run against your budget plan")

    # Iterate over the check_list
    for check in check_list:
        # Call the function in the check tuple with budget_plans as an argument and store the result in result
        result, fail_dict = check[0](budget_plans)
        # Get the rule description from the check tuple
        rule = check[1]
        # If the result of the check function is True, print a message indicating that all budget plans passed the check
        if result:
            print(f"{rule}: All PASSED")
        # If the result of the check function is False, print a message indicating that some budget plans failed the check
        # and add the fail_list to the check_results dictionary using the rule as the key
        else:
            print(f"{rule}: FAILING:", end=" ")
            fail_list_str = [f"{k}: {v}" for k, v in fail_dict.items()]
            print(", ".join(fail_list_str))

    # Return the check_results dictionary
    return check_results


def category_from_tag(budget_plan: dict, row) -> str:
    """
    Used for graphs to apply category based on the budget plan provided and tag already on transaction
    """
    # create dictionary that maps categories to their tags
    categories_tag_dict = {}

    for category in budget_plan:
        tags = budget_plan[category]["tags"]
        if tags:
            categories_tag_dict[category] = tags

    # iterate over dictionary and return category if transaction tag matches a tag in the budget plan
    for key, values in categories_tag_dict.items():
        for tag in values:
            if tag == row["Tag"]:
                return key
    # return "Failed to categorize" if transaction cannot be categorized
    else:
        return "Failed to categorize"


def category_max_spend(budget_plan: dict, Salary: int) -> dict | None:
    """
    Given a budget plan and Salary, return a dictonary with the category name, the percentage allocated for that category, and the max spend for that category
    """
    categories_max_spend_dict = {}

    for category in budget_plan:
        max_spend_percentage = budget_plan[category]["percentage"]
        if max_spend_percentage:
            categories_max_spend_dict[category] = {
                "percentage": max_spend_percentage,
                "max spend": Salary / (100 / max_spend_percentage),
            }

    return categories_max_spend_dict


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
    with engine.connect() as conn:
        try:
            conn.execute(insert(Vendors), vendors)
        except exc.IntegrityError:
            session.rollback()
            print("Vendors are loaded")


def calculate_sum(dictionary, salary):
    sum = 0
    for key in dictionary:
        if dictionary[key]["required"] == True:
            sum += dictionary[key]["percentage"] * salary / 100
    return sum


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
        (check_no_duplicates, "Has no duplicates"),
        (check_percentages_add_to_100, "Category percents add to 100"),
        (check_tag_list_match, "All avaliable tags used"),
    ]

    check_budget_plans(budget_plans, check_list)
