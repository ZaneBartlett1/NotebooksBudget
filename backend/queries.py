import re

import pandas as pd
from sqlalchemy import select

from backend import database as db

def amount_check(rows: list, id: int) -> bool | str:
    """
    Use this to make sure that when using the create children function,
    the rows sum to the amount of the parent.
    It uses the transaction ID to select the parent.
    Return True if they do, or a string with an error message if they don't.
    """
    with db.engine.connect() as conn:
        # Get the amount of the parent transaction
        parent_query_amount = (select(db.Transactions.Amount)).where(db.Transactions.id == id)
        parent_amount = pd.read_sql(parent_query_amount, conn)
        absolute_parent_amount = float(parent_amount["Amount"].values[0])

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
    with db.engine.connect() as conn:
        # Get the official list of tags from the Vendors table
        tags_query_tag = select(db.Vendors.Tag)
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
    

def vendorizer(name: str) -> str:
    """
    Return the vendor UUID associated with the given expense name.
    If no vendor is found, return "No Vendor Found".
    This is used on import so that we can assign a vendor UUID based on what regex pattern we've assigned in the database
    """
    # Query the Vendors table for the vendor UUID and their corresponding patterns
    vendor_query = select(db.Vendors.UUID, db.Vendors.Pattern)

    # Connect to the database
    with db.engine.connect() as conn:
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

    with db.engine.connect() as conn:
        uuid_to_vendor_query = (select(db.Vendors.Tag, db.Vendors.Initialized)).where(
            db.Vendors.UUID == UUID
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

    with db.engine.connect() as conn:
        uuid_to_vendor_query = (select(db.Vendors.Vendor, db.Vendors.Initialized)).where(
            db.Vendors.UUID == UUID
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
    with db.engine.connect() as conn:
        vendor_to_uuid_query = (select(db.Vendors.UUID)).where(db.Vendors.Vendor == vendor)
        result = conn.execute(vendor_to_uuid_query).fetchone()
        if not result:
            return "Vendor did not match to any in database"
        else:
            return result