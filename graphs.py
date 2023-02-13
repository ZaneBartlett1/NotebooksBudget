from budget import *

import plotly.express as px

with engine.connect() as conn:
    # Pull Transactions table
    pandas_query = select(Transactions)
    tran_table = pd.read_sql(pandas_query, conn)
    # This part looks for transactions that have children transactions, removes them, and the concatenates the children rows on
    tran_table = tran_table[tran_table["Has Child"] != None]
    tran_table["Tag"] = tran_table["VendorUUID"].apply(uuid_to_tag)
    columns = [
        ChildTransactions.id,
        ChildTransactions.Date,
        ChildTransactions.Transaction,
        ChildTransactions.Name,
        ChildTransactions.Memo,
        ChildTransactions.Amount,
        ChildTransactions.VendorUUID,
    ]
    child_query = select(columns).select_from(ChildTransactions)
    child_table = pd.read_sql(child_query, engine)
    child_table["Tag"] = child_table["VendorUUID"].apply(uuid_to_tag)
    tran_table = pd.concat([tran_table, child_table], ignore_index=True)
    # Add columns for time
    tran_table["Date"] = pd.to_datetime(tran_table["Date"], infer_datetime_format=True)
    tran_table["Year"] = pd.DatetimeIndex(tran_table["Date"]).year
    tran_table["Month"] = tran_table["Date"].dt.to_period("M").dt.strftime("%Y-%m")
    tran_table["Quarter"] = tran_table["Date"].dt.to_period("Q").dt.strftime("%Y-%q")
    
    # Pull Vendors, also do vendor_list in a cell in the notebook to get a list of vendors
    vendor_query = select(Vendors)
    vendor_list = pd.read_sql(vendor_query, conn).sort_values(by="Vendor")

    # Do tag_list in a cell in the notebook to get a list of tags
    tag_array = vendor_list['Tag'].unique()
    tag_list = pd.DataFrame(tag_array, columns = ['Tags']).sort_values(by='Tags')


def graph_one(
    group_by: str, filter_year: str, filter_month: str, width: int, height: int, invert: bool = False
):
    """
    Example use: graph_one(group_by='Month', filter_year='2022', filter_month='01', height=500, width=1200)
    This is used for just seeing a grouping of tagged expenses by either month or quarter, starting from the filtered year and month
    """
    # Create a filter for the transactions dataframe
    tran_table_filter = (
        (tran_table["Tag"] != "Internal Transfer")  # exclude "Internal Transfer" transactions
        & (tran_table["Date"] >= f"{filter_year}-{filter_month}-01")  # include transactions with a Date >= the specified year and month
        & (tran_table["Amount"] < int(0))  # include transactions with negative Amounts
    )
    
    # Apply the filter to the transactions dataframe to create a new dataframe
    new_tran_table = tran_table[tran_table_filter]
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate chart with")
        return None
    # Group the new dataframe by the specified group_by column and the "Tag" column
    # and sum the "Amount" column to create a new dataframe
    expense_table_tags = new_tran_table.groupby(
        [group_by, "Tag"], as_index=False
    ).Amount.sum()

    # Invert the amount if the invert option is set to True
    if invert:
        expense_table_tags["Amount"] *= -1

    # Create a bar graph using the new dataframe
    # with the specified group_by column on the x-axis,
    # the "Amount" column on the y-axis,
    # and the "Tag" column for the color of the bars
    # with the specified width and height
    expense_graph = px.bar(
        expense_table_tags,
        x=group_by,
        y="Amount",
        color="Tag",
        width=width,
        height=height,
    )
    expense_graph.show()

def graph_two(
    group_by: str, filter_year: str, filter_month: str, width: int, height: int, invert: bool = False
):
    """
    This graph is very similar to graph_one, but will show a line for each individual expense
    """
    # Filter the transaction table to exclude internal transfers and transactions from before the specified year and month
    tran_table_filter = (
        (tran_table["Tag"] != "Internal Transfer")
        & (tran_table["Date"] >= f"{filter_year}-{filter_month}-01")
        & (tran_table["Amount"] < int(0))
    )
    new_tran_table = tran_table[tran_table_filter]
    
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate chart with")
        return None
    
    new_tran_table["Vendor"] = new_tran_table["VendorUUID"].apply(uuid_to_vendor)
        
    # Group the transactions by the specified group, tag, and vendor and sum their amounts
    expense_table_vendors = new_tran_table.groupby(
        [group_by, "Tag", "Vendor"], as_index=False
    ).Amount.sum()
    
    if invert:
        expense_table_tags["Amount"] *= -1
    
    # Create a bar graph of the grouped transactions
    expense_graph = px.bar(
        expense_table_vendors,
        x=group_by,
        y="Amount",
        color="Tag",
        hover_data=["Vendor"],
        width=width,
        height=height,
    )
    expense_graph.show()


