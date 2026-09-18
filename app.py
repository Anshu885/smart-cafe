import pandas as pd

from datetime import date, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

from decimal import Decimal

import mysql.connector
from mysql.connector import Error

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from ml.demand_prediction import (
    get_sales_data,
    train_demand_model
)


app = Flask(__name__)

app.secret_key = "change-this-secret-key"


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Anshu@123",
    "database": "smart_cafe"
}


def get_db_connection():

    return mysql.connector.connect(**DB_CONFIG)


def is_logged_in():

    return "user_id" in session


def is_admin():

    return session.get("role") == "admin"


def get_positive_int(value, default=1):

    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


def get_unread_notification_count(user_id, cursor=None):
    """Return unread notification count for a logged-in user."""

    if cursor is not None:

        cursor.execute(
            """
            SELECT COUNT(*) AS unread_notifications
            FROM notifications
            WHERE user_id = %s
            AND is_read = 0
            """,
            (user_id,)
        )

        return cursor.fetchone()["unread_notifications"]

    conn = get_db_connection()
    local_cursor = conn.cursor(dictionary=True)

    try:

        local_cursor.execute(
            """
            SELECT COUNT(*) AS unread_notifications
            FROM notifications
            WHERE user_id = %s
            AND is_read = 0
            """,
            (user_id,)
        )

        return local_cursor.fetchone()["unread_notifications"]

    finally:

        local_cursor.close()
        conn.close()


