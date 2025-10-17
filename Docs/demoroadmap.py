import pandas as pd

# Define roadmap as structured milestones
roadmap = [
    {"Phase": "1. Planning & Architecture", "Task": "Requirements Gathering", "Status": "✅ Completed", "Est. Time (hrs)": 10},
    {"Phase": "1. Planning & Architecture", "Task": "Tech Stack & Architecture Design", "Status": "✅ Completed", "Est. Time (hrs)": 15},
    {"Phase": "2. Backend Foundation", "Task": "Django Project + App Scaffolding", "Status": "✅ Completed", "Est. Time (hrs)": 20},
    {"Phase": "2. Backend Foundation", "Task": "Custom User Model, Role System", "Status": "✅ Completed", "Est. Time (hrs)": 40},
    {"Phase": "3. ERP Module Development", "Task": "Accounting Module (FiscalYear, CostCenter)", "Status": "✅ Completed", "Est. Time (hrs)": 120},
    {"Phase": "3. ERP Module Development", "Task": "User Management (Signup, Login, Roles)", "Status": "✅ Completed", "Est. Time (hrs)": 60},
    {"Phase": "3. ERP Module Development", "Task": "Multi-Tenant Middleware", "Status": "✅ Completed", "Est. Time (hrs)": 60},
    {"Phase": "4. Frontend & Templates", "Task": "Admin Layout, Sidebar, Theming", "Status": "✅ Completed", "Est. Time (hrs)": 100},
    {"Phase": "4. Frontend & Templates", "Task": "Form Templates & Static Assets", "Status": "✅ Completed", "Est. Time (hrs)": 100},
    {"Phase": "5. API Layer", "Task": "Django REST Framework Integration", "Status": "✅ Completed", "Est. Time (hrs)": 80},
    {"Phase": "6. DevOps", "Task": "Settings, Environment, Static Files Setup", "Status": "✅ Completed", "Est. Time (hrs)": 40},
    {"Phase": "6. DevOps", "Task": "Local + Prod Config for SQL Server", "Status": "✅ Completed", "Est. Time (hrs)": 20},
    {"Phase": "7. Docs & QA", "Task": "README, Contribution Guide, Usage", "Status": "✅ Completed", "Est. Time (hrs)": 40},
    {"Phase": "7. Docs & QA", "Task": "Testing & Bug Fixing", "Status": "🟡 Partial", "Est. Time (hrs)": 40},
    {"Phase": "8. Finalization & Hardening", "Task": "API Documentation (Swagger/ReDoc)", "Status": "🟥 Not Started", "Est. Time (hrs)": 20},
    {"Phase": "8. Finalization & Hardening", "Task": "Security Audit, Permissions QA", "Status": "🟥 Not Started", "Est. Time (hrs)": 30},
    {"Phase": "8. Finalization & Hardening", "Task": "CI/CD Pipeline Setup", "Status": "🟥 Not Started", "Est. Time (hrs)": 30},
    {"Phase": "9. Optional Expansion", "Task": "CRM, HRM, Inventory Modules", "Status": "🟥 Not Started", "Est. Time (hrs)": 120}
]

df_roadmap = pd.DataFrame(roadmap)
import ace_tools as tools; tools.display_dataframe_to_user(name="ERP Project Roadmap", dataframe=df_roadmap)

