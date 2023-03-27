# Close - Customer Support Engineer - Take Home Project
# Eden Simmons - 03/27/23
# Usage: closetest.py API_KEY INPUT_FILE OUTPUT_FILE START_DATE END_DATE

# Note: Some segments are verbose for clarity.
# Oneliners are nice, but can be difficult to support.

debug = False  # True adds some verbose console logs
debugDisableImport = False  # True disables CSV import into Close

# Imports
from closeio_api import Client
import csv
import re
import datetime
import statistics
import sys

if len(sys.argv) < 6:
    print('Invalid arguments.')
    print('closetest.py api_key import_file export_file start_date end_date')
    print('dates should be in ISO format i.e.: 1971-02-27')
    exit()

# Command Line Arguments
apiKey = sys.argv[1]
inputFile = sys.argv[2]
outputFile = sys.argv[3]
argDateFrom = datetime.date.fromisoformat(sys.argv[4])  # datetime.date.fromisoformat('1971-02-27')
argDateTo = datetime.date.fromisoformat(sys.argv[5])  # datetime.date.fromisoformat('2023-01-01')

api = Client(apiKey)

# Regex Setup
validationPhoneNumber = r'^\\+?[1-9][0-9]{7,14}$'
validationEmail = r"^\S+@\S+\.\S+$"

# Delimiters/Symbols
delimitersEmail = ['\n', ',', ';']  # Some delimiters that appear within the data.
delimitersPhone = ['\n', ',', ';']  # Some delimiters that appear within the data.
ignoreSymbols = ['?']

# Output preparation
validatedData = []
listCompanies = []

#  Segment A - Import CSV to Close
with open(inputFile) as openCSV:  # Hold CSV file open, with automatic file close afterwards.

    importCSV = csv.DictReader(openCSV)  # Parses the CSV into a Python-accessible format.

    for contact in importCSV:  # Each CSV row is considered a contact within Close.

        # Data contains instances of multiple emails, this section parses/corrects them.
        if any(delimiter in contact['Contact Emails'] for delimiter in delimitersEmail):  # If there are multiple emails
            emails = contact['Contact Emails']
            # Convert all delimiters to the same newline.
            for delimiter in delimitersEmail[1:]:
                emails = emails.replace(delimiter, delimitersEmail[0])
            # Strip some symbols
            for symbol in ignoreSymbols:
                emails = emails.replace(symbol, '')
            emails = emails.split(delimitersEmail[0])  # Splits emails by newline
            # List comprehension can be difficult to read, the next line removes empty emails.
            contact['Contact Emails'] = [emails for emails in emails if emails]  # Replaces them within the lead.
        else:  # Forces single emails into lists for compatibility below.
            contact['Contact Emails'] = [contact['Contact Emails']]

        # Data contains instances of multiple phone numbers, this section parses/corrects them.
        # If a lead has multiple phone numbers
        if any(delimiter in contact['Contact Phones'] for delimiter in delimitersPhone):
            phones = contact['Contact Phones']
            #  This segment converts all delimiters to the same newline.
            for delimiter in delimitersPhone[1:]:
                phones = phones.replace(delimiter, delimitersPhone[0])
            phones = phones.split(delimitersPhone[0])  # Splits phone numbers by newline
            # List comprehension can be difficult to read, the next line removes empty phone numbers.
            contact['Contact Phones'] = [phones for phones in phones if phones]  # Replaces them within the lead.
        else:  # Forces single phone numbers into lists for compatibility below.
            contact['Contact Phones'] = [contact['Contact Phones']]

        # Some dates skip leading zeroes, this section inserts them.
        if contact['custom.Company Founded']:
            date = contact['custom.Company Founded']
            newDate = []
            for dateSegment in date.split('.'):
                if len(dateSegment) < 2:
                    newDate.append(f'0{dateSegment}')  # If a leading zero is missing, we add it here.
                else:
                    newDate.append(dateSegment)
            contact['custom.Company Founded'] = '.'.join(newDate)

        # Strip invalid information.
        for email in contact['Contact Emails']:
            if email and (re.fullmatch(validationEmail, email) is None):  # Regex emails, not applicable here.
                contact['Contact Emails'].remove(email)
        for phone in contact['Contact Phones']:  # Regex and cull short phone numbers.
            if phone and (len(phone) < 7) or (re.fullmatch(validationPhoneNumber, phone) is None):
                contact['Contact Phones'].remove(phone)

        # Gatekeeper statements for further validation.
        # Removes leads with no contact information.
        if not (contact['Contact Name'] or
                [i for i in contact['Contact Emails'] if i] or [i for i in contact['Contact Phones'] if i]):
            continue
        else:
            # Add valid data, track companies
            validatedData.append(contact)
            if contact['Company'] not in listCompanies:
                listCompanies.append(contact['Company'])

# Debug test point
if debug:
    for data in validatedData:
        print(data)
    for company in listCompanies:
        print(company)

# Close Import
if not debugDisableImport:
    customFieldFounded = None
    customFieldRevenue = None

    # Get the current list of leads and contacts
    importedLeads = api.get('lead')['data']
    importedContacts = api.get('contact')['data']

    # Get custom fields if they exist
    customFields = api.get('custom_field/lead')
    for field in customFields['data']:
        if field['name'] == 'Company Founded':
            customFieldFounded = field['id']
        if field['name'] == 'Company Revenue':
            customFieldRevenue = field['id']

    # Create custom fields if they don't already exist
    if customFieldFounded is None:
        customFieldFounded = api.post('custom_field/lead', {
            'name': 'Company Founded',
            'type': 'date'
        })['id']
    if customFieldRevenue is None:
        customFieldRevenue = api.post('custom_field/lead', {
            'name': 'Company Revenue',
            'type': 'number'
        })['id']

    # Create leads for each company as needed, then create contacts
    for company in listCompanies:
        for contact in [lead for lead in validatedData if lead['Company'] == company]:
            # If there isn't a matching lead yet
            if company not in [lead['name'] for lead in importedLeads if lead['name'] == company]:
                # Handles missing data
                if not contact['custom.Company Founded']:
                    contact['custom.Company Founded'] = None
                if not contact['custom.Company Revenue']:
                    contact['custom.Company Revenue'] = None
                newLead = {  # Create one based off of a contact
                    'name': contact['Company'],
                    f'custom.{customFieldFounded}': contact['custom.Company Founded'],
                    f'custom.{customFieldRevenue}': contact['custom.Company Revenue'],
                }
                if contact['Company US State']:  # Append state if we have one
                    newLead['addresses'] = [{
                        'state': contact['Company US State']
                    }]
                createdLead = api.post('lead',newLead)
                importedLeads.append(createdLead)

            # Prepare contact info to add to lead
            leadID = [lead['id'] for lead in importedLeads if lead['name'] == company][0]
            contactPhones = []
            contactEmails = []
            for phone in contact['Contact Phones']:
                if phone:
                    contactPhones.append({
                        'phone': phone
                    })
            for email in contact['Contact Emails']:
                if email:
                    contactEmails.append({
                        'email': email
                    })

            # Add contact to lead
            if contact['Contact Name'] not in\
                    [contact['name'] for contact in importedContacts if contact['lead_id'] == leadID]:
                newContact = {
                    'lead_id': leadID,
                }
                if contact['Contact Name']:
                    newContact['name'] = contact['Contact Name']
                if contact['Contact Emails']:
                    newContact['emails'] = contactEmails
                if contact['Contact Phones']:
                    newContact['Phones'] = contactPhones
                createdContact = api.post('contact', newContact)
                importedContacts.append(createdContact)

# Segment B - Filter by Date
# Get the most up to date list of leads and contacts
importedLeads = api.get('lead')['data']
importedContacts = api.get('contact')['data']
print(f'{importedLeads} leads with {importedContacts} contacts.')
filterList = []
for lead in importedLeads:
    # Filter out leads without a founding date
    if f'custom.{customFieldFounded}' in lead.keys() and f'custom.{customFieldRevenue}' in lead.keys()\
            and len(lead['addresses']) > 0:  # Also removes leads without location or revenue
        dateFounded = datetime.date.fromisoformat(lead[f'custom.{customFieldFounded}'])
        if argDateFrom <= dateFounded <= argDateTo:
            filterList.append(lead)

print(f'{len(filterList)} valid contacts within date range.')

# Segment C - Group and Output
outputData = {}
for lead in filterList: # Groups by State
    for address in lead['addresses']:
        if address['state'] not in outputData.keys():
            outputData[address['state']] = {}

for state, data in outputData.items(): # Collects data by state
    outputData[state] = {
        'leadCount': len([lead for lead in filterList if state in lead['addresses'][0]['state']]),
        'medianRevenue': statistics.median([lead[f'custom.{customFieldRevenue}'] for lead in filterList if state in lead['addresses'][0]['state']])
    }
    highestRevenue = {f'custom.{customFieldRevenue}': 0}
    for lead in [lead for lead in filterList if state in lead['addresses'][0]['state']]:
        if lead[f'custom.{customFieldRevenue}'] > highestRevenue[f'custom.{customFieldRevenue}']:
            highestRevenue = lead
    outputData[state]['highest'] = highestRevenue

with open(outputFile, 'w', newline='') as openCSV:
    exportCSV = csv.writer(openCSV);
    exportCSV.writerow(['US State', 'Total number of leads', 'Lead with most revenue', 'Total revenue', 'Median revenue'])
    for state, data in outputData.items():  # Output a row for each state
        exportCSV.writerow([
            state,
            data['leadCount'],
            data['highest']['name'],
            data['highest'][f'custom.{customFieldRevenue}'],
            data['medianRevenue']
        ])

print('Script complete.')