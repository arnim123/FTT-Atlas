"""Catalog copied from the front-end mock data.

Documents are the first 25 entries in frontend/src/mocks/documents.ts, in the same order.
The user roster is one account per role plus the indexer bot; seed.py remaps the other mock owners.
"""

# code, name, description
DEPARTMENTS: list[tuple[str, str, str]] = [
    ("product", "Product", "Product strategy, design, and documentation"),
    ("engineering", "Engineering", "Technical guides, architecture, and integrations"),
    ("hr", "People & Culture", "People, policies, and everything in between"),
    ("sales", "Sales", "Resources to build better customer relationships"),
    ("operations", "Operations", "Processes that keep the company moving"),
]

# key, name, email, role, department code, is_bot, last_seen
USERS: list[tuple[str, str, str, str, str, bool, str]] = [
    ("u1", "Alex Morgan", "alex.morgan@company.com", "super_admin", "product", False, "2026-11-15T09:00:00Z"),
    ("u2", "Sarah Chen", "sarah.chen@company.com", "admin", "hr", False, "2026-11-15T08:45:00Z"),
    ("u3", "James Wilson", "james.wilson@company.com", "manager", "product", False, "2026-11-15T08:30:00Z"),
    ("u4", "Emma Davis", "emma.davis@company.com", "employee", "product", False, "2026-11-15T08:15:00Z"),
    ("u5", "Noah Williams", "noah@partner.co", "guest", "sales", False, "2026-11-14T13:10:00Z"),
    ("u13", "Atlas Indexer", "atlas.indexer@company.com", "employee", "engineering", True, "2026-11-15T11:20:00Z"),
]

# Mock owners that are not in the reduced roster, pointed at the seeded account for that department.
OWNER_REMAP: dict[str, str] = {
    "u1": "u1",
    "u2": "u2",
    "u3": "u3",
    "u4": "u4",
    "u5": "u5",
    "u6": "u2",
    "u7": "u13",
    "u8": "u5",
    "u9": "u3",
    "u10": "u4",
    "u13": "u13",
}

# key, name, parent key, department code. Parents are listed before their children.
FOLDERS: list[tuple[str, str, str | None, str]] = [
    ("root", "Company Knowledge", None, "product"),
    ("hr", "HR", "root", "hr"),
    ("policies", "Policies", "hr", "hr"),
    ("leave", "Leave Rules", "hr", "hr"),
    ("recruitment", "Recruitment", "hr", "hr"),
    ("products", "Products", "root", "product"),
    ("erp", "ERP Lens", "products", "product"),
    ("erp-manual", "User Manual", "erp", "product"),
    ("erp-features", "Features", "erp", "product"),
    ("erp-faq", "FAQs", "erp", "product"),
    ("chatbot", "AI Chatbot", "products", "engineering"),
    ("chatbot-setup", "Setup Guide", "chatbot", "engineering"),
    ("chatbot-integration", "Integration Docs", "chatbot", "engineering"),
    ("chatbot-troubleshooting", "Troubleshooting", "chatbot", "engineering"),
    ("sales", "Sales", "root", "sales"),
    ("pitch", "Pitch Decks", "sales", "sales"),
    ("pricing", "Pricing", "sales", "sales"),
    ("proposals", "Proposals", "sales", "sales"),
    ("operations", "Operations", "root", "operations"),
    ("processes", "Processes", "operations", "operations"),
    ("reports", "Reports", "operations", "operations"),
]

DEPARTMENT_FOLDERS = {"recruitment", "pricing", "reports"}

# Folder owner in the UI mock, before OWNER_REMAP.
FOLDER_OWNER_BY_DEPARTMENT = {
    "product": "u3",
    "hr": "u2",
    "engineering": "u7",
    "sales": "u8",
    "operations": "u9",
}

# key, name, description
CATEGORIES: list[tuple[str, str, str]] = [
    ("manual", "User manuals", "Step-by-step product documentation"),
    ("policy", "Policies", "Company guidelines and policies"),
    ("guide", "Guides & tutorials", "Practical instructions and learning resources"),
    ("sop", "Standard procedures", "Repeatable operational processes"),
    ("template", "Templates", "Ready-to-use starting points"),
    ("report", "Reports", "Insights, metrics, and analysis"),
]