def create_notification(
    user_id,
    message,
    order_id=None,
    notification_type="Order",
    conn=None
):
    """Create a notification using an existing transaction when supplied."""

    owns_connection = conn is None

    local_conn = conn or get_db_connection()

    cursor = None

    try:

        cursor = local_conn.cursor()

        cursor.execute(
            """
            INSERT INTO notifications
            (user_id, order_id, message, notification_type, is_read)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                order_id,
                message,
                notification_type,
                0
            )
        )

        if owns_connection:
            local_conn.commit()

    except Error:

        if owns_connection:
            local_conn.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        if owns_connection:
            local_conn.close()


# =========================================================
# PRODUCT RECOMMENDATION
# =========================================================

def get_recommendations(item_id):

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            oi2.item_id AS recommended_item_id,
            i2.item_name AS recommended_item,
            i2.price,
            COUNT(DISTINCT oi1.order_id) AS times_bought_together
        FROM order_item oi1

        JOIN order_item oi2
            ON oi1.order_id = oi2.order_id
            AND oi1.item_id <> oi2.item_id

        JOIN items i2
            ON oi2.item_id = i2.item_id

        WHERE oi1.item_id = %s

        GROUP BY
            oi2.item_id,
            i2.item_name,
            i2.price

        ORDER BY
            times_bought_together DESC

        LIMIT 3
        """,
        (item_id,)
    )

    recommendations = cursor.fetchall()

    cursor.close()
    conn.close()

    return recommendations


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        email = request.form[
            "email"
        ].strip()

        password = request.form[
            "password"
        ]

        if not username or not email or not password:

            flash(
                "All fields are required."
            )

            return redirect(
                url_for("register")
            )

        try:

            conn = get_db_connection()

            cursor = conn.cursor()

            password_hash = generate_password_hash(
                password
            )

            cursor.execute(
                """
                INSERT INTO users
                (username, email, password, role)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    username,
                    email,
                    password_hash,
                    "user"
                )
            )

            conn.commit()

            cursor.close()
            conn.close()

            flash(
                "Registration successful. Please login."
            )

            return redirect(
                url_for("login")
            )

        except Error as e:

            flash(
                "Registration failed. Email may already exist."
            )

            print(
                "Database error:",
                e
            )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form[
            "email"
        ].strip()

        password = request.form[
            "password"
        ]

        try:

            conn = get_db_connection()

            cursor = conn.cursor(
                dictionary=True
            )

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            cursor.close()
            conn.close()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session["user_id"] = user[
                    "user_id"
                ]

                session["username"] = user[
                    "username"
                ]

                session["role"] = user[
                    "role"
                ]

                return redirect(
                    url_for("dashboard")
                )

            flash(
                "Invalid email or password."
            )

        except Error as e:

            flash(
                "Could not connect to the database."
            )

            print(
                "Database error:",
                e
            )

    return render_template(
        "login.html"
    )


# =========================================================
# ADMIN DEMAND PREDICTION
# =========================================================

@app.route(
    "/admin/demand-prediction"
)
def admin_demand_prediction():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    # =====================================================
    # GET HISTORICAL SALES DATA
    # =====================================================

    sales_data = get_sales_data()

    if sales_data.empty:

        return render_template(
            "demand_prediction.html",
            predictions=[],
            prediction_date=None
        )

    # =====================================================
    # PREPARE HISTORICAL DATA
    # =====================================================

    sales_data["order_date"] = pd.to_datetime(
        sales_data["order_date"]
    )

    sales_data["day_of_week"] = (
        sales_data["order_date"].dt.dayofweek
    )

    # =====================================================
    # FUTURE PREDICTION DATE
    # =====================================================

    prediction_date = (
        date.today()
        + timedelta(days=1)
    )

    prediction_day_of_week = (
        prediction_date.weekday()
    )

    # =====================================================
    # GET CURRENT MENU ITEMS
    # =====================================================

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            item_id,
            item_name,
            stock_quantity
        FROM items
        ORDER BY item_name
        """
    )

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    # =====================================================
    # TRAIN ML MODEL
    # =====================================================

    model = train_demand_model(
        sales_data
    )

    prediction_results = []

    # =====================================================
    # PREDICT DEMAND FOR EACH ITEM
    # =====================================================

    for item in items:

        item_history = sales_data[
            sales_data["item_id"]
            == item["item_id"]
        ]

        predicted_demand = 0

        prediction_available = False

        # -------------------------------------------------
        # MINIMUM HISTORICAL RECORDS
        # -------------------------------------------------

        if len(item_history) >= 2:

            prediction_data = pd.DataFrame({

                "item_id": [
                    item["item_id"]
                ],

                "day_of_week": [
                    prediction_day_of_week
                ]

            })

            predicted_demand = float(
                model.predict(
                    prediction_data
                )[0]
            )

            # -------------------------------------------------
            # DEMAND CANNOT BE NEGATIVE
            # -------------------------------------------------

            if predicted_demand < 0:

                predicted_demand = 0

            prediction_available = True

        # -------------------------------------------------
        # STORE RESULT
        # -------------------------------------------------

        prediction_results.append({

            "item_name":
                item["item_name"],

            "current_stock":
                item["stock_quantity"],

            "predicted_demand":
                predicted_demand,

            "prediction_available":
                prediction_available

        })

    # =====================================================
    # SEND RESULTS TO TEMPLATE
    # =====================================================

    return render_template(

        "demand_prediction.html",

        predictions=prediction_results,

        prediction_date=
            prediction_date.strftime(
                "%d %B %Y"
            )

    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    conn = None

    cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        if is_admin():

            # =================================================
            # ADMIN DASHBOARD
            # =================================================

            cursor.execute(
                """
                SELECT COUNT(*) AS total_items
                FROM items
                """
            )

            total_items = cursor.fetchone()[
                "total_items"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_orders
                FROM orders
                """
            )

            total_orders = cursor.fetchone()[
                "total_orders"
            ]

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(total_sale),
                        0
                    ) AS total_sales
                FROM sales
                """
            )

            total_sales = cursor.fetchone()[
                "total_sales"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS pending_orders
                FROM orders
                WHERE order_status = 'Pending'
                """
            )

            pending_orders = cursor.fetchone()[
                "pending_orders"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS low_stock_items
                FROM items
                WHERE stock_quantity <= 5
                """
            )

            low_stock_items = cursor.fetchone()[
                "low_stock_items"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS completed_sales
                FROM sales
                """
            )

            completed_sales = cursor.fetchone()[
                "completed_sales"
            ]

            cursor.execute(
                """
                SELECT
                    DATE(sale_date) AS sale_date,
                    COALESCE(
                        SUM(total_sale),
                        0
                    ) AS daily_sales

                FROM sales

                WHERE sale_date >=
                    CURDATE() - INTERVAL 6 DAY

                GROUP BY DATE(sale_date)

                ORDER BY sale_date ASC
                """
            )

            sales_overview = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    o.order_id,
                    u.username,
                    o.total_amount,
                    o.order_status,
                    o.order_date

                FROM orders o

                JOIN users u
                    ON o.user_id = u.user_id

                WHERE o.order_status IN
                    ('Pending', 'Preparing', 'Ready')

                ORDER BY
                    o.order_date DESC,
                    o.order_id DESC

                LIMIT 10
                """
            )

            recent_orders = cursor.fetchall()

            return render_template(

                "dashboard.html",

                is_admin=True,

                total_items=total_items,

                total_orders=total_orders,

                total_sales=total_sales,

                pending_orders=pending_orders,

                low_stock_items=low_stock_items,

                completed_sales=completed_sales,

                recent_orders=recent_orders,

                sales_overview=sales_overview,

                unread_notifications=
                    get_unread_notification_count(
                        session["user_id"],
                        cursor=cursor
                    )

            )

        # =====================================================
        # CUSTOMER DASHBOARD
        # =====================================================

        user_id = session[
            "user_id"
        ]

        cursor.execute(
            """
            SELECT COUNT(*) AS my_total_orders
            FROM orders
            WHERE user_id = %s
            """,
            (user_id,)
        )

        my_total_orders = cursor.fetchone()[
            "my_total_orders"
        ]

        cursor.execute(
            """
            SELECT COUNT(*) AS my_pending_orders

            FROM orders

            WHERE user_id = %s
              AND order_status != 'Completed'
            """,
            (user_id,)
        )

        my_pending_orders = cursor.fetchone()[
            "my_pending_orders"
        ]

        cursor.execute(
            """
            SELECT
                order_id,
                total_amount,
                order_status,
                order_date

            FROM orders

            WHERE user_id = %s

            ORDER BY
                order_date DESC,
                order_id DESC

            LIMIT 1
            """,
            (user_id,)
        )

        recent_order = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS unread_notifications

            FROM notifications

            WHERE user_id = %s
              AND is_read = 0
            """,
            (user_id,)
        )

        unread_notifications = cursor.fetchone()[
            "unread_notifications"
        ]

        return render_template(

            "dashboard.html",

            is_admin=False,

            my_total_orders=my_total_orders,

            my_pending_orders=my_pending_orders,

            recent_order=recent_order,

            total_items=0,

            total_orders=0,

            total_sales=0,

            pending_orders=0,

            low_stock_items=0,

            completed_sales=0,

            recent_orders=[],

            sales_overview=[],

            unread_notifications=
                unread_notifications

        )

    except Error as e:

        print(
            "Dashboard database error:",
            e
        )

        flash(
            "Dashboard could not load.",
            "danger"
        )

        return render_template(

            "dashboard.html",

            is_admin=is_admin(),

            total_items=0,

            total_orders=0,

            total_sales=0,

            pending_orders=0,

            low_stock_items=0,

            completed_sales=0,

            my_total_orders=0,

            my_pending_orders=0,

            recent_order=None,

            recent_orders=[],

            sales_overview=[],

            unread_notifications=0

        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# TOPBAR SEARCH
# =========================================================

@app.route("/search-items")
def search_items():

    if not is_logged_in():

        return jsonify([])

    query = request.args.get(
        "q",
        ""
    ).strip()

    if not query:

        return jsonify([])

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                item_id,
                item_name,
                category,
                price

            FROM items

            WHERE item_name LIKE %s
               OR category LIKE %s

            ORDER BY item_name

            LIMIT 10
            """,
            (
                f"%{query}%",
                f"%{query}%"
            )
        )

        return jsonify(
            cursor.fetchall()
        )

    finally:

        cursor.close()
        conn.close()


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.route("/notifications")
def notifications():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                notification_id,
                order_id,
                message,
                notification_type,
                is_read,
                created_at

            FROM notifications

            WHERE user_id = %s

            ORDER BY created_at DESC
            """,
            (
                session["user_id"],
            )
        )

        notification_list = cursor.fetchall()

        return render_template(
            "notifications.html",
            notifications=notification_list
        )

    finally:

        cursor.close()
        conn.close()


@app.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"]
)
def mark_notification_read(
    notification_id
):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            UPDATE notifications

            SET is_read = 1

            WHERE notification_id = %s
              AND user_id = %s
            """,
            (
                notification_id,
                session["user_id"]
            )
        )

        conn.commit()

        return redirect(
            url_for("notifications")
        )

    finally:

        cursor.close()
        conn.close()


