# Close Take Home Project - Eden Simmons
Requires the Close API:
`pip install closeio_api`

Usage:
`python .\closetest.py api_key input_file export_file from_date to_date`

Dates must be in ISO format.

Example:
`python .\closetest.py [API_KEY] import.csv export.csv 1971-02-27 2023-01-01`

This script aims to accomplish the following tasks:
* Import a CSV into Close.
* Remove invalid data and entries.
* Select data within a date range.
* Export a report in CSV format including a variety of data and statistics.

Outside of the Close API, all the funcionality necessary is built into Python.

The bulk of the work is filtering out invalid and incomplete data. After importing the entire CSV file, each row is checked for invalid phone numbers and email addresses.

Additionally, contacts that are missing basic information are dropped entirely (in this instance, contacts that have no contact information).
I have opted not to make a decision on names, as they are best fixed on an individual basis.

After the data has been collected and filtered, it is segmented by company name.
At this time, custom fields are either created or loaded for the special data within the CSV file.

A single row for each company is used to generate a lead within close, after which the same row and every related row is imported as a contact.

At this stage, data is completely reloaded from Close, to ensure everything is up to date and orderly.

Using Python's date function, all leads are selected with founding dates within the range provided.
A list of states is made from this data, and used to collect statistics such as maximum and median revenue.

The collected data is then output into a CSV file.