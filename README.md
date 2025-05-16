# BoockMe

## Description

BoockMe is a Django-based web application designed for booking shared resources or activities such as Pool, Nintendo Switch, and Table Tennis. It allows users to register, log in, view available time slots, book activities, and manage their bookings. Additionally, it features a competitive system where users can set their match availability, find opponents, request matches, create and join competitions, record match results, and track their rankings on a leaderboard. The system also includes an Elo-based ranking system for different activities.

## Key Features

* **User Authentication**: Secure registration, login, and logout functionality.
* **Activity Booking**: Users can book available time slots for various activities like Pool, Nintendo Switch, and Table Tennis.
* **Timetable View**: A clear display of available and booked slots for each activity, navigable by date.
* **Match Availability**: Users can specify their availability for matches for different activities.
* **Find Matches**: Users can find other players with overlapping availability and similar skill levels for specific activities.
* **Match Requests**: Ability to send, receive, and respond to direct match requests between users.
* **Competition Management**:
    * Create competitions for different activities with a maximum number of joiners.
    * Join and leave competitions.
    * Competition creators can add matches (1v1, 2v2, FFA) within a competition.
    * Assign participants to matches.
    * Enter and confirm match results.
    * Mark competitions as completed.
* **Elo Ranking System**: User rankings are updated based on match outcomes using an Elo rating system for 1v1, 2v2, and Free-for-All (FFA) match types.
* **Match History**: Users can view a history of their past matches and their results.
* **Leaderboard**: Displays user rankings for different activities, sortable by activity.
* **User Profiles**: Each user has a profile displaying their rankings for different activities.
* **Database**: Uses MySQL as the backend database.

## Tech Stack

* Python
* Django
* MySQL
* HTML, CSS, JavaScript (for front-end templating and interactions)

## Setup and Installation


1.  **Create a Virtual Environment (Recommended)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2.  **Install Dependencies**:
    You'll need to pip install the requirements.txt file
    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Setup**:
    * Ensure you have MySQL server installed and running.
    * Create a MySQL database named `boockme`.
        ```sql
        CREATE DATABASE boockme;
        ```
    * Configure your database settings in `boockme/settings.py`:
        ```python
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'boockme',
                'USER': 'your_mysql_username',  # Replace with your MySQL username
                'PASSWORD': 'your_mysql_password',  # Replace with your MySQL password
                'HOST': 'localhost',  # Or your MySQL host
                'PORT': '3306',       # Or your MySQL port
            }
        }
        ```
5.  **Apply Migrations**:
    ```bash
    python manage.py migrate
    ```

6.  **Create a Superuser (for Admin Access) (Optional)**:
    ```bash
    python manage.py createsuperuser
    ```
    Follow the prompts to create an administrator account.


## How to Run the Application

1.  **Start the Development Server**:
    ```bash
    python manage.py runserver
    ```
2.  Open your web browser and navigate to `http://127.0.0.1:8000/`.

## How to Run Tests

The project is configured to use Pytest for running tests.


1.  **Run Tests**:
    Navigate to the project's root directory (where `manage.py` is located) and run:
    ```bash
    pytest
    ```
    Tests are expected to be located within the `bookings` application directory, as specified in `pytest.ini`.



2.  **Run Tests (With coverage check)**:
    Navigate to the project's root directory (where `manage.py` is located) and run:
    ```bash
    pytest --cov=bookings 
    ```