# Streamlit App
import streamlit as st
import tempfile
import os
import json
from main import LettaClient
import uuid
import datetime
import pathlib
import pandas as pd
import csv
import io
import shutil

st.set_page_config(page_title="LegalSphere", page_icon="⚖️", layout="wide")

# Directory to store conversation data files
DATA_DIR = 'user_data'
LOGS_DIR = 'audit_logs'
EXPORTS_DIR = 'exports'
CASES_DIR = 'cases'
SHARED_CASES_DIR = 'shared_cases'  # New directory for shared cases
CONFIG_DIR = 'config'
WORKFLOWS_DIR = 'workflows'  # New directory for workflow templates
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(CASES_DIR, exist_ok=True)
os.makedirs(SHARED_CASES_DIR, exist_ok=True)  # Create the shared cases directory
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(WORKFLOWS_DIR, exist_ok=True)  # Create the workflows directory

# Define default workflow templates
DEFAULT_WORKFLOWS = {
    "trade_dispute": {
        "name": "Trade Dispute Analysis",
        "description": "A workflow for analyzing international trade disputes",
        "stages": [
            {
                "id": "assessment",
                "name": "Initial Assessment",
                "description": "Gather facts and verify jurisdiction"
            },
            {
                "id": "research",
                "name": "Legal Research",
                "description": "Identify similar WTO cases and outcomes"
            },
            {
                "id": "strategy",
                "name": "Strategy Development",
                "description": "Prepare legal positions and resolution options"
            }
        ]
    },
    "wto_compliance": {
        "name": "WTO Compliance Check",
        "description": "A workflow for checking compliance with WTO regulations",
        "stages": [
            {
                "id": "review",
                "name": "Regulation Review",
                "description": "Identify applicable WTO agreements and provisions"
            },
            {
                "id": "analysis",
                "name": "Gap Analysis",
                "description": "Compare practices with WTO requirements"
            },
            {
                "id": "recommendations",
                "name": "Recommendations",
                "description": "Develop compliance recommendations"
            }
        ]
    }
}

# Create a default agent config if it doesn't exist
DEFAULT_AGENT_CONFIG = {
    "name": "Default Agent",
    "model": "anthropic/claude-3-haiku-20240307",
    "temperature": 0.7,
    "system_prompt": "You are a legal assistant specializing in international trade law and WTO regulations. Provide accurate and helpful information to assist legal professionals and clients with their inquiries.",
    "tools": []
}

agent_config_path = os.path.join(CONFIG_DIR, 'agent_config.json')
if not os.path.exists(agent_config_path):
    with open(agent_config_path, 'w') as f:
        json.dump(DEFAULT_AGENT_CONFIG, f, indent=2)

# RBAC user database (in-memory)
ROLES = {
    "admin": {
        "permissions": ["view_agents", "upload_documents", "chat", "view_reasoning", "view_logs", "manage_cases", "create_agents"]
    },
    "legal_advisor": {
        "permissions": ["view_agents", "upload_documents", "chat", "view_reasoning", "manage_cases", "create_agents"]
    },
    "client": {
        "permissions": ["view_agents", "chat", "manage_cases"]
    },
    "guest": {
        "permissions": ["chat"]
    }
}

# Sample users (in-memory database)
USERS = {
    "admin1": {"password": "admin123", "role": "admin"},
    "advisor1": {"password": "legal123", "role": "legal_advisor"},
    "client1": {"password": "client123", "role": "client"},
    "guest1": {"password": "guest123", "role": "guest"}
}

# Functions for conversation persistence
def get_conversation_file_path(username):
    """Get the file path for a user's conversation data"""
    safe_username = username.replace('/', '_').replace('\\', '_')
    return os.path.join(DATA_DIR, f"{safe_username}_conversations.json")

def save_conversations(username, conversations):
    """Save conversations to a JSON file"""
    try:
        file_path = get_conversation_file_path(username)
        with open(file_path, 'w') as f:
            json.dump(conversations, f)
    except Exception as e:
        st.error(f"Error saving conversations: {str(e)}")

def load_conversations(username):
    """Load conversations from a JSON file"""
    file_path = get_conversation_file_path(username)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading conversations: {str(e)}")
    return {}

# Case management functions
def get_case_file_path(username):
    """Get the file path for a user's cases data"""
    safe_username = username.replace('/', '_').replace('\\', '_')
    return os.path.join(CASES_DIR, f"{safe_username}_cases.json")

def get_shared_case_file_path():
    """Get the file path for shared cases between legal advisors and admin"""
    return os.path.join(SHARED_CASES_DIR, "shared_cases.json")

def save_cases(username, cases):
    """Save cases to a JSON file"""
    try:
        # Save to user's personal cases file
        file_path = get_case_file_path(username)
        with open(file_path, 'w') as f:
            json.dump(cases, f)
        
        # If user is a legal advisor, also save to the shared cases file
        if st.session_state.user_role == "legal_advisor":
            shared_file_path = get_shared_case_file_path()
            shared_cases = {}
            
            # Load existing shared cases if they exist
            if os.path.exists(shared_file_path):
                with open(shared_file_path, 'r') as f:
                    shared_cases = json.load(f)
            
            # Add this legal advisor's cases to the shared cases
            for case_id, case in cases.items():
                # Add creator information if it doesn't exist
                if "creator" not in case:
                    case["creator"] = username
                shared_cases[case_id] = case
            
            # Save the updated shared cases
            with open(shared_file_path, 'w') as f:
                json.dump(shared_cases, f)
        
        # If user is an admin, check if any of the cases are from legal advisors and update the shared file
        elif st.session_state.user_role == "admin":
            shared_file_path = get_shared_case_file_path()
            if os.path.exists(shared_file_path):
                try:
                    # Load shared cases
                    with open(shared_file_path, 'r') as f:
                        shared_cases = json.load(f)
                    
                    # Check each case the admin has
                    for case_id, case in cases.items():
                        # If this case exists in shared cases and has a creator that's not the admin
                        if case_id in shared_cases and "creator" in case and case["creator"] != username:
                            # Update the shared case with admin's changes, but keep original title and creator
                            original_title = shared_cases[case_id]["title"] if "title" in shared_cases[case_id] else case["title"]
                            original_creator = shared_cases[case_id]["creator"] if "creator" in shared_cases[case_id] else case["creator"]
                            
                            # Create a clean copy without the admin's display formatting
                            updated_case = case.copy()
                            if "title" in updated_case and " (by " in updated_case["title"]:
                                updated_case["title"] = original_title
                            
                            updated_case["creator"] = original_creator
                            shared_cases[case_id] = updated_case
                    
                    # Save the updated shared cases
                    with open(shared_file_path, 'w') as f:
                        json.dump(shared_cases, f)
                except Exception as e:
                    st.error(f"Error updating shared cases as admin: {str(e)}")
    except Exception as e:
        st.error(f"Error saving cases: {str(e)}")

def load_cases(username):
    """Load cases from a JSON file"""
    # Start with the user's personal cases
    user_cases = {}
    file_path = get_case_file_path(username)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                user_cases = json.load(f)
        except Exception as e:
            st.error(f"Error loading user cases: {str(e)}")
    
    # If user is an admin, also load shared cases from legal advisors
    if st.session_state.user_role == "admin":
        shared_file_path = get_shared_case_file_path()
        if os.path.exists(shared_file_path):
            try:
                with open(shared_file_path, 'r') as f:
                    shared_cases = json.load(f)
                
                # Add shared cases to the admin's view, but mark them as from legal advisors
                for case_id, case in shared_cases.items():
                    if case_id not in user_cases:  # Don't override admin's own cases with same ID
                        # Add a label to show it's from a legal advisor
                        if "creator" in case:
                            case["title"] = f"{case['title']} (by {case['creator']})"
                        else:
                            case["title"] = f"{case['title']} (shared)"
                        user_cases[case_id] = case
            except Exception as e:
                st.error(f"Error loading shared cases: {str(e)}")
    
    return user_cases

# Create new case
def create_new_case(title, agents=None):
    """Create a new legal case with the given title and optional pre-selected agents"""
    case_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    st.session_state.cases[case_id] = {
        "id": case_id,
        "title": title,
        "created_at": timestamp,
        "conversations": {},
        "agents": agents or [],
        "creator": st.session_state.username,
        "workflow": None  # Initialize with no workflow
    }
    
    # Save the updated cases
    if st.session_state.username:
        save_cases(st.session_state.username, st.session_state.cases)
    
    # Log the action
    log_user_action(st.session_state.username, "create_case", 
                    {"case_id": case_id, "title": title})
    
    return case_id

# Workflow management functions
def get_workflow_templates():
    """Get all available workflow templates"""
    # Load default templates
    templates = DEFAULT_WORKFLOWS.copy()
    
    # Check for custom templates in the WORKFLOWS_DIR
    for filename in os.listdir(WORKFLOWS_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(WORKFLOWS_DIR, filename), 'r') as f:
                    custom_template = json.load(f)
                    template_id = os.path.splitext(filename)[0]
                    templates[template_id] = custom_template
            except Exception as e:
                print(f"Error loading workflow template {filename}: {str(e)}")
    
    return templates

