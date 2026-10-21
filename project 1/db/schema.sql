-- ERP System Database Schema
-- Project: ERP for Tailoring and Suits Factory

-- 1. Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(100),
    address TEXT,
    credit_limit DECIMAL(15, 2) DEFAULT 0,
    current_balance DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Raw Materials
CREATE TABLE IF NOT EXISTS raw_materials (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100), -- (Fabrics, Buttons, Lining, etc.)
    unit VARCHAR(20) NOT NULL, -- (Meter, Piece, Roll)
    cost_price DECIMAL(15, 2) DEFAULT 0, -- Weighted Average Cost
    reorder_point DECIMAL(15, 2) DEFAULT 0,
    supplier_id INTEGER REFERENCES suppliers(id),
    stock_level DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    address TEXT,
    shoulder_size DECIMAL(5, 2),
    chest_size DECIMAL(5, 2),
    waist_size DECIMAL(5, 2),
    length_size DECIMAL(5, 2),
    notes TEXT,
    balance DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Products (Ready Suits or Custom Designs)
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE,
    category VARCHAR(100), -- Ready/Custom
    base_price DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Bill of Materials (BOM)
CREATE TABLE IF NOT EXISTS bom (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    material_id INTEGER REFERENCES raw_materials(id),
    quantity DECIMAL(10, 3) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Invoices
CREATE TYPE invoice_status AS ENUM ('proforma', 'confirmed', 'delivered', 'cancelled');
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    total_amount DECIMAL(15, 2) NOT NULL,
    paid_amount DECIMAL(15, 2) DEFAULT 0,
    status invoice_status DEFAULT 'proforma',
    is_taxable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Production Orders
CREATE TYPE production_status AS ENUM ('pending', 'cutting', 'sewing', 'fitting', 'finishing', 'ironing', 'completed');
CREATE TABLE IF NOT EXISTS production_orders (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    product_id INTEGER REFERENCES products(id),
    status production_status DEFAULT 'pending',
    start_date DATE,
    end_date DATE,
    assigned_worker_id INTEGER, -- Link to Employees table later
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Treasury Transactions
CREATE TYPE transaction_type AS ENUM ('income', 'expense');
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    type transaction_type NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    category VARCHAR(100), -- (Sales, Purchase, Salary, Rent)
    description TEXT,
    related_invoice_id INTEGER REFERENCES invoices(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