def graph_three(
    filter_year: str, filter_month: str, width: int, height: int, budget_plan: str, Salary: int, invert: bool = False
):
    """
    The graph for this is basically a level up from graph one, where using the budget_plans file, groups your tags into categories.
    It also gives overview information about other things like your monthly income, spending, the amount left after that,
    how much you still need to spend on required expenses, like savings, and how much you have left after that.
    """
    # Load budget plans from budget_plans.yml
    with open("budget_plans.yml", "r") as budp:
        budget_plans = yaml.safe_load(budp)

    # Filter transactions that are not internal transfers and are from the specified year and month
    tran_table_filter = (
        (tran_table["Tag"] != "Internal Transfer")
        & (tran_table["Date"] >= f"{filter_year}-{filter_month}-01")
        & (tran_table["Date"] <= f"{filter_year}-{filter_month}-{calendar.monthrange(int(filter_year), int(filter_month))[1]}")
        & (tran_table["Amount"] < int(0))
    )
    # Run query filter
    new_tran_table = tran_table[tran_table_filter]
    
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate chart with")
        return None
        
    # Add a new column "Category" to the new transaction table by applying the category_from_tag function to each row
    new_tran_table["Category"] = new_tran_table.apply(lambda row: category_from_tag(budget_plans[budget_plan], row), axis=1)
    # Add a new column "Required" to the new transaction table by checking whether the category has a true value for required in the dictionary
    new_tran_table["Required"] = new_tran_table.apply(
        lambda row: budget_plans[budget_plan][row["Category"]]["required"] if row["Category"] in budget_plans[budget_plan] else False, axis=1
    )
    # Group the transactions by their Category and Tag, and sum up their amounts
    expense_table_vendors = new_tran_table.groupby(["Category", "Tag"], as_index=False).Amount.sum()
    
    
    # Group the transactions by their category and sum up their amounts
    expense_table_categories_sum = new_tran_table.groupby("Category")["Amount"].sum().to_dict()
    # Get the total sum of all expenses from all categories
    total_expenses = sum(expense_table_categories_sum.values())
    # Get the sum of all rows that equal required on the new transaction table
    required_sum_paid = new_tran_table[new_tran_table["Required"] == True]["Amount"].sum()
    # Get the sum of the amount to be paid against categories that are required
    required_sum_owed = (calculate_sum(budget_plans[budget_plan], Salary)/12)
    print(f"Monthly income: {round((Salary/12), 2)}, Monthly Expenses so far: {round((total_expenses), 2)}\n\
Income-Expenses: {round(((Salary/12)+total_expenses), 2)}, Required Spending Left: {round((required_sum_owed + required_sum_paid), 2)}.\n\
Left and not allocated to required: {round((((Salary/12)+total_expenses) - (required_sum_owed + required_sum_paid)), 2)}")
        
    # give output for amount of spend left for each category
    categories_max_spend_dict = category_max_spend(budget_plans[budget_plan], Salary)
    print("Below is information about each category")
    for category in categories_max_spend_dict:
        max_spend = categories_max_spend_dict[category]["max spend"]
        if category not in expense_table_categories_sum:
            if budget_plans[budget_plan][category]['type'] == 'savings':
                print(f"{category} Category: This is set as a saving category with no contribution made yet, {round((max_spend/12), 2)} to go")
            elif budget_plans[budget_plan][category]['type'] == 'hard_limit':
                print(f"{category} Category: This is set as a hard limit category, just keep monthly expenses below {round((max_spend/12), 2)}")
            elif budget_plans[budget_plan][category]['type'] == 'free_spend':
                print(f"{category} Category: This is set as a free spending category, you have {round((max_spend/12), 2)} left to spend")
        else:
            amount_left = round(((max_spend/12) + expense_table_categories_sum[category]), 2)
            if (budget_plans[budget_plan][category]['type'] == 'savings') & (amount_left > 0):
                print(f"{category} Category: Looks like you've made some progress, {amount_left} to go")
            elif (budget_plans[budget_plan][category]['type'] == 'savings') & (amount_left <= 0):
                print(f"{category} Category: Damnnnnn you killing it, and you're {amount_left} over the amount to save this month")
            elif (budget_plans[budget_plan][category]['type'] == 'hard_limit') & (amount_left >= 0):
                print(f"{category} Category: This is set as a hard limit category, just keep monthly expenses below {amount_left}")
            elif (budget_plans[budget_plan][category]['type'] == 'hard_limit') & (amount_left < 0):
                print(f"{category} Category: You're over your hard limit by {amount_left}, you honestly probably need to rethink the budget")
            elif (budget_plans[budget_plan][category]['type'] == 'free_spend') & (amount_left >= 0):
                print(f"{category} Category: This is set as a free spending category, you have {amount_left} left to spend")
            elif (budget_plans[budget_plan][category]['type'] == 'free_spend') & (amount_left < 0):
                print(f"{category} Category: This is set as a free spending category, you have {amount_left} left to spend")
                
    if invert:
        expense_table_vendors["Amount"] *= -1
    
    # Create a bar chart using plotly express, with the x-axis being the Category, the y-axis being the Amount, and the color being the Tag
    expense_graph = px.bar(
        expense_table_vendors,
        x="Category",
        y="Amount",
        color="Tag",
        hover_data=["Tag"],
        width=width,
        height=height,
        title=f'Expenses for the month, grouped by category. Using the {budget_plan}',
    )

    # Show the bar chart
    expense_graph.show()
    
    
