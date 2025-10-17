# General Journal App

This app provides a fully functional General Journal for the ERP system.

## Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run migrations:**
    ```bash
    python manage.py migrate
    ```

3.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```

## Usage

1.  Navigate to the General Journal page at `/accounting/journals/advanced-entry/default-journal/`.
2.  Fill out the journal batch form and add journal lines as needed.
3.  Use the "Auto-Balance" button to automatically add a balancing line.
4.  Save the batch using the "Save" button.
5.  Post the batch using the "Post" button.

## Testing

To run the tests, use the following command:
```bash
python manage.py test accounting