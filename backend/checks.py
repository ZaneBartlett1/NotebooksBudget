from sqlalchemy import select

from backend import database as db

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

    with db.engine.connect() as conn:
        # Query the Vendors table for the list of tags
        tag_query = select(db.Vendors.Tag)
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