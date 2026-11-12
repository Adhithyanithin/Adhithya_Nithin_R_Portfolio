-- Requires MySQL 8.0.16+ (CHECK constraints are enforced)
CREATE DATABASE IF NOT EXISTS smart_inventory;
USE smart_inventory;

CREATE TABLE suppliers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),
  email VARCHAR(100)
);
CREATE TABLE products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(30) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  supplier_id INT NULL,
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
  stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
  reorder_level INT NOT NULL DEFAULT 10,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);
CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),
  email VARCHAR(100)
);
CREATE TABLE orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  total DECIMAL(10,2) NOT NULL,
  status ENUM('Completed','Cancelled') NOT NULL DEFAULT 'Completed',
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
CREATE TABLE order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL CHECK (quantity > 0),
  unit_price DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE inventory_transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  change_qty INT NOT NULL,
  type ENUM('SALE','RESTOCK','ADJUST','RETURN') NOT NULL,
  note VARCHAR(200),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Sample data
INSERT INTO suppliers (name, phone, email) VALUES
 ('Sample Traders', '9000000001', 'traders@example.com'),
 ('Demo Wholesale', '9000000002', 'wholesale@example.com');
INSERT INTO products (sku, name, supplier_id, price, stock, reorder_level) VALUES
 ('PEN-001', 'Ball Pen (Blue)', 1, 10.00, 120, 30),
 ('NBK-001', 'Notebook A5', 1, 45.00, 40, 15),
 ('STP-001', 'Stapler', 2, 85.00, 12, 10),
 ('MRK-001', 'Marker Set', 2, 150.00, 8, 10),
 ('FLD-001', 'File Folder', 1, 25.00, 60, 20);
INSERT INTO customers (name, phone, email) VALUES
 ('Sample Customer', '9000000010', 'customer@example.com'),
 ('Demo Customer', '9000000011', 'demo@example.com');