@app.route(
    "/notifications/read-all",
    methods=["POST"]
)
def mark_all_notifications_read():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            UPDATE notifications

            SET is_read = 1

            WHERE user_id = %s
              AND is_read = 0
            """,
            (
                session["user_id"],
            )
        )

        conn.commit()

        return redirect(
            url_for("notifications")
        )

    finally:

        cursor.close()
        conn.close()


# =========================================================
# MENU MANAGEMENT
# =========================================================


# =========================================================
# VIEW MENU
# =========================================================

@app.route("/menu")
def menu():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    query = """
        SELECT
            item_id,
            item_name,
            category,
            price,
            stock_quantity
        FROM items
        WHERE 1=1
    """

    params = []

    # =====================================================
    # SEARCH BY ITEM NAME
    # =====================================================

    if search:

        query += """
            AND item_name LIKE %s
        """

        params.append(
            "%" + search + "%"
        )

    # =====================================================
    # FILTER BY CATEGORY
    # =====================================================

    if category:

        query += """
            AND category = %s
        """

        params.append(
            category
        )

    query += """
        ORDER BY item_id DESC
    """

    cursor.execute(
        query,
        params
    )

    items = cursor.fetchall()

    # =====================================================
    # GET CATEGORIES
    # =====================================================

    cursor.execute(
        """
        SELECT DISTINCT category
        FROM items
        ORDER BY category
        """
    )

    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "menu.html",

        items=items,

        categories=categories,

        search=search,

        selected_category=category

    )


# =========================================================
# MENU ITEM DETAILS
# =========================================================

@app.route(
    "/menu/item/<int:item_id>"
)
def menu_item(item_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            item_id,
            item_name,
            category,
            price,
            stock_quantity

        FROM items

        WHERE item_id = %s
        """,
        (item_id,)
    )

    item = cursor.fetchone()

    cursor.close()
    conn.close()

    if not item:

        return "Item not found", 404

    recommendations = get_recommendations(
        item_id
    )

    return render_template(

        "menu_item.html",

        item=item,

        recommendations=
            recommendations

    )


# =========================================================
# ADD MENU ITEM
# =========================================================