TAG_NAMES = [
    "Getting started",
    "ERP Lens",
    "Inventory",
    "Internal",
    "Onboarding",
    "AI Chatbot",
    "Process",
    "Q4 2026",
    "Customer-facing",
    "Security",
    "Sales enablement",
    "Benefits",
]

# name, ui source type, folder key, department code, owner key, category key, tags
DOCUMENTS: list[tuple[str, str, str, str, str, str, list[str]]] = [
    ("ERP Lens Inventory Manual", "google-doc", "erp-manual", "product", "u3", "manual", ["ERP Lens", "Inventory", "Getting started"]),
    ("Employee Handbook 2026", "pdf", "policies", "hr", "u2", "policy", ["Onboarding", "Internal"]),
    ("Q4 Sales Playbook", "google-slide", "pitch", "sales", "u8", "guide", ["Sales enablement", "Q4 2026"]),
    ("AI Chatbot Integration Guide", "google-doc", "chatbot-integration", "engineering", "u7", "guide", ["AI Chatbot", "Getting started"]),
    ("Product Roadmap · Q4 2026", "google-sheet", "erp-features", "product", "u1", "report", ["ERP Lens", "Q4 2026"]),
    ("Inventory SOP", "docx", "processes", "operations", "u9", "sop", ["Inventory", "Process"]),
    ("Warehouse Process Guide", "pdf", "processes", "operations", "u10", "guide", ["Inventory", "Process"]),
    ("Remote Work Policy", "google-doc", "policies", "hr", "u2", "policy", ["Internal", "Benefits"]),
    ("Leave & Holiday Guidelines", "pdf", "leave", "hr", "u6", "policy", ["Benefits", "Internal"]),
    ("New Hire Onboarding Checklist", "google-sheet", "recruitment", "hr", "u2", "template", ["Onboarding", "Getting started"]),
    ("ERP Lens Quick Start", "pdf", "erp-manual", "product", "u4", "manual", ["ERP Lens", "Getting started"]),
    ("ERP Lens Feature Overview", "google-slide", "erp-features", "product", "u3", "guide", ["ERP Lens", "Customer-facing"]),
    ("ERP Lens Frequently Asked Questions", "google-doc", "erp-faq", "product", "u4", "guide", ["ERP Lens", "Customer-facing"]),
    ("AI Chatbot Setup Checklist", "google-doc", "chatbot-setup", "engineering", "u7", "guide", ["AI Chatbot", "Getting started"]),
    ("API Authentication Reference", "pdf", "chatbot-integration", "engineering", "u7", "manual", ["AI Chatbot", "Security"]),
    ("Chatbot Troubleshooting Runbook", "google-doc", "chatbot-troubleshooting", "engineering", "u7", "sop", ["AI Chatbot", "Process"]),
    ("Company Overview Deck", "ppt", "pitch", "sales", "u8", "template", ["Sales enablement", "Customer-facing"]),
    ("Enterprise Pricing Matrix", "xlsx", "pricing", "sales", "u8", "report", ["Sales enablement", "Internal"]),
    ("Customer Proposal Template", "docx", "proposals", "sales", "u8", "template", ["Customer-facing", "Sales enablement"]),
    ("Brand & Visual Guidelines", "pdf", "products", "product", "u4", "guide", ["Internal", "Getting started"]),
    ("Design System Overview", "image", "erp-features", "product", "u4", "guide", ["ERP Lens", "Internal"]),
    ("Incident Response Plan", "google-doc", "chatbot-troubleshooting", "engineering", "u7", "sop", ["Security", "Process"]),
    ("Data Security Policy", "pdf", "policies", "hr", "u2", "policy", ["Security", "Internal"]),
    ("Recruitment Interview Kit", "docx", "recruitment", "hr", "u6", "template", ["Onboarding", "Internal"]),
    ("Benefits at a Glance", "google-slide", "leave", "hr", "u6", "guide", ["Benefits", "Onboarding"]),
]
