# Budgeting

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About the project</a></li>
    <li>
      <a href="#features">Features</a>
      <ul>
        <li><a href="#generate-fake-data-to-test">Generate fake data to test</a></li>
        <li><a href="#concatenate-files-from-multiple-accounts">Concatenate files from multiple accounts</a></li>
        <li><a href="#checks-to-see-if-new-csvs-have-been-added-to-save-time-loading">Checks to see if new csvs have been added to save time loading</a></li>
        <li><a href="#define-your-banks-csv-profile-so-that-any-bank-should-work">Define your bank's csv profile, so that any bank should work</a></li>
        <li><a href="#identify-and-automatically-remove-duplicate-expenses">Identify and automatically remove duplicate expenses</a></li>
        <li><a href="#use-regex-patterns-to-match-vendors-and-assign-a-tag-to-each-vendor">Use regex patterns to match vendors and assign a tag to each vendor</a></li>
        <li><a href="#create-budget-with-yaml-files-and-use-tags-to-group-vendors-in-categories">Create budget with yaml files and use tags to group vendors in categories</a></li>
        <li><a href="#checks-are-automatically-run-against-budgets">Checks are automatically run against budgets</a></li>
        <li><a href="#premade-graphs-for-understanding-your-spending">Premade graphs for understanding your spending</a></li>
        <li><a href="#add-vendors-and-update-them-to-match-if-they-rebrand">Add vendors, and update them to match if they rebrand</a></li>
        <li><a href="#split-transactions-to-handle-situations-like-buying-from-amazon-but-wanting-the-expense-to-go-to-multiple-tags">Split transactions to handle situations like buying from Amazon but wanting the expense to go to multiple tags</a></li>
      </ul>
    </li>
    <li><a href="#why-make-this">Why make this?</a></li>
    <li><a href="#setting-up">Setting up</a></li>
    <li><a href="#using-it">Using it</a></li>
    <li><a href="#some-notes">Some Notes</a></li>
  </ol>
</details>



## About the project

This is a budgeting app designed for tracking and management of monthly or quarterly budgets. Features include vendor identification, tagging and categorization, budget creation, and the auto-generation of charts for visual representation.

This is a good medium between using something a spreadsheet tool like google sheets and GNUCash, this budgeting tool focuses primarily on assisting users in achieving their financial goals within specific spending categories. For optimal results, I recommend only using this tool withonly one or two primary expense accounts.

## Features

### Generate fake data to test

