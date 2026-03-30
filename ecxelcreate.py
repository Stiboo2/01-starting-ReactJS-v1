import pandas as pd

# Employee data
employees = pd.DataFrame({
    'Employee ID': ['EMP-001', 'EMP-002', 'EMP-003', 'EMP-004', 'EMP-005'],
    'Name': ['Zara Chen', 'Marcus Velez', 'Priya Kapoor', 'Liam O\'Connor', 'Yuki Tanaka'],
    'Department': ['Quantum Computing', 'AI Ethics', 'Neural Interfaces', 'Biotech Integration', 'Quantum Computing'],
    'Position': ['Lead Researcher', 'Compliance Officer', 'Hardware Engineer', 'Scientist', 'Junior Researcher'],
    'Salary': [187500, 142300, 165200, 178900, 98400],
    'Start Date': ['2024-01-15', '2024-02-01', '2024-01-22', '2024-03-10', '2024-04-05'],
    'Office Location': ['Seattle Lab B', 'Virtual', 'Austin Hub 3', 'Boston R&D', 'Seattle Lab B']
})
employees.to_excel('Backend/knowledge-base/employees/employee_records.xlsx', index=False)

# Products data
products = pd.DataFrame({
    'SKU': ['QU-001', 'QU-002', 'QU-003', 'QU-004', 'QU-005'],
    'Product Name': ['Quantum Processor Q7', 'Neural Interface N3', 'AI Ethics Framework v2', 'Biotech Sensor Array', 'Quantum Cooling Unit'],
    'Category': ['Hardware', 'Wearables', 'Software', 'Medical', 'Hardware'],
    'Stock': [12, 47, 234, 8, 23],
    'Reorder Level': [5, 20, 100, 10, 8],
    'Unit Price': [3450, 899, 0, 12750, 2100],
    'Supplier Code': ['SUPP-QC-01', 'SUPP-NI-02', 'Internal', 'SUPP-BIO-03', 'SUPP-QC-02']
})
products.to_excel('Backend/knowledge-base/products/inventory_2024.xlsx', index=False)

# Customers data
customers = pd.DataFrame({
    'Client ID': ['CL-1001', 'CL-1002', 'CL-1003', 'CL-1004', 'CL-1005'],
    'Company': ['NovaTech Solutions', 'Greenfield Energy', 'BioSynth Labs', 'DeepMind AI Research', 'Arctic Computing'],
    'Industry': ['Aerospace', 'Clean Tech', 'Healthcare', 'AI/ML', 'Data Centers'],
    'Contract Value': [450000, 280000, 625000, 890000, 175000],
    'Renewal Date': ['2025-01-20', '2024-12-15', '2025-03-01', '2025-02-10', '2024-11-30'],
    'Account Manager': ['Sarah Chen', 'Marcus Velez', 'Priya Kapoor', 'Zara Chen', 'Liam O\'Connor'],
    'Priority Level': ['Platinum', 'Gold', 'Platinum', 'Platinum', 'Silver']
})
customers.to_excel('Backend/knowledge-base/customers/enterprise_clients.xlsx', index=False)

print("All Excel files created successfully!")