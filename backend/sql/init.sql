-- Built-in retail database for AskDB. Loaded once, into a fresh Postgres volume.
-- The application connects as demo_reader, which can only SELECT.

CREATE DATABASE demo;

\c demo

CREATE TABLE regions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions (id),
    opened_on DATE NOT NULL
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    store_id INTEGER NOT NULL REFERENCES stores (id),
    hired_on DATE NOT NULL,
    salary NUMERIC(10, 2) NOT NULL
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions (id),
    joined_on DATE NOT NULL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories (id),
    unit_price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    store_id INTEGER NOT NULL REFERENCES stores (id),
    employee_id INTEGER NOT NULL REFERENCES employees (id),
    ordered_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('paid', 'refunded', 'pending'))
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders (id),
    product_id INTEGER NOT NULL REFERENCES products (id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);

INSERT INTO regions (id, name) VALUES
    (1, 'North'),
    (2, 'South'),
    (3, 'West'),
    (4, 'East');

INSERT INTO stores (id, name, city, region_id, opened_on) VALUES
    (1, 'Harbor Market', 'Portland', 1, '2018-04-12'),
    (2, 'Harbor Market', 'Austin', 2, '2019-09-01'),
    (3, 'Harbor Market', 'Denver', 3, '2021-02-14'),
    (4, 'Harbor Outlet', 'Boston', 4, '2022-06-30');

INSERT INTO employees (id, name, role, store_id, hired_on, salary) VALUES
    (1, 'Ava Shah', 'Manager', 1, '2019-01-15', 82000),
    (2, 'Noah Patel', 'Associate', 1, '2022-03-01', 48000),
    (3, 'Mia Chen', 'Manager', 2, '2020-05-20', 79000),
    (4, 'Liam Ortiz', 'Associate', 2, '2023-07-11', 45000),
    (5, 'Emma Brooks', 'Manager', 3, '2021-03-02', 81000),
    (6, 'Sofia Nguyen', 'Associate', 3, '2024-01-08', 47000),
    (7, 'Ethan Clark', 'Manager', 4, '2022-07-01', 77000),
    (8, 'Isla Romero', 'Associate', 4, '2024-11-19', 46000);

INSERT INTO customers (id, name, email, city, region_id, joined_on) VALUES
    (1, 'Priya Nair', 'priya@example.com', 'Portland', 1, '2023-02-11'),
    (2, 'Jonah Ellis', 'jonah@example.com', 'Austin', 2, '2024-06-02'),
    (3, 'Helena Cho', 'helena@example.com', 'Denver', 3, '2022-11-19'),
    (4, 'Marcus Bell', 'marcus@example.com', 'Boston', 4, '2025-01-09'),
    (5, 'Amira Hassan', 'amira@example.com', 'Portland', 1, '2024-09-14'),
    (6, 'Diego Alvarez', 'diego@example.com', 'Austin', 2, '2023-12-01'),
    (7, 'Freya Lind', 'freya@example.com', 'Denver', 3, '2025-03-22'),
    (8, 'Chris Dalton', 'chris@example.com', 'Boston', 4, '2021-08-30'),
    (9, 'Nina Kapoor', 'nina@example.com', 'Portland', 1, '2026-01-17'),
    (10, 'Owen Blake', 'owen@example.com', 'Austin', 2, '2026-04-03');

INSERT INTO categories (id, name) VALUES
    (1, 'Coffee'),
    (2, 'Tea'),
    (3, 'Gear');

INSERT INTO products (id, name, category_id, unit_price, stock) VALUES
    (1, 'House Blend', 1, 14.00, 120),
    (2, 'Espresso Roast', 1, 16.50, 80),
    (3, 'Earl Grey', 2, 12.00, 60),
    (4, 'Jasmine Pearls', 2, 18.00, 15),
    (5, 'Ceramic Mug', 3, 22.00, 40),
    (6, 'Travel Tumbler', 3, 28.00, 8),
    (7, 'Pour Over Kit', 3, 42.00, 25),
    (8, 'Decaf Blend', 1, 15.00, 18);

INSERT INTO orders (id, customer_id, store_id, employee_id, ordered_at, status) VALUES
    (1, 1, 1, 2, '2025-11-03 10:15', 'paid'),
    (2, 2, 2, 4, '2025-12-12 14:40', 'paid'),
    (3, 3, 3, 6, '2026-01-08 09:05', 'paid'),
    (4, 4, 4, 8, '2026-01-21 16:22', 'refunded'),
    (5, 5, 1, 1, '2026-02-14 11:18', 'paid'),
    (6, 6, 2, 3, '2026-03-02 13:47', 'paid'),
    (7, 7, 3, 5, '2026-03-19 15:03', 'paid'),
    (8, 8, 4, 7, '2026-04-11 12:11', 'pending'),
    (9, 9, 1, 2, '2026-05-06 08:44', 'paid'),
    (10, 1, 1, 1, '2026-06-18 17:26', 'paid'),
    (11, 2, 2, 4, '2026-07-09 10:52', 'paid'),
    (12, 10, 2, 3, '2026-08-01 18:09', 'paid'),
    (13, 3, 3, 6, '2026-08-22 11:33', 'paid'),
    (14, 5, 1, 2, '2026-09-15 09:58', 'paid'),
    (15, 6, 2, 4, '2026-10-02 14:14', 'paid'),
    (16, 7, 3, 5, '2026-10-18 16:41', 'paid'),
    (17, 4, 4, 8, '2026-10-20 13:05', 'pending'),
    (18, 9, 1, 1, '2026-10-21 19:27', 'paid');

INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 2, 14.00),
    (2, 1, 5, 1, 22.00),
    (3, 2, 2, 1, 16.50),
    (4, 2, 3, 2, 12.00),
    (5, 3, 4, 1, 18.00),
    (6, 3, 6, 1, 28.00),
    (7, 4, 7, 1, 42.00),
    (8, 5, 1, 3, 14.00),
    (9, 5, 8, 1, 15.00),
    (10, 6, 2, 2, 16.50),
    (11, 6, 5, 2, 22.00),
    (12, 7, 3, 1, 12.00),
    (13, 7, 7, 1, 42.00),
    (14, 8, 6, 1, 28.00),
    (15, 9, 1, 1, 14.00),
    (16, 9, 4, 1, 18.00),
    (17, 10, 2, 4, 16.50),
    (18, 11, 8, 2, 15.00),
    (19, 11, 5, 1, 22.00),
    (20, 12, 1, 2, 14.00),
    (21, 12, 3, 1, 12.00),
    (22, 13, 7, 1, 42.00),
    (23, 13, 6, 1, 28.00),
    (24, 14, 1, 5, 14.00),
    (25, 15, 2, 2, 16.50),
    (26, 15, 4, 1, 18.00),
    (27, 16, 5, 3, 22.00),
    (28, 16, 8, 1, 15.00),
    (29, 17, 6, 1, 28.00),
    (30, 18, 1, 2, 14.00),
    (31, 18, 7, 1, 42.00);

CREATE ROLE demo_reader LOGIN PASSWORD 'demo_reader_pass';

REVOKE ALL ON DATABASE demo FROM PUBLIC;
GRANT CONNECT ON DATABASE demo TO demo_reader;
GRANT USAGE ON SCHEMA public TO demo_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO demo_reader;