def assign_workflow_to_case(case_id, workflow_template_id):
    """Assign a workflow template to a case"""
    if case_id not in st.session_state.cases:
        return False
    
    templates = get_workflow_templates()
    if workflow_template_id not in templates:
        return False
    
    # Create a copy of the template for this case
    template = templates[workflow_template_id]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Initialize the workflow with stages from the template
    workflow = {
        "template_id": workflow_template_id,
        "name": template["name"],
        "description": template["description"],
        "assigned_at": timestamp,
        "current_stage_index": 0,  # Start at the first stage
        "stages": []
    }
    
    # Copy stages from template and initialize their status
    for stage in template["stages"]:
        workflow["stages"].append({
            "id": stage["id"],
            "name": stage["name"],
            "description": stage["description"],
            "status": "not_started",  # Options: not_started, in_progress, completed
            "start_date": None,
            "completion_date": None,
            "notes": ""
        })
    
    # Set the first stage to in_progress
    if workflow["stages"]:
        workflow["stages"][0]["status"] = "in_progress"
        workflow["stages"][0]["start_date"] = timestamp
    
    # Assign the workflow to the case
    st.session_state.cases[case_id]["workflow"] = workflow
    
    # Save the updated cases
    if st.session_state.username:
        save_cases(st.session_state.username, st.session_state.cases)
    
    # Log the action
    log_user_action(
        st.session_state.username, 
        "assign_workflow", 
        {
            "case_id": case_id,
            "workflow_name": template["name"],
            "template_id": workflow_template_id
        }
    )
    
    return True

def update_workflow_stage_status(case_id, stage_index, new_status):
    """Update the status of a workflow stage"""
    if case_id not in st.session_state.cases:
        return False
    
    case = st.session_state.cases[case_id]
    if not case.get("workflow") or "stages" not in case["workflow"]:
        return False
    
    workflow = case["workflow"]
    if stage_index < 0 or stage_index >= len(workflow["stages"]):
        return False
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage = workflow["stages"][stage_index]
    old_status = stage["status"]
    stage["status"] = new_status
    
    # Set appropriate dates
    if new_status == "in_progress" and not stage["start_date"]:
        stage["start_date"] = timestamp
    elif new_status == "completed" and not stage["completion_date"]:
        stage["completion_date"] = timestamp
    
    # If this stage is completed, move to the next stage
    if new_status == "completed" and stage_index < len(workflow["stages"]) - 1:
        workflow["current_stage_index"] = stage_index + 1
        # Set the next stage to in_progress
        next_stage = workflow["stages"][stage_index + 1]
        next_stage["status"] = "in_progress"
        next_stage["start_date"] = timestamp
    
    # Save the updated cases
    if st.session_state.username:
        save_cases(st.session_state.username, st.session_state.cases)
    
    # Log the action
    log_user_action(
        st.session_state.username, 
        "update_workflow_stage", 
        {
            "case_id": case_id,
            "stage_name": stage["name"],
            "old_status": old_status,
            "new_status": new_status
        }
    )
    
    return True

def update_workflow_stage_notes(case_id, stage_index, notes):
    """Update the notes for a workflow stage"""
    if case_id not in st.session_state.cases:
        return False
    
    case = st.session_state.cases[case_id]
    if not case.get("workflow") or "stages" not in case["workflow"]:
        return False
    
    workflow = case["workflow"]
    if stage_index < 0 or stage_index >= len(workflow["stages"]):
        return False
    
    stage = workflow["stages"][stage_index]
    stage["notes"] = notes
    
    # Save the updated cases
    if st.session_state.username:
        save_cases(st.session_state.username, st.session_state.cases)
    
    return True

# Create new conversation within a case
def create_case_conversation(case_id, title=None, agent_id=None):
    """Create a new conversation within a case"""
    conversation_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not title:
        case_conversations = st.session_state.cases[case_id]["conversations"]
        title = f"Conversation {len(case_conversations) + 1}"
    
    st.session_state.cases[case_id]["conversations"][conversation_id] = {
        "id": conversation_id,
        "title": title,
        "created_at": timestamp,
        "messages": [],
        "agent_id": agent_id
    }
    
    # Save the updated cases
    if st.session_state.username:
        save_cases(st.session_state.username, st.session_state.cases)
    
    # Log the action
    log_user_action(st.session_state.username, "create_case_conversation", 
                    {"case_id": case_id, "conversation_id": conversation_id, "title": title})
    
    return conversation_id

# Audit logging functions
def log_user_action(username, action, details=None):
    """Log a user action to the audit log file"""
    if not username:
        return
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "username": username,
        "role": st.session_state.get("user_role", "unknown"),
        "action": action,
        "details": details or {},
        "ip_address": "127.0.0.1"  # In a real app, you'd get the actual IP
    }
    
    log_file = os.path.join(LOGS_DIR, "user_activity.log")
    
    try:
        # Load existing logs
        existing_logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                existing_logs = json.load(f)
        
        # Add new log entry
        existing_logs.append(log_entry)
        
        # Save updated logs
        with open(log_file, 'w') as f:
            json.dump(existing_logs, f, indent=2)
    except Exception as e:
        print(f"Error logging user action: {str(e)}")

def get_audit_logs():
    """Get all audit logs"""
    log_file = os.path.join(LOGS_DIR, "user_activity.log")
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error reading audit logs: {str(e)}")
    return []

