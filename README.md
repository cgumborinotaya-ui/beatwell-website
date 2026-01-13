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
   pip install Flask Flask-SQLAlchemy
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