def graph_four(
    filter_year: str, filter_month: str, width: int, height: int, invert: bool = False
):
    """
    Sum grouped by tag for a given year
    """
    
    eoy = str(int(filter_year)+1)

    
    # Filter the transaction table to exclude internal transfers and transactions from before the specified year and month
    tran_table_filter = (
        (tran_table["Tag"] != "Internal Transfer")
        & (tran_table["Date"] >= f"{filter_year}-{filter_month}-01")
        & (tran_table["Date"] <= f"{eoy}-{filter_month}-01")
        & (tran_table["Amount"] < int(0))
    )
    new_tran_table = tran_table[tran_table_filter]
    
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate chart with")
        return None
    
    new_tran_table["Vendor"] = new_tran_table["VendorUUID"].apply(uuid_to_vendor)
        
    # Group the transactions by the specified group, tag, and vendor and sum their amounts
    expense_table_vendors = new_tran_table.groupby(
        ["Tag", "Vendor"], as_index=False
    ).Amount.sum().sort_values(by="Amount")
    
    if invert:
        expense_table_vendors["Amount"] *= -1
    
    # Create a bar graph of the grouped transactions
    expense_graph = px.bar(
        expense_table_vendors,
        x="Tag",
        y="Amount",
        hover_data=["Vendor"],
        color="Vendor",
        width=width,
        height=height,
    )
    expense_graph.show()
    
    
def graph_five(
    filter_year: str, filter_month: str, width: int, height: int, invert: bool = False
):
    """
    Example use: graph_one(group_by='Month', filter_year='2022', filter_month='01', height=500, width=1200)
    This is used for just seeing a grouping of tagged expenses by either month or quarter, starting from the filtered year and month
    """
    
    eoy = str(int(filter_year)+1)
    
    # Create a filter for the transactions dataframe
    tran_table_filter = (
        (tran_table["Tag"] != "Internal Transfer")
        & (tran_table["Tag"] == "Vendor w/o default Tag")
        & (tran_table["Date"] >= f"{filter_year}-{filter_month}-01")
        & (tran_table["Date"] <= f"{eoy}-{filter_month}-01")
        & (tran_table["Amount"] < int(0))
    )
    
    # Apply the filter to the transactions dataframe to create a new dataframe
    new_tran_table = tran_table[tran_table_filter]
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate chart with")
        return None
    
    new_tran_table["Vendor"] = new_tran_table["VendorUUID"].apply(uuid_to_vendor)    

    # Invert the amount if the invert option is set to True
    if invert:
        new_tran_table["Amount"] *= -1
        
    # Group the new dataframe
    expense_table_vendors = new_tran_table.groupby(
        ["Vendor", "Amount", "Name"], as_index=False
    ).Amount.sum().sort_values(by="Amount", ascending=False)    
    
    # Create a bar graph using the new dataframe
    expense_graph = px.bar(
        expense_table_vendors,
        x="Vendor",
        y="Amount",
        color="Vendor",
        hover_data=["Vendor", "Name"],
        width=width,
        height=height,
    )
    expense_graph.show()


def pt_one(filter_tag: str, filter_month: Optional[int] = None, head: Optional[int] = 15):
    """This sorts by amount so you'll most use this to look at things like the highest expenses for vendors without tags"""
    
    if filter_month != None:
        # Create filter from signature, and also only look at negative numbers
        filter_tran_table = (
            (tran_table["Month"] == filter_month)
            & (tran_table["Tag"] == filter_tag)
            & (tran_table["Amount"] < int(0))
        )
    else:
        # Create filter from signature, and also only look at negative numbers
        filter_tran_table = (
            (tran_table["Tag"] == filter_tag)
            & (tran_table["Amount"] < int(0))
        )
        
    
    # Apply the filter
    new_tran_table = tran_table[filter_tran_table]
    
    if new_tran_table.empty:
        print("The dataframe is empty. Nothing to populate pivot table with")
        return None
    
    # Use the `uuid_to_vendor()` function to convert the VendorUUID column to the Vendor column
    new_tran_table["Vendor"] = new_tran_table["VendorUUID"].apply(uuid_to_vendor)
    
    newer_tran_table = pd.pivot_table(new_tran_table, index=["Vendor", "Name", "id", "Date"])
    return newer_tran_table.sort_values(by="Amount").head(head)