@app.route(
    "/menu/add",
    methods=["GET", "POST"]
)
def add_item():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access Denied", 403

    if request.method == "POST":

        item_name = request.form[
            "item_name"
        ]

        category = request.form[
            "category"
        ]

        price = request.form[
            "price"
        ]

        stock_quantity = request.form[
            "stock_quantity"
        ]

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO items
            (
                item_name,
                category,
                price,
                stock_quantity
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                item_name,
                category,
                price,
                stock_quantity
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(
            url_for("menu")
        )

    return render_template(
        "add_item.html"
    )


# =========================================================
# EDIT MENU ITEM
# =========================================================

@app.route(
    "/menu/edit/<int:item_id>",
    methods=["GET", "POST"]
)
def edit_item(item_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access Denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    if request.method == "POST":

        item_name = request.form[
            "item_name"
        ]

        category = request.form[
            "category"
        ]

        price = request.form[
            "price"
        ]

        stock_quantity = request.form[
            "stock_quantity"
        ]

        cursor.execute(
            """
            UPDATE items

            SET
                item_name = %s,
                category = %s,
                price = %s,
                stock_quantity = %s

            WHERE item_id = %s
            """,
            (
                item_name,
                category,
                price,
                stock_quantity,
                item_id
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(
            url_for("menu")
        )

    cursor.execute(
        """
        SELECT
            item_id,
            item_name,
            category,
            price,
            stock_quantity

        FROM items

        WHERE item_id = %s
        """,
        (item_id,)
    )

    item = cursor.fetchone()

    cursor.close()
    conn.close()

    if not item:

        return "Item not found", 404

    return render_template(

        "edit_item.html",

        item=item

    )


# =========================================================
# DELETE MENU ITEM
# =========================================================

@app.route(
    "/menu/delete/<int:item_id>",
    methods=["POST"]
)
def delete_item(item_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access Denied", 403

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM items
        WHERE item_id = %s
        """,
        (item_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(
        url_for("menu")
    )


# =========================================================
# CUSTOMER CART
# =========================================================


# =========================================================
# ADD TO CART
# =========================================================

@app.route(
    "/cart/add/<int:item_id>",
    methods=["POST"]
)
def add_to_cart(item_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    quantity = get_positive_int(
        request.form.get(
            "quantity",
            1
        )
    )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                item_id,
                item_name,
                price,
                stock_quantity

            FROM items

            WHERE item_id = %s
            """,
            (item_id,)
        )

        item = cursor.fetchone()

        if not item:

            return "Item not found", 404

        if item["stock_quantity"] <= 0:

            flash(
                f"{item['item_name']} is currently out of stock.",
                "warning"
            )

            return redirect(
                url_for("menu")
            )

        cart = session.get(
            "cart",
            {}
        )

        item_id_str = str(
            item_id
        )

        current_quantity = (
            get_positive_int(
                cart.get(
                    item_id_str,
                    0
                ),
                0
            )
            if cart.get(item_id_str)
            else 0
        )

        new_quantity = (
            current_quantity
            + quantity
        )

        if new_quantity > item[
            "stock_quantity"
        ]:

            flash(
                f"Only {item['stock_quantity']} "
                f"{item['item_name']} available in stock.",
                "warning"
            )

            return redirect(
                url_for("menu")
            )

        cart[
            item_id_str
        ] = new_quantity

        session["cart"] = cart

        session.modified = True

        flash(
            f"{item['item_name']} added to cart.",
            "success"
        )

        return redirect(
            url_for("menu")
        )

    finally:

        cursor.close()
        conn.close()


# =========================================================
# VIEW CART
# =========================================================

@app.route("/cart")
def cart():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    cart = session.get(
        "cart",
        {}
    )

    cart_items = []

    total = Decimal(
        "0.00"
    )

    if cart:

        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        try:

            item_ids = []

            for item_id in cart.keys():

                try:

                    item_ids.append(
                        int(item_id)
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue

            if item_ids:

                placeholders = ",".join(
                    ["%s"] * len(item_ids)
                )

                cursor.execute(
                    f"""
                    SELECT
                        item_id,
                        item_name,
                        category,
                        price,
                        stock_quantity

                    FROM items

                    WHERE item_id IN
                        ({placeholders})
                    """,
                    item_ids
                )

                items = cursor.fetchall()

            else:

                items = []

            valid_ids = set()

            for item in items:

                item_id_str = str(
                    item["item_id"]
                )

                valid_ids.add(
                    item_id_str
                )

                quantity = get_positive_int(
                    cart.get(
                        item_id_str
                    ),
                    1
                )

                if item[
                    "stock_quantity"
                ] <= 0:

                    continue

                if quantity > item[
                    "stock_quantity"
                ]:

                    quantity = item[
                        "stock_quantity"
                    ]

                    cart[
                        item_id_str
                    ] = quantity

                price = Decimal(
                    str(
                        item["price"]
                    )
                )

                subtotal = (
                    price
                    * quantity
                )

                total += subtotal

                cart_items.append({

                    "item_id":
                        item["item_id"],

                    "item_name":
                        item["item_name"],

                    "price":
                        float(price),

                    "quantity":
                        quantity,

                    "subtotal":
                        float(subtotal)

                })

            # -------------------------------------------------
            # REMOVE INVALID CART ITEMS
            # -------------------------------------------------

            for item_id_str in list(
                cart.keys()
            ):

                if item_id_str not in valid_ids:

                    cart.pop(
                        item_id_str,
                        None
                    )

            session["cart"] = cart

            session.modified = True

        finally:

            cursor.close()
            conn.close()

    return render_template(

        "cart.html",

        cart_items=cart_items,

        total=float(total)

    )


# =========================================================
# REMOVE FROM CART
# =========================================================

@app.route(
    "/cart/remove/<int:item_id>",
    methods=["POST"]
)
def remove_from_cart(item_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    cart = session.get(
        "cart",
        {}
    )

    if str(item_id) in cart:

        del cart[
            str(item_id)
        ]

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


# =========================================================
# INCREASE CART QUANTITY
# =========================================================

@app.route(
    "/cart/increase/<int:item_id>",
    methods=["POST"]
)
def increase_quantity(item_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    cart = session.get(
        "cart",
        {}
    )

    item_id_str = str(
        item_id
    )

    if item_id_str not in cart:

        return redirect(
            url_for("cart")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                item_name,
                stock_quantity

            FROM items

            WHERE item_id = %s
            """,
            (item_id,)
        )

        item = cursor.fetchone()

        if not item:

            cart.pop(
                item_id_str,
                None
            )

        else:

            current_quantity = (
                get_positive_int(
                    cart[item_id_str]
                )
            )

            if current_quantity < item[
                "stock_quantity"
            ]:

                cart[
                    item_id_str
                ] = (
                    current_quantity
                    + 1
                )

            else:

                flash(
                    f"Only {item['stock_quantity']} "
                    f"{item['item_name']} available in stock.",
                    "warning"
                )

        session["cart"] = cart

        session.modified = True

        return redirect(
            url_for("cart")
        )

    finally:

        cursor.close()
        conn.close()


# =========================================================
# DECREASE CART QUANTITY
# =========================================================

@app.route(
    "/cart/decrease/<int:item_id>",
    methods=["POST"]
)
def decrease_quantity(item_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    cart = session.get(
        "cart",
        {}
    )

    item_id_str = str(
        item_id
    )

    if item_id_str in cart:

        current_quantity = (
            get_positive_int(
                cart[item_id_str]
            )
        )

        current_quantity -= 1

        if current_quantity <= 0:

            cart.pop(
                item_id_str,
                None
            )

        else:

            cart[
                item_id_str
            ] = current_quantity

    session["cart"] = cart

    session.modified = True

    return redirect(
        url_for("cart")
    )


# =========================================================
# PLACE ORDER
# =========================================================

@app.route(
    "/order/place",
    methods=["POST"]
)
def place_order():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    cart = session.get(
        "cart",
        {}
    )

    if not cart:

        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(
            url_for("cart")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        item_ids = []

        clean_cart = {}

        for item_id, quantity in cart.items():

            try:

                parsed_item_id = int(
                    item_id
                )

                parsed_quantity = int(
                    quantity
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            if parsed_quantity <= 0:

                continue

            item_ids.append(
                parsed_item_id
            )

            clean_cart[
                str(parsed_item_id)
            ] = parsed_quantity

        if not item_ids:

            session.pop(
                "cart",
                None
            )

            return redirect(
                url_for("cart")
            )

        placeholders = ",".join(
            ["%s"] * len(item_ids)
        )

        # =================================================
        # LOCK INVENTORY ROWS
        # =================================================

        cursor.execute(
            f"""
            SELECT
                item_id,
                item_name,
                price,
                stock_quantity

            FROM items

            WHERE item_id IN
                ({placeholders})

            FOR UPDATE
            """,
            item_ids
        )

        items = cursor.fetchall()

        if len(items) != len(
            set(item_ids)
        ):

            conn.rollback()

            flash(
                "One or more items in your cart are no longer available.",
                "warning"
            )

            session["cart"] = {

                str(item["item_id"]):
                    clean_cart[
                        str(item["item_id"])
                    ]

                for item in items

                if str(
                    item["item_id"]
                ) in clean_cart

            }

            return redirect(
                url_for("cart")
            )

        total_amount = Decimal(
            "0.00"
        )

        # =================================================
        # CHECK STOCK
        # =================================================

        for item in items:

            quantity = clean_cart[
                str(
                    item["item_id"]
                )
            ]

            if item[
                "stock_quantity"
            ] < quantity:

                conn.rollback()

                flash(
                    f"Only {item['stock_quantity']} "
                    f"{item['item_name']} available in stock.",
                    "warning"
                )

                return redirect(
                    url_for("cart")
                )

            total_amount += (
                Decimal(
                    str(
                        item["price"]
                    )
                )
                * quantity
            )

        # =================================================
        # CREATE ORDER
        # =================================================

        cursor.execute(
            """
            INSERT INTO orders
            (
                user_id,
                total_amount,
                order_status
            )

            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session["user_id"],
                total_amount,
                "Pending"
            )
        )

        order_id = cursor.lastrowid

        # =================================================
        # CREATE ORDER ITEMS
        # =================================================

        for item in items:

            quantity = clean_cart[
                str(
                    item["item_id"]
                )
            ]

            subtotal = (
                Decimal(
                    str(
                        item["price"]
                    )
                )
                * quantity
            )

            cursor.execute(
                """
                INSERT INTO order_item
                (
                    order_id,
                    item_id,
                    quantity,
                    subtotal
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    order_id,
                    item["item_id"],
                    quantity,
                    subtotal
                )
            )

            # =================================================
            # UPDATE STOCK
            # =================================================

            cursor.execute(
                """
                UPDATE items

                SET stock_quantity =
                    stock_quantity - %s

                WHERE item_id = %s
                  AND stock_quantity >= %s
                """,
                (
                    quantity,
                    item["item_id"],
                    quantity
                )
            )

            if cursor.rowcount != 1:

                raise RuntimeError(
                    f"Stock changed while placing order "
                    f"for {item['item_name']}."
                )

        # =================================================
        # CUSTOMER NOTIFICATION
        # =================================================

        create_notification(

            session["user_id"],

            f"Order #{order_id} has been placed successfully.",

            order_id,

            "Order",

            conn=conn

        )

        # =================================================
        # ADMIN NOTIFICATION
        # =================================================

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE role = 'admin'
            """
        )

        admin_users = cursor.fetchall()

        for admin_user in admin_users:

            create_notification(

                admin_user["user_id"],

                f"New Order #{order_id} received "
                f"from {session['username']}.",

                order_id,

                "New Order",

                conn=conn

            )

        conn.commit()

        session.pop(
            "cart",
            None
        )

        flash(
            f"Order #{order_id} placed successfully.",
            "success"
        )

        return redirect(
            url_for(
                "order_confirmation",
                order_id=order_id
            )
        )

    except Exception as e:

        conn.rollback()

        print(
            "Order placement error:",
            e
        )

        flash(
            "Order could not be placed. Please try again.",
            "danger"
        )

        return redirect(
            url_for("cart")
        )

    finally:

        cursor.close()
        conn.close()


# =========================================================
# ORDER CONFIRMATION
# =========================================================

@app.route(
    "/order/confirmation/<int:order_id>"
)
def order_confirmation(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            order_id,
            total_amount,
            order_status,
            order_date

        FROM orders

        WHERE order_id = %s
          AND user_id = %s
        """,
        (
            order_id,
            session["user_id"]
        )
    )

    order = cursor.fetchone()

    cursor.close()
    conn.close()

    if not order:

        return "Order not found", 404

    return render_template(

        "order_confirmation.html",

        order=order

    )


# =========================================================
# CUSTOMER ORDERS
# =========================================================

@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            order_id,
            total_amount,
            order_status,
            order_date

        FROM orders

        WHERE user_id = %s

        ORDER BY order_date DESC
        """,
        (
            session["user_id"],
        )
    )

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "my_orders.html",

        orders=orders

    )


# =========================================================
# CUSTOMER ORDER DETAILS
# =========================================================

@app.route(
    "/my-orders/<int:order_id>"
)
def my_order_details(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # GET CUSTOMER'S ORDER
    # =====================================================

    cursor.execute(
        """
        SELECT
            o.order_id,
            o.total_amount,
            o.order_status,
            o.order_date

        FROM orders o

        WHERE o.order_id = %s
          AND o.user_id = %s
        """,
        (
            order_id,
            session["user_id"]
        )
    )

    order = cursor.fetchone()

    if not order:

        cursor.close()
        conn.close()

        return (
            "Order not found or access denied",
            404
        )

    # =====================================================
    # GET ORDER ITEMS
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,
            oi.quantity,
            i.price,
            oi.subtotal

        FROM order_item oi

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE oi.order_id = %s
        """,
        (order_id,)
    )

    order_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "my_order_details.html",

        order=order,

        order_items=order_items

    )


# =========================================================
# CUSTOMER BILL
# =========================================================

@app.route(
    "/my-orders/<int:order_id>/bill"
)
def customer_bill(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # GET CUSTOMER ORDER
    # =====================================================

    cursor.execute(
        """
        SELECT
            o.order_id,
            o.total_amount,
            o.order_status,
            o.order_date,
            u.username

        FROM orders o

        JOIN users u
            ON o.user_id = u.user_id

        WHERE o.order_id = %s
          AND o.user_id = %s
        """,
        (
            order_id,
            session["user_id"]
        )
    )

    order = cursor.fetchone()

    if not order:

        cursor.close()
        conn.close()

        return (
            "Order not found or access denied",
            404
        )

    # =====================================================
    # GET ORDER ITEMS
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,
            i.price,
            oi.quantity,
            oi.subtotal

        FROM order_item oi

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE oi.order_id = %s
        """,
        (order_id,)
    )

    order_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "customer_bill.html",

        order=order,

        order_items=order_items

    )


# =========================================================
# ADMIN ORDER MANAGEMENT
# =========================================================


# =========================================================
# VIEW ALL ORDERS
# =========================================================

@app.route("/admin/orders")
def admin_orders():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            o.order_id,
            u.username,
            o.total_amount,
            o.order_status,
            o.order_date

        FROM orders o

        JOIN users u
            ON o.user_id = u.user_id

        ORDER BY o.order_date DESC
        """
    )

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin_orders.html",

        orders=orders

    )


# =========================================================
# ADMIN ORDER DETAILS
# =========================================================

@app.route(
    "/admin/orders/<int:order_id>"
)
def admin_order_details(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # ORDER INFORMATION
    # =====================================================

    cursor.execute(
        """
        SELECT
            o.order_id,
            u.username,
            o.total_amount,
            o.order_status,
            o.order_date

        FROM orders o

        JOIN users u
            ON o.user_id = u.user_id

        WHERE o.order_id = %s
        """,
        (order_id,)
    )

    order = cursor.fetchone()

    if not order:

        cursor.close()
        conn.close()

        return "Order not found", 404

    # =====================================================
    # ORDERED ITEMS
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,
            i.price,
            oi.quantity,
            oi.subtotal

        FROM order_item oi

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE oi.order_id = %s
        """,
        (order_id,)
    )

    order_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin_order_details.html",

        order=order,

        order_items=order_items

    )


# =========================================================
# UPDATE ORDER STATUS
# =========================================================

@app.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"]
)
def update_order_status(order_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )

    if not is_admin():

        return "Access denied", 403

    new_status = request.form.get(
        "order_status",
        ""
    ).strip()

    allowed_statuses = [

        "Pending",

        "Preparing",

        "Ready",

        "Completed"

    ]

    if new_status not in allowed_statuses:

        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for("admin_orders")
        )

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                user_id,
                total_amount,
                order_status

            FROM orders

            WHERE order_id = %s

            FOR UPDATE
            """,
            (order_id,)
        )

        existing_order = cursor.fetchone()

        if not existing_order:

            conn.rollback()

            return "Order not found", 404

        old_status = existing_order[
            "order_status"
        ]

        customer_id = existing_order[
            "user_id"
        ]

        if old_status == new_status:

            conn.commit()

            flash(
                f"Order #{order_id} is already {new_status}.",
                "info"
            )

            return redirect(
                url_for(
                    "admin_order_details",
                    order_id=order_id
                )
            )

        status_order = {

            "Pending": 0,

            "Preparing": 1,

            "Ready": 2,

            "Completed": 3

        }

        # =================================================
        # PREVENT BACKWARD STATUS
        # =================================================

        if old_status == "Completed":

            conn.rollback()

            flash(
                "A completed order cannot be moved back to an earlier status.",
                "warning"
            )

            return redirect(
                url_for(
                    "admin_order_details",
                    order_id=order_id
                )
            )

        if (
            status_order[new_status]
            != status_order[old_status] + 1
        ):

            conn.rollback()

            flash(
                f"Order #{order_id} must move from "
                f"{old_status} to the next status in sequence.",
                "warning"
            )

            return redirect(
                url_for(
                    "admin_order_details",
                    order_id=order_id
                )
            )

        # =================================================
        # UPDATE STATUS
        # =================================================

        cursor.execute(
            """
            UPDATE orders

            SET order_status = %s

            WHERE order_id = %s
            """,
            (
                new_status,
                order_id
            )
        )

        status_messages = {

            "Preparing":
                f"Order #{order_id} is now being prepared.",

            "Ready":
                f"Order #{order_id} is ready for pickup.",

            "Completed":
                f"Order #{order_id} has been completed."

        }

        # =================================================
        # CUSTOMER NOTIFICATION
        # =================================================

        create_notification(

            customer_id,

            status_messages[new_status],

            order_id,

            "Order",

            conn=conn

        )

        # =================================================
        # CREATE SALES RECORD WHEN COMPLETED
        # =================================================

        if new_status == "Completed":

            cursor.execute(
                """
                SELECT sale_id

                FROM sales

                WHERE order_id = %s
                """,
                (order_id,)
            )

            existing_sale = cursor.fetchone()

            if not existing_sale:

                cursor.execute(
                    """
                    INSERT INTO sales
                    (
                        order_id,
                        total_sale
                    )

                    VALUES
                    (
                        %s,
                        %s
                    )
                    """,
                    (
                        order_id,
                        existing_order[
                            "total_amount"
                        ]
                    )
                )

        conn.commit()

        flash(
            f"Order #{order_id} updated to {new_status}.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "Order status error:",
            e
        )

        flash(
            "Order status could not be updated.",
            "danger"
        )

    finally:

        cursor.close()
        conn.close()

    return redirect(
        url_for(
            "admin_order_details",
            order_id=order_id
        )
    )


# =========================================================
# BILLING
# =========================================================

@app.route(
    "/admin/orders/<int:order_id>/bill"
)
def generate_bill(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # GET ORDER
    # =====================================================

    cursor.execute(
        """
        SELECT
            o.order_id,
            u.username,
            o.total_amount,
            o.order_status,
            o.order_date

        FROM orders o

        JOIN users u
            ON o.user_id = u.user_id

        WHERE o.order_id = %s
        """,
        (order_id,)
    )

    order = cursor.fetchone()

    if not order:

        cursor.close()
        conn.close()

        return "Order not found", 404

    # =====================================================
    # GET ORDER ITEMS
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,
            i.price,
            oi.quantity,
            oi.subtotal

        FROM order_item oi

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE oi.order_id = %s
        """,
        (order_id,)
    )

    order_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "bill.html",

        order=order,

        order_items=order_items

    )


