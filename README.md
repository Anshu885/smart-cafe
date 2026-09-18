# Smart Cafe Intelligence System — Day 1

This is the Day 1 starter implementation for the IGNOU MCSP-232 project.

## Day 1 completed

- Flask backend created
- MySQL database structure created
- User registration
- Password hashing
- User login/logout
- Session management
- Basic role field
- Dashboard with item/order/sales counts
- Sample cafe items

## Setup

1. Install Python 3.
2. Install MySQL Server.
3. Open MySQL Workbench.
4. Run `database.sql`.
5. Open `app.py`.
6. Change `YOUR_MYSQL_PASSWORD` to your MySQL root password.
7. Open terminal in this folder.
8. Run:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

9. Open:

http://127.0.0.1:5000/

Register a user and login.

## Important

This is only Day 1. Do not add random features yet. The next development stages will build menu management, orders, inventory, analytics, and ML on this same structure.