# Export functions for conversation history
def export_conversations_to_txt(username, conversations):
    """Export all conversations to a txt file"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = os.path.join(EXPORTS_DIR, f"{username}_conversations_{timestamp}.txt")
    
    try:
        with open(export_path, 'w', encoding='utf-8') as f:
            for conv_id, conv in conversations.items():
                f.write(f"Conversation: {conv['title']}\n")
                f.write(f"Created: {conv['created_at']}\n")
                f.write(f"ID: {conv['id']}\n\n")
                f.write("Messages:\n")
                
                for msg in conv['messages']:
                    f.write(f"[{msg['role'].upper()}]: {msg['content']}\n")
                    if 'reasoning' in msg and msg['reasoning']:
                        f.write(f"[REASONING]: {msg['reasoning']}\n")
                    f.write("\n")
                
                f.write("-" * 50 + "\n\n")
        
        return export_path
    except Exception as e:
        print(f"Error exporting conversations to TXT: {str(e)}")
        return None

def export_conversations_to_csv(username, conversations):
    """Export all conversations to a CSV file"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = os.path.join(EXPORTS_DIR, f"{username}_conversations_{timestamp}.csv")
    
    try:
        with open(export_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Conversation ID', 'Title', 'Created At', 'Role', 'Message', 'Reasoning'])
            
            for conv_id, conv in conversations.items():
                for msg in conv['messages']:
                    writer.writerow([
                        conv['id'],
                        conv['title'],
                        conv['created_at'],
                        msg['role'],
                        msg['content'],
                        msg.get('reasoning', '')
                    ])
        
        return export_path
    except Exception as e:
        print(f"Error exporting conversations to CSV: {str(e)}")
        return None

def export_conversations_to_pdf(username, conversations):
    """Export all conversations to a PDF file"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = os.path.join(EXPORTS_DIR, f"{username}_conversations_{timestamp}.pdf")
    
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", size=12)
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"LegalSphere Conversation Export - {username}", 0, 1, 'C')
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, 'C')
        pdf.ln(10)
        
        # Add conversations
        for conv_id, conv in conversations.items():
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, f"Conversation: {conv['title']}", 0, 1)
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 5, f"Created: {conv['created_at']}", 0, 1)
            pdf.cell(0, 5, f"ID: {conv['id']}", 0, 1)
            pdf.ln(5)
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "Messages:", 0, 1)
            
            for msg in conv['messages']:
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(0, 5, f"{msg['role'].upper()}:", 0, 1)
                pdf.set_font("Arial", size=10)
                
                # Handle multi-line text for content
                pdf.multi_cell(0, 5, msg['content'])
                
                if 'reasoning' in msg and msg['reasoning']:
                    pdf.ln(2)
                    pdf.set_font("Arial", 'I', 8)
                    pdf.cell(0, 5, "Reasoning:", 0, 1)
                    pdf.multi_cell(0, 5, msg['reasoning'])
                
                pdf.ln(5)
            
            pdf.ln(10)
            pdf.cell(0, 0, "_" * 150, 0, 1)
            pdf.ln(10)
            
            # Add a new page if not the last conversation
            if list(conversations.keys()).index(conv_id) < len(conversations) - 1:
                pdf.add_page()
        
        pdf.output(export_path)
        return export_path
    except Exception as e:
        print(f"Error exporting conversations to PDF: {str(e)}")
        return None

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'client' not in st.session_state:
    st.session_state.client = LettaClient()
if 'selected_agent' not in st.session_state:
    st.session_state.selected_agent = None
if 'conversations' not in st.session_state:
    st.session_state.conversations = {}
if 'active_conversation' not in st.session_state:
    st.session_state.active_conversation = None
if 'show_logs' not in st.session_state:
    st.session_state.show_logs = False
if 'show_conversation_export' not in st.session_state:
    st.session_state.show_conversation_export = False
if 'cases' not in st.session_state:
    st.session_state.cases = {}
if 'active_case' not in st.session_state:
    st.session_state.active_case = None
if 'case_conversation' not in st.session_state:
    st.session_state.case_conversation = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "normal"  # Options: "normal" or "case"

# Authentication function
def authenticate(username, password):
    if username in USERS and USERS[username]["password"] == password:
        st.session_state.authenticated = True
        st.session_state.user_role = USERS[username]["role"]
        st.session_state.username = username
        
        # Load user's conversations
        st.session_state.conversations = load_conversations(username)
        
        # Load user's cases
        st.session_state.cases = load_cases(username)
        
        # Log the login action
        log_user_action(username, "login", {"role": USERS[username]["role"]})
        
        return True
    return False

# Check permission function
def has_permission(permission):
    if not st.session_state.authenticated:
        return False
    role = st.session_state.user_role
    return permission in ROLES.get(role, {}).get("permissions", [])

# Create new conversation
def create_new_conversation(title=None):
    conversation_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not title:
        title = f"Conversation {len(st.session_state.conversations) + 1}"
    
    st.session_state.conversations[conversation_id] = {
        "id": conversation_id,
        "title": title,
        "created_at": timestamp,
        "messages": [],
        "agent_id": st.session_state.selected_agent
    }
    
    # Save the updated conversations
    if st.session_state.username:
        save_conversations(st.session_state.username, st.session_state.conversations)
    
    # Log the action
    log_user_action(st.session_state.username, "create_conversation", 
                    {"conversation_id": conversation_id, "title": title})
    
    return conversation_id

# Login screen
if not st.session_state.authenticated:
    st.title("LegalSphere: Legal AI Assistant")
    st.subheader("Login")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")
        
        if login_button:
            if authenticate(username, password):
                st.success(f"Logged in as {username} with role: {st.session_state.user_role}")
                st.rerun()
            else:
                st.error("Invalid username or password")
                # Log failed login attempt
                log_user_action(username, "failed_login", {"reason": "Invalid credentials"})
    
    with col2:
        st.info("Demo Accounts:")
        st.markdown("- Admin: admin1/admin123")
        st.markdown("- Legal Advisor: advisor1/legal123")  
        st.markdown("- Client: client1/client123")
        st.markdown("- Guest: guest1/guest123")
        
        st.markdown("---")
        st.markdown("**Role Permissions:**")
        st.markdown("- **Admin**: All access + Audit Logs")
        st.markdown("- **Legal Advisor**: Full system access")
        st.markdown("- **Client**: View agents and chat")
        st.markdown("- **Guest**: Chat only")

else:
    # App header
    st.title("LegalSphere: Legal AI Assistant")
    st.subheader("International Trade Law & WTO Regulations")
    
    # User info and logout in top right
    col1, col2 = st.columns([3, 1])
    with col2:
        st.info(f"Logged in as: {st.session_state.user_role.upper()}")
        
        if st.button("Logout"):
            # Log the logout action
            log_user_action(st.session_state.username, "logout")
            
            # Save conversations before logout
            if st.session_state.username:
                save_conversations(st.session_state.username, st.session_state.conversations)
                save_cases(st.session_state.username, st.session_state.cases)
            
            # Clear session state
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.username = None
            st.session_state.conversations = {}
            st.session_state.active_conversation = None
            st.session_state.cases = {}
            st.session_state.active_case = None
            st.session_state.case_conversation = None
            st.session_state.view_mode = "normal"
            st.session_state.show_logs = False
            st.session_state.show_conversation_export = False
            st.rerun()

    # Admin-only section for logs
    if has_permission("view_logs"):
        st.sidebar.markdown("---")
        st.sidebar.subheader("Admin Tools")
        
        if st.sidebar.checkbox("Show Audit Logs", value=st.session_state.show_logs):
            st.session_state.show_logs = True
        else:
            st.session_state.show_logs = False
    
    # If admin wants to see logs, show them instead of the main interface
    if st.session_state.show_logs and has_permission("view_logs"):
        st.header("System Audit Logs")
        
        # Add tabs for Audit Logs and Conversation Export
        tab1, tab2 = st.tabs(["Audit Logs", "Conversation Export"])
        
        with tab1:
            # Add filtering options
            col1, col2, col3 = st.columns(3)
            with col1:
                username_filter = st.text_input("Filter by username:")
            with col2:
                action_options = ["All Actions", "login", "logout", "create_conversation", 
                                  "delete_conversation", "send_message", "upload_document", "failed_login"]
                action_filter = st.selectbox("Filter by action:", action_options)
            with col3:
                date_filter = st.date_input("Filter by date:", datetime.datetime.now())
            
            # Get the logs
            logs = get_audit_logs()
            
            # Apply filters
            filtered_logs = logs
            if username_filter:
                filtered_logs = [log for log in filtered_logs if username_filter.lower() in log["username"].lower()]
            if action_filter != "All Actions":
                filtered_logs = [log for log in filtered_logs if log["action"] == action_filter]
            
            date_str = date_filter.strftime("%Y-%m-%d")
            filtered_logs = [log for log in filtered_logs if log["timestamp"].startswith(date_str)]
            
            # Display the logs in a table
            if filtered_logs:
                st.write(f"Showing {len(filtered_logs)} log entries")
                
                # Create a dataframe for better display
                log_data = []
                for log in filtered_logs:
                    log_data.append({
                        "Timestamp": log["timestamp"],
                        "User": log["username"],
                        "Role": log["role"],
                        "Action": log["action"],
                        "Details": str(log["details"])
                    })
                
                st.table(log_data)
                
                # Export option
                if st.button("Export Logs as JSON"):
                    export_path = os.path.join(LOGS_DIR, f"exported_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                    with open(export_path, 'w') as f:
                        json.dump(filtered_logs, f, indent=2)
                    st.success(f"Logs exported to {export_path}")
            else:
                st.info("No logs match your filter criteria")
        
        with tab2:
            st.header("Export Conversation History")
            
            # User selection
            user_data_files = [f for f in os.listdir(DATA_DIR) if f.endswith('_conversations.json')]
            available_users = [f.split('_conversations.json')[0] for f in user_data_files]
            
            if available_users:
                selected_user = st.selectbox("Select user to export conversations:", available_users)
                
                if selected_user:
                    # Load the selected user's conversations
                    user_conversations = load_conversations(selected_user)
                    
                    if user_conversations:
                        st.write(f"Found {len(user_conversations)} conversations for user {selected_user}")
                        
                        # Show conversation list with checkboxes for selection
                        selected_convs = {}
                        st.write("Select conversations to export:")
                        select_all = st.checkbox("Select All")
                        
                        for conv_id, conv in user_conversations.items():
                            is_selected = select_all or st.checkbox(
                                f"{conv['title']} ({len(conv['messages'])} messages, created {conv['created_at']})",
                                key=f"export_{conv_id}"
                            )
                            if is_selected:
                                selected_convs[conv_id] = conv
                        
                        # Export format selection
                        export_format = st.radio(
                            "Select export format:",
                            ["TXT", "CSV", "PDF"]
                        )
                        
                        if st.button("Export Selected Conversations") and selected_convs:
                            export_path = None
                            
                            with st.spinner(f"Exporting {len(selected_convs)} conversations as {export_format}..."):
                                if export_format == "TXT":
                                    export_path = export_conversations_to_txt(selected_user, selected_convs)
                                elif export_format == "CSV":
                                    export_path = export_conversations_to_csv(selected_user, selected_convs)
                                elif export_format == "PDF":
                                    export_path = export_conversations_to_pdf(selected_user, selected_convs)
                            
                            if export_path:
                                st.success(f"Export successful! File saved to: {export_path}")
                                
                                # Create a download button
                                with open(export_path, "rb") as file:
                                    btn = st.download_button(
                                        label=f"Download {export_format} File",
                                        data=file,
                                        file_name=os.path.basename(export_path),
                                        mime="application/octet-stream"
                                    )
                                
                                # Log the export action
                                log_user_action(
                                    st.session_state.username,
                                    "export_conversations",
                                    {
                                        "target_user": selected_user,
                                        "format": export_format,
                                        "conversation_count": len(selected_convs)
                                    }
                                )
                            else:
                                st.error("Failed to export conversations. Check the logs for details.")
                    else:
                        st.info(f"No conversations found for user {selected_user}")
            else:
                st.info("No user conversation data found in the system.")

    else:
        # Regular app interface (when not viewing logs)
        # Sidebar for agent selection, conversation management, and document upload
        with st.sidebar:
            st.header("Configuration")
            
            # Tab-based sidebar for normal view and case management
            sidebar_tabs = st.tabs(["Regular Chat", "Cases"])
            
            with sidebar_tabs[0]:
                # Agent Selection
                if has_permission("view_agents"):
                    st.subheader("Select Agent")
                    
                    # Agent Creation UI
                    if has_permission("create_agents"):
                        with st.expander("Create New Agent"):
                            new_agent_name = st.text_input("Agent Name", key="new_agent_name_regular")
                            new_agent_persona = st.text_area("Agent Persona", 
                                placeholder="Enter a description of the agent's persona, expertise, and personality.", 
                                key="new_agent_persona_regular", 
                                height=150)
                            if st.button("Create Agent", key="create_agent_regular"):
                                try:
                                    with st.spinner("Creating new agent..."):
                                        # Create agent using the client
                                        new_agent = st.session_state.client.create_agent(new_agent_name, new_agent_persona)
                                        
                                        # Log the action
                                        log_user_action(
                                            st.session_state.username, 
                                            "create_agent", 
                                            {"agent_name": new_agent_name, "agent_id": new_agent.get('id')}
                                        )
                                        
                                        # Set as selected agent
                                        st.session_state.selected_agent = new_agent.get('id')
                                        
                                        st.success(f"Created new agent: {new_agent_name}")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error creating agent: {str(e)}")
                    
                    # Agent Selection UI
                    try:
                        agents = st.session_state.client.list_agents()
                        if agents:
                            agent_names = [f"{agent.get('name', 'Unnamed Agent')} ({agent['id']})" for agent in agents]
                            selected_agent_index = st.selectbox("Choose an agent:", range(len(agent_names)), format_func=lambda i: agent_names[i])
                            st.session_state.selected_agent = agents[selected_agent_index]['id']
                            
                            # Show agent details and delete option
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"Selected: {agents[selected_agent_index].get('name', 'Unnamed Agent')}")
                            with col2:
                                if st.button("🗑️ Delete", key="delete_agent_btn"):
                                    try:
                                        with st.spinner("Deleting agent..."):
                                            # Delete the agent
                                            st.session_state.client.delete_agent(agents[selected_agent_index]['id'])
                                            
                                            # Log the action
                                            log_user_action(
                                                st.session_state.username, 
                                                "delete_agent", 
                                                {
                                                    "agent_name": agents[selected_agent_index].get('name', 'Unnamed Agent'),
                                                    "agent_id": agents[selected_agent_index]['id']
                                                }
                                            )
                                            
                                            # If this was the selected agent, clear the selection
                                            if st.session_state.selected_agent == agents[selected_agent_index]['id']:
                                                st.session_state.selected_agent = None
                                            
                                            st.success(f"Deleted agent: {agents[selected_agent_index].get('name', 'Unnamed Agent')}")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting agent: {str(e)}")
                        else:
                            st.error("No agents found. Please create one.")
                    except Exception as e:
                        st.error(f"Error loading agents: {str(e)}")
                        st.session_state.selected_agent = None
                else:
                    # For users without agent selection permission, auto-select first agent if available
                    try:
                        agents = st.session_state.client.list_agents()
                        if agents:
                            st.session_state.selected_agent = agents[0]['id']
                    except Exception:
                        st.session_state.selected_agent = None

                # Conversation Management
                st.subheader("Conversations")
                
                # Create new conversation button
                if st.session_state.selected_agent:
                    new_conv_title = st.text_input("New conversation title (optional)")
                    if st.button("Start New Conversation", key="sidebar_new_conv_btn"):
                        new_conv_id = create_new_conversation(new_conv_title)
                        st.session_state.active_conversation = new_conv_id
                        st.session_state.view_mode = "normal"
                        st.rerun()
                
                # List all conversations for selection
                if st.session_state.conversations:
                    st.write("Your conversations:")
                    
                    # Sort conversations by creation date (newest first)
                    sorted_conversations = sorted(
                        st.session_state.conversations.items(),
                        key=lambda x: x[1].get('created_at', ''),
                        reverse=True
                    )
                    
                    for conv_id, conv in sorted_conversations:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            if st.button(f"{conv['title']}", key=f"select_{conv_id}"):
                                st.session_state.active_conversation = conv_id
                                st.session_state.view_mode = "normal"
                                st.rerun()
                        
                        with col2:
                            if st.button("🗑️", key=f"delete_{conv_id}"):
                                # Log the deletion
                                log_user_action(
                                    st.session_state.username, 
                                    "delete_conversation", 
                                    {"conversation_id": conv_id, "title": conv["title"]}
                                )
                                
                                # Delete the conversation
                                del st.session_state.conversations[conv_id]
                                
                                # Save the updated conversations
                                save_conversations(st.session_state.username, st.session_state.conversations)
                                
                                if st.session_state.active_conversation == conv_id:
                                    st.session_state.active_conversation = None
                                st.rerun()
                else:
                    st.info("No conversations yet. Start a new one!")
            
            with sidebar_tabs[1]:
                if has_permission("manage_cases"):
                    st.subheader("Case Management")
                    
                    # Add a note for admins
                    if st.session_state.user_role == "admin":
                        st.info("As an admin, you can view and manage all cases, including those created by legal advisors.")
                    
                    # Create new case
                    new_case_title = st.text_input("New case name", key="new_case_name")
                    
                    # Option to create a new agent specifically for this case
                    create_new_case_agent = st.checkbox("Create new agent for this case", key="create_new_case_agent")
                    new_case_agent_name = None
                    new_case_agent_persona = None
                    
                    if create_new_case_agent and has_permission("create_agents"):
                        new_case_agent_name = st.text_input("New agent name", key="new_case_agent_name")
                        new_case_agent_persona = st.text_area("Agent Persona", 
                            placeholder="Enter a description of the agent's persona, expertise, and personality.", 
                            key="new_case_agent_persona", 
                            height=150)
                    
                    # Agent selection for case (optional)
                    case_agents = []
                    if has_permission("view_agents"):
                        try:
                            agents = st.session_state.client.list_agents()
                            if agents:
                                st.write("Preselect agents for this case (optional):")
                                for agent in agents:
                                    agent_name = agent.get('name', f"Agent {agent['id']}")
                                    if st.checkbox(f"{agent_name}", key=f"case_agent_{agent['id']}"):
                                        case_agents.append(agent['id'])
                        except Exception as e:
                            st.error(f"Error loading agents for case: {str(e)}")
                    
                    # Document upload for case creation
                    if has_permission("upload_documents"):
                        st.write("Upload initial documents for this case (optional):")
                        new_case_files = st.file_uploader(
                            "Choose documents",
                            type=["pdf", "txt", "docx", "doc", "rtf", "png", "jpg", "jpeg"],
                            accept_multiple_files=True,
                            key="new_case_document_uploader"
                        )
                    else:
                        new_case_files = []
                    
                    if st.button("Create New Case") and new_case_title:
                        # First create a new agent if requested
                        if create_new_case_agent and new_case_agent_name and has_permission("create_agents"):
                            try:
                                with st.spinner("Creating new agent for case..."):
                                    # Create agent using the client
                                    new_agent = st.session_state.client.create_agent(new_case_agent_name, new_case_agent_persona)
                                    new_agent_id = new_agent.get('id')
                                    
                                    # Add to the case agents
                                    case_agents.append(new_agent_id)
                                    
                                    # Log the action
                                    log_user_action(
                                        st.session_state.username, 
                                        "create_agent_for_new_case", 
                                        {"agent_name": new_case_agent_name, "agent_id": new_agent_id}
                                    )
                                    
                                    st.success(f"Created new agent: {new_case_agent_name}")
                            except Exception as e:
                                st.error(f"Error creating agent: {str(e)}")
                                # Continue with case creation even if agent creation fails
                        
                        # Create the case
                        new_case_id = create_new_case(new_case_title, case_agents)
                        
                        # Handle document uploads if any
                        if new_case_files and has_permission("upload_documents"):
                            # Create a documents directory for cases if it doesn't exist
                            case_docs_dir = os.path.join(CASES_DIR, "documents")
                            os.makedirs(case_docs_dir, exist_ok=True)
                            
                            # Create case-specific directory
                            case_specific_dir = os.path.join(case_docs_dir, new_case_id)
                            os.makedirs(case_specific_dir, exist_ok=True)
                            
                            # Initialize documents list if not exists
                            if "documents" not in st.session_state.cases[new_case_id]:
                                st.session_state.cases[new_case_id]["documents"] = []
                            
                            # Process each file
                            for uploaded_file in new_case_files:
                                # Create unique filename (timestamp + original name)
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"{timestamp}_{uploaded_file.name}"
                                file_path = os.path.join(case_specific_dir, filename)
                                
                                # Save the file
                                with open(file_path, 'wb') as f:
                                    f.write(uploaded_file.getvalue())
                                
                                # Add to case documents list
                                st.session_state.cases[new_case_id]["documents"].append({
                                    "id": str(uuid.uuid4()),
                                    "name": uploaded_file.name,
                                    "filename": filename,
                                    "uploaded_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "uploaded_by": st.session_state.username,
                                    "file_path": file_path,
                                    "size": uploaded_file.size,
                                    "type": uploaded_file.type,
                                })
                                
                                # Log the document upload
                                log_user_action(
                                    st.session_state.username, 
                                    "upload_document_during_case_creation", 
                                    {
                                        "case_id": new_case_id,
                                        "filename": uploaded_file.name,
                                        "file_size": uploaded_file.size
                                    }
                                )
                            
                            # Save the updated cases
                            save_cases(st.session_state.username, st.session_state.cases)
                        
                        st.session_state.active_case = new_case_id
                        st.session_state.view_mode = "case"
                        st.success(f"Created new case: {new_case_title}")
                        st.rerun()
                    
                    # List all cases
                    if st.session_state.cases:
                        st.write("Your cases:")
                        
                        # Sort cases by creation date (newest first)
                        sorted_cases = sorted(
                            st.session_state.cases.items(),
                            key=lambda x: x[1].get('created_at', ''),
                            reverse=True
                        )
                        
                        for case_id, case in sorted_cases:
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                # Add workflow indicator if case has a workflow
                                case_title = case['title']
                                if case.get('workflow'):
                                    # Calculate workflow progress
                                    workflow = case['workflow']
                                    total_stages = len(workflow['stages'])
                                    completed_stages = sum(1 for stage in workflow['stages'] if stage['status'] == 'completed')
                                    progress_pct = int((completed_stages / total_stages) * 100) if total_stages > 0 else 0
                                    current_stage = workflow['stages'][workflow['current_stage_index']]
                                    
                                    # Add emoji and progress to case title
                                    status_emoji = {
                                        "not_started": "⚪",
                                        "in_progress": "🔵",
                                        "completed": "✅"
                                    }.get(current_stage['status'], "⚪")
                                    
                                    case_title = f"{case_title} {status_emoji} ({progress_pct}%)"
                                
                                if st.button(f"{case_title}", key=f"select_case_{case_id}"):
                                    st.session_state.active_case = case_id
                                    st.session_state.case_conversation = None  # Reset active conversation in the case
                                    st.session_state.view_mode = "case"
                                    st.rerun()
                            
                            with col2:
                                if st.button("🗑️", key=f"delete_case_{case_id}"):
                                    # Log the deletion
                                    log_user_action(
                                        st.session_state.username, 
                                        "delete_case", 
                                        {"case_id": case_id, "title": case["title"]}
                                    )
                                    
                                    # Delete the case
                                    del st.session_state.cases[case_id]
                                    
                                    # Save the updated cases
                                    save_cases(st.session_state.username, st.session_state.cases)
                                    
                                    # If this is a legal advisor, also remove from shared cases if exists
                                    if st.session_state.user_role == "legal_advisor":
                                        shared_file_path = get_shared_case_file_path()
                                        if os.path.exists(shared_file_path):
                                            try:
                                                # Load shared cases
                                                with open(shared_file_path, 'r') as f:
                                                    shared_cases = json.load(f)
                                                
                                                # Remove this case if it exists in shared cases
                                                if case_id in shared_cases:
                                                    del shared_cases[case_id]
                                                
                                                # Save the updated shared cases
                                                with open(shared_file_path, 'w') as f:
                                                    json.dump(shared_cases, f)
                                            except Exception as e:
                                                st.error(f"Error updating shared cases: {str(e)}")
                                    
                                    if st.session_state.active_case == case_id:
                                        st.session_state.active_case = None
                                        st.session_state.view_mode = "normal"
                                    st.rerun()
                    else:
                        st.info("No cases yet. Create a new one!")
                else:
                    st.info("You don't have permission to manage cases.")

            # Document Upload (shared between regular mode and case mode)
            if has_permission("upload_documents"):
                st.subheader("Upload Documents")
                uploaded_files = st.file_uploader("Choose documents", type=["pdf", "txt", "docx"], accept_multiple_files=True)

                if uploaded_files and (st.session_state.selected_agent or (st.session_state.view_mode == "case" and st.session_state.active_case)):
                    # Get sources attached to the selected agent
                    try:
                        agent_id = st.session_state.selected_agent
                        if st.session_state.view_mode == "case" and st.session_state.active_case:
                            # If in case view and a case is active, get the case's first agent or the selected agent
                            case_agents = st.session_state.cases[st.session_state.active_case].get("agents", [])
                            if case_agents:
                                agent_id = case_agents[0]  # Use the first agent in the case
                        
                        agent_sources = st.session_state.client.get_agent_sources(agent_id)
                        
                        if not agent_sources:
                            st.warning("No sources are attached to this agent. Please attach sources through the Letta Server UI.")
                        else:
                            # Create a dropdown to select which source to upload to
                            source_options = {source.get('name', f"Source {i}"): source['id'] for i, source in enumerate(agent_sources)}
                            selected_source_name = st.selectbox("Select source to upload to:", list(source_options.keys()))
                            selected_source_id = source_options[selected_source_name]
                            
                            if st.button("Upload Documents", key="upload_doc_btn"):
                                # Create a temporary directory for all files
                                temp_dir = tempfile.mkdtemp()
                                
                                try:
                                    # Process each file
                                    for uploaded_file in uploaded_files:
                                        st.write(f"Processing: {uploaded_file.name}")
                                        
                                        # Create a temporary file with the original filename
                                        temp_path = os.path.join(temp_dir, uploaded_file.name)
                                        
                                        # Write the file content
                                        with open(temp_path, 'wb') as f:
                                            f.write(uploaded_file.getvalue())
                                        
                                        # Upload file to the selected source
                                        st.session_state.client.upload_file_to_source(selected_source_id, temp_path)
                                        
                                        # Log the document upload
                                        log_user_action(
                                            st.session_state.username, 
                                            "upload_document", 
                                            {
                                                "filename": uploaded_file.name, 
                                                "source_id": selected_source_id,
                                                "source_name": selected_source_name
                                            }
                                        )
                                        
                                        st.success(f"Successfully uploaded: {uploaded_file.name}")
                                        
                                        # Clean up the individual temp file
                                        os.remove(temp_path)
                                    
                                    # Clean up the temp directory
                                    os.rmdir(temp_dir)
                                    
                                except Exception as e:
                                    st.error(f"Error processing documents: {str(e)}")
                                    # Clean up temp directory in case of error
                                    try:
                                        for file in os.listdir(temp_dir):
                                            os.remove(os.path.join(temp_dir, file))
                                        os.rmdir(temp_dir)
                                    except:
                                        pass
                    except Exception as e:
                        st.error(f"Error retrieving agent sources: {str(e)}")

        # Main chat interface
        if has_permission("chat"):
            # Switch between regular chat and case view modes
            if st.session_state.view_mode == "normal":
                # Check if there's an active conversation, otherwise show welcome message
                if st.session_state.active_conversation and st.session_state.active_conversation in st.session_state.conversations:
                    active_conv = st.session_state.conversations[st.session_state.active_conversation]
                    
                    # Show conversation title as header
                    st.header(f"Conversation: {active_conv['title']}")
                    
                    # Display chat messages for the active conversation
                    for message in active_conv['messages']:
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                            # Only show reasoning expander if reasoning exists and user has permission
                            if "reasoning" in message and message["reasoning"] and has_permission("view_reasoning"):
                                with st.expander("View Agent Reasoning"):
                                    st.markdown(message["reasoning"])

                    # Chat input for active conversation
                    prompt = st.chat_input("What would you like to know about international trade law?")
                    
                    if prompt:
                        # Get the agent ID for this conversation
                        agent_id = active_conv.get('agent_id', st.session_state.selected_agent)
                        
                        if not agent_id:
                            st.error("No agent selected for this conversation.")
                        else:
                            # Add user message to conversation
                            active_conv['messages'].append({"role": "user", "content": prompt})
                            
                            # Display user message
                            with st.chat_message("user"):
                                st.markdown(prompt)
                                
                            # Log the message send action
                            log_user_action(
                                st.session_state.username, 
                                "send_message", 
                                {
                                    "conversation_id": st.session_state.active_conversation,
                                    "conversation_title": active_conv["title"],
                                    "message": prompt[:50] + ("..." if len(prompt) > 50 else "")
                                }
                            )
                                
                            # Get agent response
                            with st.chat_message("assistant"):
                                with st.spinner("Thinking..."):
                                    try:
                                        response = st.session_state.client.send_message(
                                            agent_id, 
                                            prompt
                                        )
                                        
                                        # Extract content and reasoning if available
                                        content = ""
                                        reasoning = ""
                                        
                                        # Parse the Letta API response format
                                        if isinstance(response, dict) and "messages" in response:
                                            for msg in response["messages"]:
                                                if msg.get("message_type") == "reasoning_message":
                                                    reasoning = msg.get("reasoning", "")
                                                elif msg.get("message_type") == "assistant_message":
                                                    content = msg.get("content", "")
                                        
                                        # Display response
                                        st.markdown(content)
                                        
                                        # Display reasoning in an expander if user has permission
                                        if reasoning and has_permission("view_reasoning"):
                                            with st.expander("View Agent Reasoning"):
                                                st.markdown(reasoning)
                                        
                                        # Add to conversation history
                                        active_conv['messages'].append({
                                            "role": "assistant", 
                                            "content": content,
                                            "reasoning": reasoning
                                        })
                                        
                                        # Save the updated conversations
                                        save_conversations(st.session_state.username, st.session_state.conversations)
                                        
                                    except Exception as e:
                                        st.error(f"Error getting response: {str(e)}")
                else:
                    # Welcome message if no conversation is active
                    st.header("Welcome to LegalSphere")
                    st.write("Start a new conversation from the sidebar to begin chatting.")
                    
                    if not st.session_state.selected_agent:
                        st.warning("Please select an agent from the sidebar first.")
                    else:
                        # Offer a quick start button if an agent is selected
                        if st.button("Start New Conversation", key="main_new_conv_btn"):
                            new_conv_id = create_new_conversation("New Legal Consultation")
                            st.session_state.active_conversation = new_conv_id
                            st.rerun()
            
            # Case view mode
            elif st.session_state.view_mode == "case" and st.session_state.active_case:
                active_case = st.session_state.cases[st.session_state.active_case]
                
                # Show case details
                st.header(f"Case: {active_case['title']}")
                st.write(f"Created: {active_case['created_at']}")
                
                # Case management tabs
                case_tabs = st.tabs(["Conversations", "Agents", "Details", "Workflow"])
                
                # Conversations tab - manage conversations within this case
                with case_tabs[0]:
                    # Top-level columns for case conversation management
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader("Case Conversations")
                    
                    with col2:
                        # Create new conversation in the case
                        new_case_conv_title = st.text_input("New conversation title", key="new_case_conv_title")
                    
                    # Button to create a new conversation
                    if st.button("New Case Conversation") and st.session_state.active_case:
                        # Select an agent for this conversation
                        agent_id = None
                        case_agents = active_case.get("agents", [])
                        
                        # Use the first agent in the case's agent list if available, otherwise use the selected agent
                        if case_agents:
                            agent_id = case_agents[0]
                        elif st.session_state.selected_agent:
                            agent_id = st.session_state.selected_agent
                        
                        if agent_id:
                            # Create conversation within the case
                            conv_id = create_case_conversation(
                                st.session_state.active_case, 
                                new_case_conv_title or "New Discussion",
                                agent_id
                            )
                            st.session_state.case_conversation = conv_id
                            st.success("Created new case conversation")
                            st.rerun()
                        else:
                            st.error("No agent available for this conversation. Please add agents to the case or select one.")
                    
                    # List all conversations in this case
                    case_conversations = active_case.get("conversations", {})
                    
                    if case_conversations:
                        # Sort conversations by creation date (newest first)
                        sorted_case_convs = sorted(
                            case_conversations.items(),
                            key=lambda x: x[1].get('created_at', ''),
                            reverse=True
                        )
                        
                        # Show the conversations list
                        for conv_id, conv in sorted_case_convs:
                            conv_col1, conv_col2 = st.columns([3, 1])
                            
                            with conv_col1:
                                if st.button(f"{conv['title']}", key=f"case_conv_{conv_id}"):
                                    st.session_state.case_conversation = conv_id
                                    st.rerun()
                            
                            with conv_col2:
                                if st.button("🗑️", key=f"delete_case_conv_{conv_id}"):
                                    # Log the deletion
                                    log_user_action(
                                        st.session_state.username, 
                                        "delete_case_conversation", 
                                        {
                                            "case_id": st.session_state.active_case,
                                            "conversation_id": conv_id, 
                                            "title": conv["title"]
                                        }
                                    )
                                    
                                    # Delete the conversation from the case
                                    del active_case["conversations"][conv_id]
                                    
                                    # Save the updated cases
                                    save_cases(st.session_state.username, st.session_state.cases)
                                    
                                    if st.session_state.case_conversation == conv_id:
                                        st.session_state.case_conversation = None
                                    st.rerun()
                        
                        # Show active conversation if one is selected
                        if st.session_state.case_conversation and st.session_state.case_conversation in case_conversations:
                            active_conv = case_conversations[st.session_state.case_conversation]
                            
                            st.divider()
                            
                            # Show conversation title as header
                            st.subheader(f"Conversation: {active_conv['title']}")
                            
                            # Display chat messages for the active conversation
                            for message in active_conv['messages']:
                                with st.chat_message(message["role"]):
                                    st.markdown(message["content"])
                                    # Only show reasoning expander if reasoning exists and user has permission
                                    if "reasoning" in message and message["reasoning"] and has_permission("view_reasoning"):
                                        with st.expander("View Agent Reasoning"):
                                            st.markdown(message["reasoning"])

                            # Chat input for active conversation
                            case_prompt = st.chat_input("Type your message here...")
                            
                            if case_prompt:
                                # Get the agent ID for this conversation
                                agent_id = active_conv.get('agent_id')
                                
                                if not agent_id:
                                    # If no agent specified for this conversation, try to use a case agent or the selected agent
                                    case_agents = active_case.get("agents", [])
                                    if case_agents:
                                        agent_id = case_agents[0]
                                    else:
                                        agent_id = st.session_state.selected_agent
                                
                                if not agent_id:
                                    st.error("No agent selected for this conversation.")
                                else:
                                    # Add user message to conversation
                                    active_conv['messages'].append({"role": "user", "content": case_prompt})
                                    
                                    # Display user message
                                    with st.chat_message("user"):
                                        st.markdown(case_prompt)
                                            
                                    # Log the message send action
                                    log_user_action(
                                        st.session_state.username, 
                                        "send_case_message", 
                                        {
                                            "case_id": st.session_state.active_case,
                                            "conversation_id": st.session_state.case_conversation,
                                            "conversation_title": active_conv["title"],
                                            "message": case_prompt[:50] + ("..." if len(case_prompt) > 50 else "")
                                        }
                                    )
                                            
                                    # Get agent response
                                    with st.chat_message("assistant"):
                                        with st.spinner("Thinking..."):
                                            try:
                                                response = st.session_state.client.send_message(
                                                    agent_id, 
                                                    case_prompt
                                                )
                                                
                                                # Extract content and reasoning if available
                                                content = ""
                                                reasoning = ""
                                                
                                                # Parse the Letta API response format
                                                if isinstance(response, dict) and "messages" in response:
                                                    for msg in response["messages"]:
                                                        if msg.get("message_type") == "reasoning_message":
                                                            reasoning = msg.get("reasoning", "")
                                                        elif msg.get("message_type") == "assistant_message":
                                                            content = msg.get("content", "")
                                                
                                                # Display response
                                                st.markdown(content)
                                                
                                                # Display reasoning in an expander if user has permission
                                                if reasoning and has_permission("view_reasoning"):
                                                    with st.expander("View Agent Reasoning"):
                                                        st.markdown(reasoning)
                                                
                                                # Add to conversation history
                                                active_conv['messages'].append({
                                                    "role": "assistant", 
                                                    "content": content,
                                                    "reasoning": reasoning
                                                })
                                                
                                                # Save the updated cases
                                                save_cases(st.session_state.username, st.session_state.cases)
                                                
                                            except Exception as e:
                                                st.error(f"Error getting response: {str(e)}")
                    else:
                        st.info("No conversations in this case yet. Create a new conversation to get started.")
                
                # Agents tab - manage agents for this case
                with case_tabs[1]:
                    st.subheader("Case Agents")
                    
                    # Agent creation UI for case view
                    if has_permission("create_agents"):
                        with st.expander("Create New Agent for this Case"):
                            new_agent_name = st.text_input("Agent Name", key="new_agent_name_case")
                            new_agent_persona = st.text_area("Agent Persona", 
                                placeholder="Enter a description of the agent's persona, expertise, and personality.", 
                                key="new_agent_persona_case", 
                                height=150)
                            
                            if st.button("Create Agent", key="create_agent_case"):
                                try:
                                    with st.spinner("Creating new agent..."):
                                        # Create agent using the client
                                        new_agent = st.session_state.client.create_agent(new_agent_name, new_agent_persona)
                                        new_agent_id = new_agent.get('id')
                                        
                                        # Log the action
                                        log_user_action(
                                            st.session_state.username, 
                                            "create_case_agent", 
                                            {
                                                "agent_name": new_agent_name, 
                                                "agent_id": new_agent_id,
                                                "case_id": st.session_state.active_case,
                                                "case_title": active_case["title"]
                                            }
                                        )
                                        
                                        # Add the new agent to the case
                                        if "agents" not in active_case:
                                            active_case["agents"] = []
                                        active_case["agents"].append(new_agent_id)
                                        
                                        # Save the updated cases
                                        save_cases(st.session_state.username, st.session_state.cases)
                                        
                                        st.success(f"Created new agent and added to case: {new_agent_name}")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error creating agent: {str(e)}")
                    
                    # Display current agents in the case
                    case_agents = active_case.get("agents", [])
                    
                    if case_agents:
                        st.write("Current agents in this case:")
                        
                        for agent_id in case_agents:
                            try:
                                # Try to get agent details
                                agent_found = False
                                agents = st.session_state.client.list_agents()
                                for agent in agents:
                                    if agent['id'] == agent_id:
                                        agent_name = agent.get('name', f"Agent {agent_id}")
                                        agent_col1, agent_col2 = st.columns([3, 1])
                                        
                                        with agent_col1:
                                            st.write(f"• {agent_name}")
                                        
                                        with agent_col2:
                                            if st.button("Remove", key=f"remove_agent_{agent_id}"):
                                                # Remove agent from case
                                                active_case["agents"].remove(agent_id)
                                                
                                                # Save the updated cases
                                                save_cases(st.session_state.username, st.session_state.cases)
                                                
                                                # Log the action
                                                log_user_action(
                                                    st.session_state.username, 
                                                    "remove_agent_from_case", 
                                                    {
                                                        "case_id": st.session_state.active_case,
                                                        "agent_id": agent_id,
                                                        "agent_name": agent_name
                                                    }
                                                )
                                                
                                                st.success(f"Removed agent {agent_name} from the case")
                                                st.rerun()
                                        
                                        agent_found = True
                                        break
                                
                                if not agent_found:
                                    st.write(f"• Unknown Agent ({agent_id})")
                                    
                            except Exception as e:
                                st.error(f"Error loading agent details: {str(e)}")
                    else:
                        st.info("No agents have been added to this case yet.")
                    
                    # Add new agents to the case
                    st.divider()
                    st.subheader("Add Agents")
                    
                    try:
                        all_agents = st.session_state.client.list_agents()
                        available_agents = [agent for agent in all_agents if agent['id'] not in case_agents]
                        
                        if available_agents:
                            agent_options = {f"{agent.get('name', 'Unnamed Agent')} ({agent['id']})": agent['id'] for agent in available_agents}
                            selected_agent_name = st.selectbox("Select agent to add:", list(agent_options.keys()))
                            selected_agent_id = agent_options[selected_agent_name]
                            
                            if st.button("Add Agent to Case"):
                                # Add agent to case
                                if "agents" not in active_case:
                                    active_case["agents"] = []
                                
                                active_case["agents"].append(selected_agent_id)
                                
                                # Save the updated cases
                                save_cases(st.session_state.username, st.session_state.cases)
                                
                                # Log the action
                                log_user_action(
                                    st.session_state.username, 
                                    "add_agent_to_case", 
                                    {
                                        "case_id": st.session_state.active_case,
                                        "agent_id": selected_agent_id,
                                        "agent_name": selected_agent_name
                                    }
                                )
                                
                                st.success(f"Added agent to the case")
                                st.rerun()
                        else:
                            st.info("All available agents have already been added to this case.")
                    except Exception as e:
                        st.error(f"Error loading available agents: {str(e)}")
                
                # Details tab - view and edit case details
                with case_tabs[2]:
                    st.subheader("Case Details")
                    
                    # Display case ID
                    st.write(f"Case ID: {active_case['id']}")
                    
                    # Edit case title
                    new_title = st.text_input("Case Title", value=active_case['title'], key="edit_case_title")
                    
                    if new_title != active_case['title'] and st.button("Update Case Title"):
                        # Log the action
                        log_user_action(
                            st.session_state.username, 
                            "update_case_title", 
                            {
                                "case_id": st.session_state.active_case,
                                "old_title": active_case['title'],
                                "new_title": new_title
                            }
                        )
                        
                        # Update case title
                        active_case['title'] = new_title
                        
                        # Save the updated cases
                        save_cases(st.session_state.username, st.session_state.cases)
                        
                        st.success("Updated case title")
                        st.rerun()
                    
                    # Case documents section
                    st.divider()
                    st.subheader("Case Documents")
                    
                    # Initialize documents list if not exists
                    if "documents" not in active_case:
                        active_case["documents"] = []
                    
                    # Document upload section
                    case_uploaded_files = st.file_uploader(
                        "Upload documents to this case",
                        type=["pdf", "txt", "docx", "doc", "rtf", "png", "jpg", "jpeg"],
                        accept_multiple_files=True,
                        key="case_document_uploader"
                    )
                    
                    if case_uploaded_files and st.button("Attach Documents to Case"):
                        # Create a documents directory for cases if it doesn't exist
                        case_docs_dir = os.path.join(CASES_DIR, "documents")
                        os.makedirs(case_docs_dir, exist_ok=True)
                        
                        # Create case-specific directory
                        case_specific_dir = os.path.join(case_docs_dir, st.session_state.active_case)
                        os.makedirs(case_specific_dir, exist_ok=True)
                        
                        # Process each file
                        for uploaded_file in case_uploaded_files:
                            # Create unique filename (timestamp + original name)
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{timestamp}_{uploaded_file.name}"
                            file_path = os.path.join(case_specific_dir, filename)
                            
                            # Save the file
                            with open(file_path, 'wb') as f:
                                f.write(uploaded_file.getvalue())
                            
                            # Add to case documents list
                            active_case["documents"].append({
                                "id": str(uuid.uuid4()),
                                "name": uploaded_file.name,
                                "filename": filename,
                                "uploaded_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "uploaded_by": st.session_state.username,
                                "file_path": file_path,
                                "size": uploaded_file.size,
                                "type": uploaded_file.type,
                            })
                            
                            # Log the document upload
                            log_user_action(
                                st.session_state.username, 
                                "upload_case_document", 
                                {
                                    "case_id": st.session_state.active_case,
                                    "filename": uploaded_file.name,
                                    "file_size": uploaded_file.size
                                }
                            )
                        
                        # Save the updated cases
                        save_cases(st.session_state.username, st.session_state.cases)
                        st.success(f"Successfully attached {len(case_uploaded_files)} document(s) to the case")
                        st.rerun()
                    
                    # Display existing documents
                    if active_case["documents"]:
                        st.write("Attached documents:")
                        
                        for i, doc in enumerate(active_case["documents"]):
                            col1, col2, col3 = st.columns([3, 1, 1])
                            
                            with col1:
                                st.write(f"{i+1}. {doc['name']} ({doc['uploaded_at']})")
                            
                            with col2:
                                # Check if file exists before offering download
                                if os.path.exists(doc['file_path']):
                                    with open(doc['file_path'], "rb") as file:
                                        st.download_button(
                                            label="Download",
                                            data=file,
                                            file_name=doc['name'],
                                            mime=doc['type'],
                                            key=f"download_{doc['id']}"
                                        )
                                else:
                                    st.error("File not found")
                            
                            with col3:
                                if st.button("Delete", key=f"delete_doc_{doc['id']}"):
                                    # Try to delete the actual file
                                    if os.path.exists(doc['file_path']):
                                        os.remove(doc['file_path'])
                                    
                                    # Remove from documents list
                                    active_case["documents"].remove(doc)
                                    
                                    # Log the action
                                    log_user_action(
                                        st.session_state.username, 
                                        "delete_case_document", 
                                        {
                                            "case_id": st.session_state.active_case,
                                            "filename": doc['name']
                                        }
                                    )
                                    
                                    # Save the updated cases
                                    save_cases(st.session_state.username, st.session_state.cases)
                                    st.success(f"Deleted document: {doc['name']}")
                                    st.rerun()
                    else:
                        st.info("No documents attached to this case yet.")
                    
                    # Option to import documents to agent sources
                    if active_case["documents"] and has_permission("upload_documents"):
                        st.divider()
                        st.subheader("Import Documents to Agent")
                        
                        # Get the available agents for this case
                        available_agents = []
                        try:
                            # Try case-specific agents first
                            case_agents = active_case.get("agents", [])
                            if case_agents:
                                agents = st.session_state.client.list_agents()
                                available_agents = [agent for agent in agents if agent['id'] in case_agents]
                            
                            # If no case agents, get all agents
                            if not available_agents:
                                available_agents = st.session_state.client.list_agents()
                            
                            if available_agents:
                                # Select agent
                                agent_options = {f"{agent.get('name', 'Unnamed Agent')} ({agent['id']})": agent['id'] for agent in available_agents}
                                selected_agent_name = st.selectbox("Select agent:", list(agent_options.keys()), key="import_agent_select")
                                selected_agent_id = agent_options[selected_agent_name]
                                
                                # Get sources for the selected agent
                                agent_sources = st.session_state.client.get_agent_sources(selected_agent_id)
                                
                                if agent_sources:
                                    # Create a dropdown to select which source to upload to
                                    source_options = {source.get('name', f"Source {i}"): source['id'] for i, source in enumerate(agent_sources)}
                                    selected_source_name = st.selectbox("Select source to upload to:", list(source_options.keys()), key="import_source_select")
                                    selected_source_id = source_options[selected_source_name]
                                    
                                    # Multi-select for documents
                                    st.write("Select documents to import:")
                                    selected_docs = []
                                    for i, doc in enumerate(active_case["documents"]):
                                        if st.checkbox(f"{doc['name']}", key=f"import_doc_{doc['id']}"):
                                            selected_docs.append(doc)
                                    
                                    if selected_docs and st.button("Import Selected Documents to Agent"):
                                        with st.spinner("Importing documents to agent..."):
                                            success_count = 0
                                            for doc in selected_docs:
                                                try:
                                                    # Check if file exists
                                                    if os.path.exists(doc['file_path']):
                                                        # Upload file to the selected source
                                                        upload_result = st.session_state.client.upload_file_to_source(
                                                            selected_source_id, 
                                                            doc['file_path']
                                                        )
                                                        
                                                        if upload_result:
                                                            success_count += 1
                                                            
                                                            # Log the action
                                                            log_user_action(
                                                                st.session_state.username,
                                                                "import_case_document_to_agent",
                                                                {
                                                                    "case_id": st.session_state.active_case,
                                                                    "filename": doc['name'],
                                                                    "agent_id": selected_agent_id,
                                                                    "source_id": selected_source_id
                                                                }
                                                            )
                                                    else:
                                                        st.error(f"File not found: {doc['name']}")
                                                except Exception as e:
                                                    st.error(f"Error importing {doc['name']}: {str(e)}")
                                            
                                            if success_count > 0:
                                                st.success(f"Successfully imported {success_count} document(s) to the agent")
                                            else:
                                                st.error("No documents were successfully imported")
                                else:
                                    st.warning("No sources are attached to this agent. Please attach sources through the Letta Server UI.")
                            else:
                                st.error("No agents available.")
                        except Exception as e:
                            st.error(f"Error loading agents or sources: {str(e)}")
                    
                    # Case summary section
                    st.divider()
                    st.subheader("Case Summary")
                    
                    # Check if there are conversations in the case
                    case_conversations = active_case.get("conversations", {})
                    if not case_conversations:
                        st.info("No conversations in this case yet. Add conversations before generating a summary.")
                    else:
                        # Select agent for summarization
                        available_agents = []
                        try:
                            agents = st.session_state.client.list_agents()
                            if agents:
                                agent_options = {f"{agent.get('name', 'Unnamed Agent')} ({agent['id']})": agent['id'] for agent in agents}
                                selected_summary_agent_name = st.selectbox("Select agent for summarization:", list(agent_options.keys()), key="summary_agent_select")
                                selected_summary_agent_id = agent_options[selected_summary_agent_name]
                                
                                # Generate summary button
                                if st.button("Generate Case Summary"):
                                    with st.spinner("Generating case summary..."):
                                        try:
                                            # Compile all conversations into a single document
                                            conversation_text = f"# Case Summary Request: {active_case['title']}\n\n"
                                            
                                            for conv_id, conv in case_conversations.items():
                                                conversation_text += f"## Conversation: {conv.get('title', 'Untitled')}\n"
                                                
                                                # Include messages from this conversation
                                                messages = conv.get('messages', [])
                                                if messages:
                                                    for i, msg in enumerate(messages):
                                                        role = msg.get('role', 'unknown').upper()
                                                        content = msg.get('content', 'No content')
                                                        conversation_text += f"{role}: {content}\n\n"
                                                else:
                                                    conversation_text += "No messages in this conversation.\n\n"
                                                
                                                conversation_text += "---\n\n"
                                            
                                            # Add the summary request instruction at the end
                                            conversation_text += "\nPlease provide a comprehensive summary of this legal case. Include key issues, arguments, legal principles discussed, and any conclusions or recommendations made throughout the conversations."
                                            
                                            # Send to the selected agent for summarization
                                            summary_response = st.session_state.client.send_message(
                                                selected_summary_agent_id,
                                                conversation_text
                                            )
                                            
                                            # Extract content from response
                                            summary_content = ""
                                            if isinstance(summary_response, dict) and "messages" in summary_response:
                                                for msg in summary_response["messages"]:
                                                    if msg.get("message_type") == "assistant_message":
                                                        summary_content = msg.get("content", "")
                                            
                                            # Store the summary in the case data
                                            if "summary" not in active_case:
                                                active_case["summary"] = {}
                                            
                                            active_case["summary"]["content"] = summary_content
                                            active_case["summary"]["generated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            active_case["summary"]["generated_by"] = selected_summary_agent_id
                                            
                                            # Save the updated case
                                            save_cases(st.session_state.username, st.session_state.cases)
                                            
                                            # Log the action
                                            log_user_action(
                                                st.session_state.username,
                                                "generate_case_summary",
                                                {
                                                    "case_id": st.session_state.active_case,
                                                    "agent_id": selected_summary_agent_id
                                                }
                                            )
                                            
                                            st.success("Case summary generated successfully!")
                                        except Exception as e:
                                            st.error(f"Error generating summary: {str(e)}")
                            else:
                                st.error("No agents available for generating a summary.")
                        except Exception as e:
                            st.error(f"Error loading agents: {str(e)}")
                        
                        # Display existing summary if available
                        if "summary" in active_case and "content" in active_case["summary"]:
                            with st.expander("View Case Summary", expanded=True):
                                st.markdown(active_case["summary"]["content"])
                                st.caption(f"Generated at: {active_case['summary'].get('generated_at', 'Unknown')}")
                                
                                # Download summary option
                                if st.button("Download Summary as Text"):
                                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                    summary_filename = f"{active_case['title']}_{timestamp}_summary.txt"
                                    summary_content = active_case["summary"]["content"]
                                    
                                    # Create a download button for the text
                                    st.download_button(
                                        label="Download Summary",
                                        data=summary_content,
                                        file_name=summary_filename,
                                        mime="text/plain"
                                    )
                    
                    # Option to close/archive case (future enhancement)
                    st.divider()
                    if st.button("⬅️ Return to Case List"):
                        st.session_state.active_case = None
                        st.session_state.case_conversation = None
                        st.session_state.view_mode = "normal"
                        st.rerun()
                        
                # Workflow tab - manage case workflow
                with case_tabs[3]:
                    st.subheader("Case Workflow")
                    
                    # Check if the case already has a workflow
                    if active_case.get("workflow") is None:
                        # No workflow assigned yet, show workflow template selection
                        st.write("No workflow assigned to this case yet.")
                        
                        # Get available workflow templates
                        workflow_templates = get_workflow_templates()
                        
                        if workflow_templates:
                            # Create select box for templates
                            template_options = {template["name"]: template_id for template_id, template in workflow_templates.items()}
                            selected_template_name = st.selectbox(
                                "Select a workflow template:",
                                list(template_options.keys())
                            )
                            selected_template_id = template_options[selected_template_name]
                            
                            # Display template description
                            st.info(workflow_templates[selected_template_id]["description"])
                            
                            # Show stages in the selected template
                            st.write("This workflow includes the following stages:")
                            for i, stage in enumerate(workflow_templates[selected_template_id]["stages"]):
                                st.write(f"{i+1}. **{stage['name']}**: {stage['description']}")
                            
                            # Button to assign the workflow
                            if st.button("Assign Workflow to Case"):
                                if assign_workflow_to_case(st.session_state.active_case, selected_template_id):
                                    st.success(f"Assigned '{selected_template_name}' workflow to this case!")
                                    st.rerun()
                                else:
                                    st.error("Failed to assign workflow. Please try again.")
                        else:
                            st.error("No workflow templates available.")
                    else:
                        # Workflow is already assigned, show workflow progress
                        workflow = active_case["workflow"]
                        st.write(f"**Current Workflow:** {workflow['name']}")
                        st.write(workflow["description"])
                        st.write(f"Assigned on: {workflow['assigned_at']}")
                        
                        # Create progress meter
                        total_stages = len(workflow["stages"])
                        completed_stages = sum(1 for stage in workflow["stages"] if stage["status"] == "completed")
                        progress_percentage = int((completed_stages / total_stages) * 100) if total_stages > 0 else 0
                        
                        st.progress(progress_percentage / 100)
                        st.write(f"Progress: {progress_percentage}% ({completed_stages}/{total_stages} stages completed)")
                        
                        # Show all stages with their status
                        st.subheader("Workflow Stages")
                        
                        for i, stage in enumerate(workflow["stages"]):
                            # Create an expander for each stage
                            status_color = {
                                "not_started": "gray",
                                "in_progress": "blue",
                                "completed": "green"
                            }.get(stage["status"], "gray")
                            
                            status_emoji = {
                                "not_started": "⚪",
                                "in_progress": "🔵",
                                "completed": "✅"
                            }.get(stage["status"], "⚪")
                            
                            with st.expander(
                                f"{status_emoji} Stage {i+1}: {stage['name']} - "
                                f"**{stage['status'].replace('_', ' ').title()}**",
                                expanded=(i == workflow["current_stage_index"])
                            ):
                                st.write(f"**Description:** {stage['description']}")
                                
                                # Show dates if available
                                if stage["start_date"]:
                                    st.write(f"**Started:** {stage['start_date']}")
                                if stage["completion_date"]:
                                    st.write(f"**Completed:** {stage['completion_date']}")
                                
                                # Stage notes
                                stage_notes = st.text_area(
                                    "Stage Notes",
                                    value=stage["notes"],
                                    key=f"notes_{i}",
                                    height=100
                                )
                                
                                if stage_notes != stage["notes"] and st.button("Save Notes", key=f"save_notes_{i}"):
                                    if update_workflow_stage_notes(st.session_state.active_case, i, stage_notes):
                                        st.success("Notes saved!")
                                        st.rerun()
                                
                                # Status controls - only show relevant status change buttons
                                status_col1, status_col2, status_col3 = st.columns(3)
                                
                                with status_col1:
                                    if stage["status"] != "not_started" and i > 0:
                                        if st.button("⬅️ Mark Not Started", key=f"not_started_{i}"):
                                            if update_workflow_stage_status(st.session_state.active_case, i, "not_started"):
                                                st.success(f"Updated stage status to Not Started")
                                                st.rerun()
                                
                                with status_col2:
                                    if stage["status"] != "in_progress":
                                        if st.button("🔄 Mark In Progress", key=f"in_progress_{i}"):
                                            if update_workflow_stage_status(st.session_state.active_case, i, "in_progress"):
                                                st.success(f"Updated stage status to In Progress")
                                                st.rerun()
                                
                                with status_col3:
                                    if stage["status"] != "completed":
                                        if st.button("✅ Mark Completed", key=f"completed_{i}"):
                                            if update_workflow_stage_status(st.session_state.active_case, i, "completed"):
                                                st.success(f"Updated stage status to Completed")
                                                st.rerun()
            
            # Invalid state
            elif st.session_state.view_mode == "case" and not st.session_state.active_case:
                st.header("Case Management")
                st.warning("No active case selected. Please select or create a case from the sidebar.")
                
                if st.button("⬅️ Return to Regular Chat"):
                    st.session_state.view_mode = "normal"
                    st.rerun()
                    
        else:
            st.error("You don't have permission to access the chat functionality.")

        # Footer
        st.markdown("---")
        st.caption("LegalSphere - WTO and International Trade Law Assistant")