# =========================================================
# SALES RECORDS
# =========================================================

@app.route("/admin/sales")
def admin_sales():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            sale_id,
            order_id,
            total_sale,
            sale_date

        FROM sales

        ORDER BY sale_date DESC
        """
    )

    sales = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin_sales.html",

        sales=sales

    )


# =========================================================
# INVENTORY INTELLIGENCE
# =========================================================

@app.route("/admin/inventory")
def admin_inventory():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    # =====================================================
    # GET ML SALES DATA
    # =====================================================

    sales_data = get_sales_data()

    if not sales_data.empty:

        sales_data["order_date"] = pd.to_datetime(
            sales_data["order_date"]
        )

        sales_data["day_of_week"] = (
            sales_data["order_date"].dt.dayofweek
        )

        model = train_demand_model(
            sales_data
        )

    else:

        model = None

    # =====================================================
    # FUTURE PREDICTION DATE
    # =====================================================

    prediction_date = (
        date.today()
        + timedelta(days=1)
    )

    prediction_day_of_week = (
        prediction_date.weekday()
    )

    # =====================================================
    # GET ALL INVENTORY ITEMS
    # =====================================================

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            item_id,
            item_name,
            category,
            price,
            stock_quantity

        FROM items

        ORDER BY item_name
        """
    )

    items = cursor.fetchall()

    # =====================================================
    # CALCULATE INVENTORY INTELLIGENCE
    # =====================================================

    inventory_data = []

    for item in items:

        current_stock = item[
            "stock_quantity"
        ]

        predicted_demand = 0

        suggested_reorder = 0

        prediction_available = False

        # =================================================
        # GET ITEM HISTORY
        # =================================================

        if sales_data.empty:

            item_history = pd.DataFrame()

        else:

            item_history = sales_data[
                sales_data["item_id"]
                == item["item_id"]
            ]

        # =================================================
        # PREDICT TOMORROW'S DEMAND
        # =================================================

        if (
            model is not None
            and len(item_history) >= 2
        ):

            prediction_data = pd.DataFrame({

                "item_id": [
                    item["item_id"]
                ],

                "day_of_week": [
                    prediction_day_of_week
                ]

            })

            predicted_demand = float(
                model.predict(
                    prediction_data
                )[0]
            )

            if predicted_demand < 0:

                predicted_demand = 0

            prediction_available = True

        # =================================================
        # INVENTORY DECISION
        # =================================================

        if not prediction_available:

            inventory_status = (
                "Insufficient Historical Data"
            )

        elif current_stock == 0:

            inventory_status = (
                "Out of Stock"
            )

        elif current_stock < predicted_demand:

            inventory_status = (
                "Reorder Required"
            )

        else:

            inventory_status = (
                "Sufficient Stock"
            )

        # =================================================
        # SUGGESTED REORDER
        # =================================================

        if (
            prediction_available
            and current_stock < predicted_demand
        ):

            suggested_reorder = max(

                1,

                round(
                    predicted_demand
                    - current_stock
                )

            )

        inventory_data.append({

            "item_id":
                item["item_id"],

            "item_name":
                item["item_name"],

            "category":
                item["category"],

            "price":
                item["price"],

            "stock_quantity":
                current_stock,

            "predicted_demand":
                predicted_demand,

            "prediction_available":
                prediction_available,

            "inventory_status":
                inventory_status,

            "suggested_reorder":
                suggested_reorder

        })

    cursor.close()
    conn.close()

    return render_template(

        "admin_inventory.html",

        items=inventory_data

    )


