## Overview

LegalSphere is a comprehensive agentic framework for legal case management designed specifically for international trade law and WTO regulations. The application provides a role-based interface for legal professionals, clients, and administrators to collaborate on legal cases using AI-powered agents.

## Key Features

### Role-Based Access Control

- Admin: Full system access including audit logs and agent management
- Legal Advisor: Create agents, manage cases, view reasoning, upload documents
- Client: View agents, participate in chats, manage cases
- Guest: Basic chat functionality only

### Case Management

- Create and organize legal cases
- Add multiple conversations to each case
- Assign specialized AI agents to cases
- Generate comprehensive case summaries

### AI Agent Integration

- Select from existing agents or create new specialized agents
- Upload documents to agent knowledge sources
- View agent reasoning (for authorized roles)
- Customize agent personas for different legal specialties

### Document Management

- Upload legal documents (PDF, TXT, DOCX)
- Associate documents with specific sources and agents
- Process documents for AI analysis

### Conversation History

- Persistent conversation storage
- Export conversations in multiple formats (TXT, CSV, PDF)
- Organize conversations within cases

### Audit Logging

- Comprehensive tracking of user actions
- Filterable log view for administrators
- Security monitoring and compliance

## Setup Screenshots

![[Pasted image 20250509015121.jpg]]

![[Pasted image 20250509015131.jpg]]

![[Pasted image 20250509015203.jpg]]

![[Pasted image 20250509015227.jpg]]
![[Pasted image 20250509015243.jpg]]
## Technical Architecture

LegalSphere is built using:
- Streamlit: For the web interface
- LettaClient: Custom API client for AI agent communication
- File-based Storage: JSON storage for conversations, cases, and logs
- Langfuse: For AI interaction observability and tracing
- Docker Compose for Microservice Architecture
## Code Structure

LegalSphere/
├── lit.py                # Main Streamlit application
├── main.py               # LettaClient implementation
├── user_data/            # User conversation data
├── audit_logs/           # Audit log files
├── exports/              # Exported conversation files
├── cases/                # Case data files
└── config/               # Configuration files

## Case Management Workflow

- Create a Case: Users with appropriate permissions can create new legal cases
- Add Agents: Assign specialized AI agents to the case
- Create Conversations: Start multiple conversations within the case
- Upload Documents: Add relevant legal documents to agent knowledge sources
- Generate Summaries: Create comprehensive case summaries using AI agents

## Example Case Summary Request

```markdown
### Case Summary:
**Key Issues:**
1. **Definition of GATT:** The conversation began with the inquiry about GATT, where it was explained as the Generic Attribute Profile in Bluetooth Low Energy and later as the General Agreement on Tariffs and Trade in a legal context.
2. **Anti-Dumping Laws:** The user asked whether the U.S. has imposed anti-dumping laws on China, leading to a discussion on specific cases.

**Arguments:**
- **GATT’s Role in Trade:** GATT serves as a framework for international trade, aiming to reduce trade barriers and promote fair competition.
- **U.S. Anti-Dumping Measures:** The U.S. has utilized anti-dumping duties to protect its domestic industries from unfair pricing by foreign competitors, specifically citing Chinese imports.

**Legal Principles Discussed:**
- The importance of fair trade practices and regulations to protect domestic markets.

**Conclusions/Recommendations:**
- Understanding both the technical and legal aspects of GATT is crucial for grasping international trade dynamics.
- Monitoring specific cases of anti-dumping laws can provide insights into trade relations between the U.S. and China.

If you need further details or specific examples, feel free to ask!
```

## Security Considerations

- In-memory user authentication (should be enhanced for production)
- Role-based permission enforcement
- Comprehensive audit logging
- API key management (currently hardcoded, should use environment variables)

## Future Enhancements

- Document annotation capabilities
- Collaborative case editing
- Advanced search across cases and conversations
- Integration with legal citation systems
- Enhanced security features
- Mobile-responsive interface

## Getting Started / Deployment

1. Run `docker compose up --build`: service(s) will be built and start running. 
2. Access at http://localhost:8501

## Demo Accounts

- Admin: admin1/admin123
- Legal Advisor: advisor1/legal123
- Client: client1/client123
- Guest: guest1/guest123