[Screencast from 05-17-2023 01:41:47 PM.webm](https://github.com/ZaneBartlett1/NotebooksBudget/assets/85081861/8339dd0a-6988-49f7-9917-dd4a6fb50248)

### Concatenate files from multiple accounts

![image](https://user-images.githubusercontent.com/85081861/208593581-258006b9-aa19-44d0-a632-90fda28dad0a.png)


### Checks to see if new csvs have been added to save time loading

![image](https://user-images.githubusercontent.com/85081861/208598919-df8b6565-4519-44a1-a384-5a3d35397df6.png)


### Define your bank's csv profile, so that any bank should work

![image](https://user-images.githubusercontent.com/85081861/208593809-62bbe593-99b2-4085-859b-a8bc071cec9a.png)

![image](https://user-images.githubusercontent.com/85081861/208594312-96f2f6d5-b94c-4f44-8f2a-057ebcc234e0.png)


### Identify and automatically remove duplicate expenses

![image](https://user-images.githubusercontent.com/85081861/208594423-74a61bc7-c859-41d5-9dd6-b59a266bc7c3.png)


### Use regex patterns to match vendors and assign a tag to each vendor

![image](https://user-images.githubusercontent.com/85081861/208594735-fcc51ffb-cbad-4627-b2a3-1c0278270b9b.png)


### create budget with yaml files and use tags to group vendors in categories
  * Each budget has a name, with categories that make it up. 
  * In each category
    * You define the percentage of your salary that goes to this category
    * If the category is a "required" category (meaning instead of being a limit, is it a category that you need to meet the percentage you set for it. Like a savings category, for example)
    * The type of category, which is mostly a UX thing for how information about the category is printed. Two categories might be required, but you want a savings category to say things "Good job for hitting your goal!" vs a category where you shouldn't be going over saying something like "It looks like you might be spending too much and need to cut down!".
    * Then the tags under that category. You might have a category that you put track all your non-required expenses and put things like eating out and related non-essential things.

![image](https://user-images.githubusercontent.com/85081861/208595520-d2759f42-f6d4-4642-bc3f-b3e6479a9f62.png)


### Checks are automatically run against budgets

![image](https://user-images.githubusercontent.com/85081861/208598987-35b3f514-92de-48e4-b61b-e8efac4be2ea.png)

### Premade graphs for understanding your spending

![image](https://user-images.githubusercontent.com/85081861/208599604-07a887af-f7ba-491d-baeb-c55d75a7106d.png)
![image](https://user-images.githubusercontent.com/85081861/208599648-edb2cdb1-58d8-41b8-bb4b-aad6365017e5.png)

  
  Plug in your salary (after taxes) to get basic information out about how much spending you have left in a given category for your budget

![image](https://user-images.githubusercontent.com/85081861/208605209-fb8c8c90-2a0a-45d3-a3ff-570c150f0416.png)

### Add vendors, and update them to match if they rebrand
### Split transactions to handle situations like buying from Amazon but wanting the expense to go to multiple tags

## Why make this?
* I did this mostly because I wanted a very simple budgeting app and couldn't find one. I mostly just wanted to tag and group my transactions then compare that to an ideal. Doing it in LibreOffice (I actually used Google Sheets, the horror!) was a pain, while it seemed like if I was going to learn GNUCash I may as well just make my own thing. So I made my own thing!

## Setting up
* Clone the repo
* Create virtenv and activate
* Download requirements
* Drop however many csvs from your bank in that folder
* Start jupyter lab
* On the AnalyticsAndCRUD, run the init cells to get the CSVs loaded into the database
* On the AnalyticsAndCRUD, run workflow cells to go through different defined processes for figuring out and budgeting expenses

![image](https://user-images.githubusercontent.com/85081861/208600026-892dc104-5d23-4fd8-9f57-d5f6d4c4c04f.png)


## Using it
Generally the workflows are what you'd be using. There are three workflows at the time of writing. While they are written in order at the current time of writing, the titles are what will stay consistent for matching the workflow described below to the notebook. 
* There is a workflow to just try this app out, called "Generating and playing with fake data". There's a function where you can generate fake data and see how it looks in the folder, how the graphs work, how you could add vendors to match data that isn't already caught, etc. 
* The next one is "Figuring out what's normal" and is done by having you filter out transactions that haven't happened with X year and month, then the graph will help show you how many transactions you don't have vendors for, or have a vendor but doesn't have a useful default tag, like Amazon or Venmo. There's a pivot table to show you the actual vendors that are costing the most for a given month, and you can filter by things like which vendors don't have tags. You can see all unique tags, and add new vendors.
* Then there is "Periodic Check-in" that works when once you've set up a budget in the "budget_plans.yml" file. This gives a lot of good infomration based on the salary you set in the init cell.

## Some Notes
* I have the most essential and useful functions broken out into a section in the notebook called "Meaningful Function Definitions", each in there own cell with a ?, so if you need to look at what it does, just run the cell. You can run it with two ?? to get the source function if you need.
* This app will be most comfortable for extending if you're familar with Regex, SQLAlchemy, Pandas, Jupyterlab, dictionaries, and Plotly. Otherwise doing the basics should still work, but trying to do more than that might hit a wall pretty quickly.
* I do intend to use this as my budgeting application so hopefully this will continue to be developed!
* This *does not* work well for tracking across multiple accounts. Again, the idea is to track a budget over the course of a month or quarter, not how that saved across multiple accounts and how those accounts are growing. If this is too simple, consider checking out GNUCash!
* I used the [black formatter](https://pypi.org/project/black/)