# =========================================================
# UPDATE STOCK
# =========================================================

@app.route(
    "/admin/inventory/<int:item_id>/update",
    methods=["GET", "POST"]
)
def update_stock(item_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT
            item_id,
            item_name,
            category,
            price,
            stock_quantity

        FROM items

        WHERE item_id = %s
        """,
        (item_id,)
    )

    item = cursor.fetchone()

    if not item:

        cursor.close()
        conn.close()

        return "Item not found", 404

    if request.method == "POST":

        new_stock = request.form.get(
            "stock_quantity"
        )

        try:

            new_stock = int(
                new_stock
            )

        except (
            TypeError,
            ValueError
        ):

            cursor.close()
            conn.close()

            return (
                "Invalid stock quantity",
                400
            )

        if new_stock < 0:

            cursor.close()
            conn.close()

            return (
                "Stock cannot be negative",
                400
            )

        cursor.execute(
            """
            UPDATE items

            SET stock_quantity = %s

            WHERE item_id = %s
            """,
            (
                new_stock,
                item_id
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin_inventory")
        )

    cursor.close()
    conn.close()

    return render_template(

        "update_stock.html",

        item=item

    )


# =========================================================
# SALES REPORTS
# =========================================================

@app.route("/admin/reports")
def admin_reports():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # PAGINATION
    # =====================================================

    date_page = get_positive_int(
        request.args.get(
            "date_page",
            1
        )
    )

    per_page = 10

    # =====================================================
    # OVERALL SALES SUMMARY
    # =====================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_sales_count,

            COALESCE(
                SUM(total_sale),
                0
            ) AS total_sales,

            COALESCE(
                AVG(total_sale),
                0
            ) AS average_sale

        FROM sales
        """
    )

    summary = cursor.fetchone()

    # =====================================================
    # TOTAL SALES DATES
    # =====================================================

    cursor.execute(
        """
        SELECT COUNT(*) AS total_dates

        FROM
        (
            SELECT DATE(sale_date)

            FROM sales

            GROUP BY DATE(sale_date)

        ) AS date_groups
        """
    )

    total_dates = cursor.fetchone()[
        "total_dates"
    ]

    total_pages = max(
        1,
        (
            total_dates
            + per_page
            - 1
        )
        // per_page
    )

    if date_page > total_pages:

        date_page = total_pages

    offset = (
        date_page - 1
    ) * per_page

    # =====================================================
    # SALES BY DATE
    # =====================================================

    cursor.execute(
        """
        SELECT
            DATE(sale_date) AS sale_date,

            COUNT(*) AS sales_count,

            COALESCE(
                SUM(total_sale),
                0
            ) AS daily_sales

        FROM sales

        GROUP BY DATE(sale_date)

        ORDER BY sale_date DESC

        LIMIT %s OFFSET %s
        """,
        (
            per_page,
            offset
        )
    )

    daily_sales = cursor.fetchall()

    # =====================================================
    # RECENT SALES
    # =====================================================

    cursor.execute(
        """
        SELECT
            sale_id,
            order_id,
            total_sale,
            sale_date

        FROM sales

        ORDER BY sale_date DESC

        LIMIT 10
        """
    )

    recent_sales = cursor.fetchall()

    # =====================================================
    # BEST-SELLING ITEMS
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,

            SUM(
                oi.quantity
            ) AS quantity_sold,

            SUM(
                oi.subtotal
            ) AS revenue

        FROM order_item oi

        JOIN orders o
            ON oi.order_id = o.order_id

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE o.order_status = 'Completed'

        GROUP BY
            i.item_id,
            i.item_name

        ORDER BY
            quantity_sold DESC

        LIMIT 5
        """
    )

    best_selling_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin_reports.html",

        summary=summary,

        daily_sales=daily_sales,

        recent_sales=recent_sales,

        best_selling_items=
            best_selling_items,

        date_page=date_page,

        total_pages=total_pages

    )


# =========================================================
# CUSTOMER INSIGHTS
# =========================================================

@app.route("/admin/customers")
def admin_customers():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "admin":

        return "Access denied", 403

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    # =====================================================
    # CUSTOMER PURCHASE SUMMARY
    # =====================================================

    cursor.execute(
        """
        SELECT
            u.user_id,
            u.username,
            u.email,

            COUNT(
                DISTINCT o.order_id
            ) AS total_orders,

            COALESCE(
                SUM(o.total_amount),
                0
            ) AS total_spent

        FROM users u

        LEFT JOIN orders o
            ON u.user_id = o.user_id

        WHERE u.role = 'user'

        GROUP BY
            u.user_id,
            u.username,
            u.email

        ORDER BY
            total_spent DESC
        """
    )

    customers = cursor.fetchall()

    # =====================================================
    # CUSTOMER SPENDING LEVEL
    # =====================================================

    for customer in customers:

        if customer[
            "total_spent"
        ] >= 1000:

            customer[
                "spending_level"
            ] = "High Spender"

        elif customer[
            "total_spent"
        ] >= 500:

            customer[
                "spending_level"
            ] = "Medium Spender"

        else:

            customer[
                "spending_level"
            ] = "Low Spender"

    # =====================================================
    # CUSTOMER SUMMARY
    # =====================================================

    total_customers = len(
        customers
    )

    total_orders = sum(

        customer[
            "total_orders"
        ]

        for customer in customers

    )

    total_revenue = sum(

        float(
            customer[
                "total_spent"
            ]
        )

        for customer in customers

    )

    # =====================================================
    # TOP CUSTOMER
    # =====================================================

    top_customer = (

        customers[0]

        if customers

        else None

    )

    # =====================================================
    # TOP CUSTOMER FAVORITE ITEM
    # =====================================================

    favorite_item = None

    if (
        top_customer
        and top_customer[
            "total_orders"
        ] > 0
    ):

        cursor.execute(
            """
            SELECT
                i.item_name,

                SUM(
                    oi.quantity
                ) AS quantity_ordered

            FROM orders o

            JOIN order_item oi
                ON o.order_id = oi.order_id

            JOIN items i
                ON oi.item_id = i.item_id

            WHERE o.user_id = %s

            GROUP BY
                i.item_id,
                i.item_name

            ORDER BY
                quantity_ordered DESC

            LIMIT 1
            """,
            (
                top_customer[
                    "user_id"
                ],
            )
        )

        favorite_item = cursor.fetchone()

    # =====================================================
    # MOST POPULAR ITEM
    # =====================================================

    cursor.execute(
        """
        SELECT
            i.item_name,

            SUM(
                oi.quantity
            ) AS total_quantity

        FROM order_item oi

        JOIN orders o
            ON oi.order_id = o.order_id

        JOIN items i
            ON oi.item_id = i.item_id

        WHERE o.order_status = 'Completed'

        GROUP BY
            i.item_id,
            i.item_name

        ORDER BY
            total_quantity DESC

        LIMIT 1
        """
    )

    popular_item = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(

        "admin_customers.html",

        customers=customers,

        total_customers=
            total_customers,

        total_orders=
            total_orders,

        total_revenue=
            total_revenue,

        top_customer=
            top_customer,

        favorite_item=
            favorite_item,

        popular_item=
            popular_item

    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )