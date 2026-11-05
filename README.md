# Pirate Market

**The campus fashion marketplace for Hampton University students**

Designed & Built by Aniya Hopson, Billy Anders, Cletus Hyacinth, Elisa Earls, James Williams, Madison Rickman, Miles Walker, and Terrance Wynn

CSC 404, Fall 26'

---

## Live Site

**http://pirate-market-env.eba-fiec74jm.us-east-1.elasticbeanstalk.com**

---

## What is Pirate Market?

Pirate Market is a web marketplace just for Hampton University students. Student brands open a storefront, post listings with photos, sizes and stock, and manage everything from their dashboard. Shoppers browse storefronts, categories and the Hot page, save items, add them to their bag and check out. Buyers and sellers meet in person on campus, and students can also use the in-app wallet.

### Features
- Storefronts and listings with photos, sizes and stock
- All Categories with subcategories, sorting and pages
- Hot page (Hot Right Now and Rising) based on what students save, bag and buy
- Bag, checkout, order confirmation and order status
- Wallet with deposits, withdrawals and history
- Messaging between students
- Returns
- Admin dashboard
- Only Hampton University emails (`@hamptonu.edu` / `@my.hamptonu.edu`) can sign up

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript (Jinja templates) |
| Database | PostgreSQL (AWS RDS) |
| Image Storage | Amazon S3 |
| Hosting | AWS Elastic Beanstalk (gunicorn) |
| DB Adapter | psycopg2 |
| Version Control | GitHub |

---

## Running It Locally

### What you need
- Python 3.12+
- The database and S3 settings (ask the team)

### Install

```bash
git clone https://github.com/JamesCliffordWilliams/pirate_marketplace.git
cd pirate_marketplace

python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Settings

Create a `.env` file in the main folder:

```
SECRET_KEY=any-long-random-text
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_SSLMODE=require
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-2
```

Never commit your `.env` file. It's in `.gitignore`.

### Set up a new database

```bash
python3 backend/init_db.py
```

### Run the app

```bash
python3 app.py
```

Then open `http://127.0.0.1:5000`.

---

## Running Tests

```bash
python3 -m unittest discover -s backend/tests -t .
```

Tests that need a database only run against a local one.

---

## Deployment

The site runs on AWS Elastic Beanstalk in `us-east-1` (environment `pirate-market-env`). It deploys automatically when `main` changes on GitHub. The `Procfile` starts the app with gunicorn.

The real database, S3 and `SECRET_KEY` values are set in the Elastic Beanstalk console under Configuration, Environment properties. Don't put real values in `.ebextensions/env.config`.

---

## Team

| Name | Role |
|---|---|
| Billy Anders | Project Manager (PM) |
| Elisa Earls | Co-Project Manager / Backend Support |
| Miles Walker | Document Lead |
| Aniya Hopson | Systems & Security Planning Lead |
| Cletus Hyacinth | Cloud Deployment Lead |
| James Williams | Cloud Deployment Lead |
| Madison Rickman | Database & Application Support Lead |
