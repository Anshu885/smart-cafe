-- ============================================================
-- SMART CAFE INTELLIGENCE SYSTEM
-- Database: smart_cafe
-- ============================================================

CREATE DATABASE IF NOT EXISTS smart_cafe;

USE smart_cafe;


-- ============================================================
-- USERS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS users (

    user_id INT PRIMARY KEY AUTO_INCREMENT,

    username VARCHAR(50) NOT NULL,

    email VARCHAR(100) UNIQUE NOT NULL,

    password VARCHAR(255) NOT NULL,

    role VARCHAR(20) DEFAULT 'user'

);


-- ============================================================
-- ITEMS / MENU TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS items (

    item_id INT PRIMARY KEY AUTO_INCREMENT,

    item_name VARCHAR(100) NOT NULL,

    category VARCHAR(50) NOT NULL,

    price DECIMAL(10,2) NOT NULL,

    stock_quantity INT DEFAULT 0

);


-- ============================================================
-- ORDERS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (

    order_id INT PRIMARY KEY AUTO_INCREMENT,

    user_id INT NOT NULL,

    total_amount DECIMAL(10,2) NOT NULL,

    order_status VARCHAR(30) DEFAULT 'Pending',

    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)

);


-- ============================================================
-- ORDER ITEM TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS order_item (

    order_item_id INT PRIMARY KEY AUTO_INCREMENT,

    order_id INT NOT NULL,

    item_id INT NOT NULL,

    quantity INT NOT NULL,

    subtotal DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    FOREIGN KEY (item_id)
        REFERENCES items(item_id)

);


-- ============================================================
-- SALES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS sales (

    sale_id INT PRIMARY KEY AUTO_INCREMENT,

    order_id INT NOT NULL,

    total_sale DECIMAL(10,2) NOT NULL,

    sale_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id)

);


-- ============================================================
-- SMART CAFE MENU
-- TOTAL: 29 ITEMS
-- ============================================================


-- ----------------------------
-- BEVERAGES
-- ----------------------------

INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Masala Tea',
'Beverage',
70.00,
0

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Masala Tea'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Cold Coffee',
'Beverage',
140.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Cold Coffee'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Hot Chocolate',
'Beverage',
150.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Hot Chocolate'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Hazelnut Iced Latte',
'Beverage',
170.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Hazelnut Iced Latte'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Mango Cheesecake Shake',
'Beverage',
210.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Mango Cheesecake Shake'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Oreo Mint Shake',
'Beverage',
180.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Oreo Mint Shake'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Virgin Mojito',
'Beverage',
130.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Virgin Mojito'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Peach Iced Tea',
'Beverage',
120.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Peach Iced Tea'
);


-- ----------------------------
-- COFFEE
-- ----------------------------

INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Cappuccino',
'Coffee',
120.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Cappuccino'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Espresso Shot',
'Coffee',
90.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Espresso Shot'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Caffè Latte',
'Coffee',
140.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Caffè Latte'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Signature Cold Brew',
'Coffee',
160.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Signature Cold Brew'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Caramel Macchiato',
'Coffee',
180.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Caramel Macchiato'
);


-- ----------------------------
-- DESSERTS
-- ----------------------------

INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Chocolate Brownie',
'Dessert',
90.00,
0

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Chocolate Brownie'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Lotus Biscoff Cheesecake Jar',
'Dessert',
220.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Lotus Biscoff Cheesecake Jar'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Classic Tiramisu',
'Dessert',
200.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Classic Tiramisu'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Blueberry Muffin',
'Dessert',
110.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Blueberry Muffin'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Cinnamon Roll',
'Dessert',
130.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Cinnamon Roll'
);


-- ----------------------------
-- SNACKS
-- ----------------------------

INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Veg Sandwich',
'Snacks',
100.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Veg Sandwich'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Paneer Tikka Grilled Sandwich',
'Snacks',
180.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Paneer Tikka Grilled Sandwich'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Peri-Peri French Fries',
'Snacks',
140.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Peri-Peri French Fries'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Garlic Cheese Toast',
'Snacks',
130.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Garlic Cheese Toast'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Loaded Cheese Nachos',
'Snacks',
190.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Loaded Cheese Nachos'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Truffle Mushroom Toast',
'Snacks',
220.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Truffle Mushroom Toast'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Cheese Corn Balls',
'Snacks',
160.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Cheese Corn Balls'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Pesto Veggie Wrap',
'Snacks',
180.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Pesto Veggie Wrap'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Chicken Tikka Wrap',
'Snacks',
210.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Chicken Tikka Wrap'
);


-- ----------------------------
-- BREAKFAST / MEAL
-- ----------------------------

INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Classic French Toast',
'Breakfast / Meal',
150.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Classic French Toast'
);


INSERT INTO items
(item_name, category, price, stock_quantity)

SELECT
'Masala Cheese Omelette',
'Breakfast / Meal',
130.00,
30

WHERE NOT EXISTS (
    SELECT 1
    FROM items
    WHERE item_name = 'Masala Cheese Omelette'
);


-- ============================================================
-- VERIFY MENU
-- ============================================================

SELECT
    item_id,
    category,
    item_name,
    price,
    stock_quantity
FROM items
ORDER BY item_id;