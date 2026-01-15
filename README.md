# Beatwell Upholstery (Pvt) Ltd Website

This is the website project for Beatwell Upholstery, based on the System Requirements Document.

## Project Structure
- `app.py`: The main Flask application file.
- `templates/`: HTML templates for the website pages.
- `static/`: CSS, images, and other static files.
- `beatwell.db`: SQLite database (created on first run).

## How to Run
1. Ensure you have Python installed.
2. Install dependencies (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open your browser and go to `http://127.0.0.1:5001`.

## Admin Access
- URL: `http://127.0.0.1:5001/login`
- Default Credentials:
  - Username: `admin`
  - Password: `admin123`

## Password Reset (Email or SMS)
- Forgot password page: `http://127.0.0.1:5001/forgot-password`
- The reset link expires after 30 minutes (configurable via `RESET_TOKEN_TTL_SECONDS` in code).

**Email (SMTP) environment variables**
- `SMTP_HOST`
- `SMTP_PORT` (default: `587`)
- `SMTP_USER` (optional, if your SMTP requires login)
- `SMTP_PASSWORD` (optional, if your SMTP requires login)
- `SMTP_USE_TLS` (`1` or `0`, default: `1`)
- `FROM_EMAIL` (sender address; defaults to `SMTP_USER` if not set)

**SMS (Twilio) environment variables (optional)**
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

**Optional admin contact values**
- `ADMIN_EMAIL` (auto-populates the admin user if empty)
- `ADMIN_PHONE` (auto-populates the admin user if empty)

## Keeping Admin Login Working on Render
On Render free services, the filesystem may reset during deploys/restarts, which can reset the SQLite database. To avoid losing access:
- Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in Render Environment.
- If you need to force-reset the password during a deploy, set `ADMIN_RESET_PASSWORD_ON_START=1` temporarily, deploy, then remove it (or set back to `0`).

## Features Implemented
- **Home Page**: Hero banner, services overview, testimonials.
- **Services**: Categorized list of services (Household, Marine, etc.).
- **Portfolio**: Gallery of work (currently using placeholders).
- **Request a Quote**: Form to submit quote requests with image upload.
- **Contact**: Contact information.
- **Admin Dashboard**: View and manage quote requests.

## Customization
- **Colors**: Defined in `static/css/style.css` (Navy, Forest Green, Warm Brown, Cream, Gold).
- **Content**: Edit the HTML files in `templates/` or update the database.
