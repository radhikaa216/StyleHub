# StyleHub – Fashion Mini Store

StyleHub is a fashion e-commerce application designed to provide a simple and secure online shopping experience. The backend is built using FastAPI, Python, and MySQL, with JWT-based authentication and Stripe payment integration.

## Features

- User Authentication: User registration, login, and JWT-based authentication.
- Product Management: Create, view, update, and deactivate products, with admin access control.
- Shopping Cart: Add products, update quantities, view cart items, and remove items.
- Order Management:Checkout, order history, order details, and order cancellation.
-Stock Management: Validate product stock, reduce stock during checkout, and restore stock when an eligible order is cancelled.
- Payment Integration: Stripe Checkout integration for online payments.
- Payment Webhooks:Process Stripe payment events and update payment status.
- Admin Order Management: View orders and manage order status transitions.
- Database: MySQL with SQLAlchemy ORM.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | MySQL |
| ORM | SQLAlchemy |
| Data Validation | Pydantic |
| Authentication | JWT |
| Password Security | Password Hashing |
| Payment Gateway | Stripe |
| API Documentation | Swagger UI / OpenAPI |
| API Testing |  Swagger UI |
| Version Control | Git and GitHub |

## Project Structure

```text
StyleHub/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── dependencies/
│   │   ├── main.py
│   │   ├── database.py
│   │   └── config.py
│   ├── .env.example
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Prerequisites

Install the following before running the application:

- Python 3.11 or another version supported by the installed dependencies
- MySQL Server
- Git
- A Stripe account for testing online payments

## Backend Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd StyleHub
```

Replace the placeholder with your GitHub repository URL.

### 2. Create and activate a virtual environment

```bash
cd backend
python -m venv venv
```

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` inside the `backend` folder and configure the values for your local environment.

Configure the required settings, including:

- MySQL database connection details
- JWT secret and token settings
- Stripe secret key
- Stripe webhook signing secret
- Stripe publishable key, if required by the application

**Security:** Never commit `.env` or real credentials to GitHub. Use test-mode Stripe keys during development.

### 5. Create the MySQL database

Create the database in MySQL if it does not already exist:

```sql
CREATE DATABASE stylehub_db;
```

Ensure that the database credentials in your `.env` file match your local MySQL configuration.

### 6. Start the FastAPI server

From the `backend` directory, run:

```bash
uvicorn app.main:app --reload
```

The backend should be available at:

- API base URL: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## API Modules

The backend includes the following API modules:

| Module | Purpose |
|---|---|
| Authentication | Registration, login, and current-user details |
| Products | Product listing and admin product management |
| Cart | Shopping cart operations |
| Orders | Checkout, order history, and cancellation |
| Admin Orders | Order listing and order status management |
| Payments | Stripe Checkout sessions and payment webhooks |

Use Swagger UI to explore the available endpoints and test requests.

## Stripe Payment Testing

1. Configure Stripe test-mode credentials in `backend/.env`.
2. Start the FastAPI server.
3. Start the Stripe CLI and forward the relevant Checkout Session events to the webhook endpoint.
4. Complete a test payment using Stripe's official test card details.
5. Verify that the payment and order statuses are updated correctly.

Stripe webhook forwarding example:

```bash
stripe listen --forward-to http://127.0.0.1:8000/payments/webhook
```

Use the webhook signing secret printed by the Stripe CLI for the local webhook configuration. If you restart the listener and receive a new signing secret, update your local configuration and restart the backend.

## Security Notes

- Store passwords securely using password hashing.
- Protect restricted endpoints with authentication and authorization.
- Restrict administrative operations to authorized administrators.
- Keep database credentials, JWT secrets, and Stripe keys in environment variables.
- Validate payment events through Stripe webhook signature verification.
- Use Stripe test mode for development.

## Current Development Status

- Backend API implementation completed.
- MySQL database integration configured.
- Authentication and role-based authorization implemented.
- Product, cart, and order management implemented.
- Stripe Checkout and webhook integration implemented.
- Payment and order cancellation workflows verified manually.
- React frontend: Planned.

