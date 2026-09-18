import mysql.connector
import pandas as pd

from datetime import date, timedelta

from sklearn.linear_model import LinearRegression
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Anshu@123",
    "database": "smart_cafe"
}


# =========================================================
# GET HISTORICAL SALES DATA
# =========================================================

def get_sales_data():

    conn = mysql.connector.connect(**DB_CONFIG)

    query = """
        SELECT
            i.item_id,
            i.item_name,
            DATE(o.order_date) AS order_date,
            SUM(oi.quantity) AS quantity_sold
        FROM orders o
        JOIN order_item oi
            ON o.order_id = oi.order_id
        JOIN items i
            ON oi.item_id = i.item_id
        WHERE o.order_status = 'Completed'
        GROUP BY
            i.item_id,
            i.item_name,
            DATE(o.order_date)
        ORDER BY
            order_date,
            i.item_id
    """

    data = pd.read_sql(query, conn)

    conn.close()

    return data


# =========================================================
# GET ALL CURRENT MENU ITEMS
# =========================================================

def get_all_items():

    conn = mysql.connector.connect(**DB_CONFIG)

    query = """
        SELECT
            item_id,
            item_name
        FROM items
        ORDER BY item_name
    """

    data = pd.read_sql(query, conn)

    conn.close()

    return data


# =========================================================
# TRAIN DEMAND MODEL
# =========================================================

def train_demand_model(data):

    # -----------------------------------------------------
    # Input features
    # -----------------------------------------------------

    X = data[
        [
            "item_id",
            "day_of_week"
        ]
    ]

    # -----------------------------------------------------
    # Target
    # -----------------------------------------------------

    y = data["quantity_sold"]

    # -----------------------------------------------------
    # Convert item_id into separate categories
    # -----------------------------------------------------

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "item",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
                ["item_id"]
            )
        ],
        remainder="passthrough"
    )

    # -----------------------------------------------------
    # Create ML pipeline
    # -----------------------------------------------------

    model = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor
            ),
            (
                "regressor",
                LinearRegression()
            )
        ]
    )

    # -----------------------------------------------------
    # Train model
    # -----------------------------------------------------

    model.fit(X, y)

    return model


# =========================================================
# GET FUTURE PREDICTION DATE
# =========================================================

def get_prediction_date():

    # Predict demand for tomorrow.
    prediction_date = date.today() + timedelta(days=1)

    return prediction_date


# =========================================================
# PREDICT DEMAND FOR ALL CURRENT MENU ITEMS
# =========================================================

def predict_all_items_demand():

    # -----------------------------------------------------
    # Get historical sales data
    # -----------------------------------------------------

    sales_data = get_sales_data()

    # -----------------------------------------------------
    # Get all current menu items
    # -----------------------------------------------------

    all_items = get_all_items()

    # -----------------------------------------------------
    # If there is no historical data
    # -----------------------------------------------------

    if sales_data.empty:

        return pd.DataFrame({
            "item_id": all_items["item_id"],
            "item_name": all_items["item_name"],
            "predicted_demand": [None] * len(all_items),
            "prediction_available": [False] * len(all_items)
        })

    # -----------------------------------------------------
    # Prepare historical data
    # -----------------------------------------------------

    sales_data["order_date"] = pd.to_datetime(
        sales_data["order_date"]
    )

    sales_data["day_of_week"] = (
        sales_data["order_date"].dt.dayofweek
    )

    # -----------------------------------------------------
    # Get future prediction date
    # -----------------------------------------------------

    prediction_date = get_prediction_date()

    prediction_day_of_week = (
        prediction_date.weekday()
    )

    # -----------------------------------------------------
    # Train model
    # -----------------------------------------------------

    model = train_demand_model(
        sales_data
    )

    prediction_results = []

    # -----------------------------------------------------
    # Predict for every current menu item
    # -----------------------------------------------------

    for _, item in all_items.iterrows():

        item_id = int(
            item["item_id"]
        )

        # -------------------------------------------------
        # Historical records for this item
        # -------------------------------------------------

        item_history = sales_data[
            sales_data["item_id"] == item_id
        ]

        # -------------------------------------------------
        # Minimum 2 historical records required
        # -------------------------------------------------

        if len(item_history) >= 2:

            prediction_data = pd.DataFrame({
                "item_id": [item_id],
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
            # Demand cannot be negative
            # -------------------------------------------------

            if predicted_demand < 0:
                predicted_demand = 0

            prediction_available = True

        else:

            predicted_demand = None
            prediction_available = False

        prediction_results.append({

            "item_id": item_id,

            "item_name": item["item_name"],

            "predicted_demand": predicted_demand,

            "prediction_available":
                prediction_available

        })

    return pd.DataFrame(
        prediction_results
    )


# =========================================================
# TEST / RUN DIRECTLY
# =========================================================

if __name__ == "__main__":

    print(
        "Getting historical sales data..."
    )

    sales_data = get_sales_data()

    if sales_data.empty:

        print(
            "\nNo completed sales data available."
        )

    else:

        sales_data["order_date"] = pd.to_datetime(
            sales_data["order_date"]
        )

        sales_data["day_of_week"] = (
            sales_data["order_date"].dt.dayofweek
        )

        print(
            "\nPrepared ML Data:"
        )

        print(
            sales_data
        )

        model = train_demand_model(
            sales_data
        )

        print(
            "\nML model trained successfully."
        )

    # -----------------------------------------------------
    # Prediction date
    # -----------------------------------------------------

    prediction_date = get_prediction_date()

    print(
        "\nPrediction date:",
        prediction_date
    )

    print(
        "Prediction day:",
        prediction_date.strftime("%A")
    )

    # -----------------------------------------------------
    # Predict demand
    # -----------------------------------------------------

    print(
        "\nPredicting demand for all current menu items..."
    )

    results = predict_all_items_demand()

    print(
        "\nDemand Prediction Results:"
    )

    for _, row in results.iterrows():

        if row["prediction_available"]:

            print(
                f"{row['item_name']}: "
                f"{row['predicted_demand']:.2f} units"
            )

        else:

            print(
                f"{row['item_name']}: "
                "Insufficient Historical Data"
            )