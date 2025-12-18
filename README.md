# CAPSTONE APP2 - Mileage Calculator (Flask)

## Purpose
This Flask application records trip mileage and costs for one-way or roundtrip travel.
It supports start/end addresses, in-route stops (with date/time), and additional costs such as gas, food, tolls, and law enforcement citations (tickets). All data is stored in JSON for simplicity.

The app uses the IRS standard mileage rate (business) to estimate reimbursement.

## IRS Mileage Rate Source
The 2025 IRS standard mileage rate for business use is 70 cents per mile.
Reference: IRS “Standard mileage rates” page and related IRS guidance.

## How ChatGPT was used
ChatGPT was used to:
- Design the application structure (Flask routes, templates, JSON storage)
- Generate starter code for forms, validation, and rendering
- Create Render.com deployment settings (Gunicorn start command, requirements.txt)
- Draft beginner step-by-step instructions for VS Code + GitHub sync and deployment

## Run Locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
Open: http://127.0.0.1:5000
<img width="468" height="366" alt="image" src="https://github.com/user-attachments/assets/4405e8be-ce64-42a3-86db-7f31f03c2da2" />

CAPSTONE APP2 – Mileage Calculator Flask app (structure + code) that:
•	Accepts Start Address, End Address, Stops (with address + time)
•	Supports One-way and Roundtrip (same stops applied to both)
•	Uses date/time pickers (HTML datetime-local) for start/stop/arrival
•	Calculates mileage + reimbursement using the current IRS standard mileage rate (2025 business = $0.70/mile) IRS+2IRS+2
•	Stores entries to JSON (no login)
•	Has an Additional Costs page (Gas, Food, Tolls, Tickets with required ticket details)
•	Uses Bootswatch theme (Vapor) + Bootstrap CDN
•	Is deployable to Render.com using Gunicorn
It also includes an optional distance lookup via an API key (so you’re not forced to manually type miles).
<img width="468" height="260" alt="image" src="https://github.com/user-attachments/assets/7d3798af-fd32-4518-ab67-1861838ddad1" />

