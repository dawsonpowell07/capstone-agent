# VacAI - AI Vacation Planning Agent

A sophisticated vacation planning assistant powered by LangChain and LangGraph. VacAI uses a supervisor-agent architecture to help users plan complete trips through natural conversation, including flight searches, hotel recommendations, activity suggestions, and full itinerary management.

## Features

- **Natural Conversation Planning**: Chat naturally about your travel plans, and the AI supervisor coordinates specialized agents to find options
- **Flight Search**: Integration with Amadeus API for real-time flight availability
- **Hotel Search**: Google Maps Places API for accommodation recommendations
- **Activity Recommendations**: Discover attractions and experiences at your destination
- **Itinerary Management**: Save, retrieve, and update complete travel itineraries
- **User Profiles**: Personalized recommendations based on user preferences stored in Azure Cosmos DB
- **Conversation Persistence**: MongoDB-backed conversation history for seamless multi-session planning
- **Auth0 Integration**: Secure user authentication for protected endpoints

## Architecture

### Agent System

The application uses a **supervisor-agent pattern** built with LangChain:

- **Supervisor Agent** (`agent/graph.py`):
  - Main orchestrator that converses with users
  - Powered by OpenAI's GPT-5-nano model
  - Coordinates four specialized tools via natural language delegation
  - Uses dynamic prompts with user context (user_id, user_info, itinerary_id)
  - Makes smart assumptions to minimize unnecessary questions

- **Specialist Agents** (`agent/nodes/`):
  - **Flight Agent**: Searches flights using Amadeus API
  - **Hotel Agent**: Searches hotels using Google Maps Places API
  - **Activity Agent**: Searches activities/attractions using Google Maps Places API
  - **Itinerary Agent**: Manages itinerary CRUD operations with Azure Cosmos DB

### Data Storage

- **MongoDB**: Conversation state and message history (via LangGraph MongoDBSaver)
- **Azure Cosmos DB**: User profiles and travel itineraries (persistent data)

### API Endpoints

All routes are defined in `routes/chat_routes.py`:

#### Chat Endpoints
- `POST /api/chat/{thread_id}`: Unauthenticated chat for testing
- `POST /api/chat/pc/{thread_id}`: Protected chat requiring Auth0 authentication

Both accept:
```json
{
  "role": "user",
  "content": "Find me hotels in Tokyo for June 15-22",
  "userId": "optional-user-id",
  "itineraryId": "optional-itinerary-id"
}
```

#### Message History
- `GET /api/chat/threads/{thread_id}/messages`: Retrieve conversation history (unauthenticated)
- `GET /api/chat/pc/threads/{thread_id}/messages`: Retrieve conversation history (protected)

#### Health Check
- `GET /` or `GET /health`: Application health status

## Requirements

- Python 3.13+
- uv (recommended) or pip
- MongoDB instance (for conversation persistence)
- Azure Cosmos DB account (for user profiles and itineraries)
- OpenAI API key
- Auth0 account (for authentication)
- Google Maps API key (for hotel/activity searches)
- Amadeus API credentials (optional, for flight searches)

## Setup

### Option 1: Using uv (Recommended)

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run development server
uvicorn main:app --reload
```

### Option 2: Using pip

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate 

# Install dependencies
pip install -r requirements.txt

# Run server
python3 -m uvicorn main:app --reload
```

## Environment Variables

Create a `.env` file in the project root with the following variables:

### Required Variables

```bash
# OpenAI (Required - powers the AI agents)
OPENAI_API_KEY=your_openai_api_key

# MongoDB (Required - conversation persistence)
MONGO_URI=mongodb://localhost:27017  # or your MongoDB connection string

# Azure Cosmos DB (Required - user profiles and itineraries)
COSMOS_DB_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_DB_KEY=your_cosmos_db_key
COSMOS_DB_DATABASE_NAME=your_database_name
COSMOS_DB_CONTAINER_NAME=itineraries

# Google Maps (Required - hotel and activity searches)
GOOGLE_MAPS_API=your_google_maps_api_key

# Auth0 (Required - authentication)
AUTH0_API_AUDIENCE=your_api_audience
AUTH0_DOMAIN=your_domain.auth0.com
AUTH0_ISSUER=https://your_domain.auth0.com/
AUTH0_ALGORITHMS=RS256
```

### Optional Variables

```bash
# Gemini (Optional - not currently used)
GEMENI_API_KEY=dummy_value

# LangSmith (Optional - for debugging/tracing)
LANGSMITH_API_KEY=your_langsmith_key

# Amadeus (Optional - for flight searches)
AMADEUS_API_SECRET=your_amadeus_secret
AMADEUS_API_KEY=your_amadeus_key
AMADEUS_TOKEN_URL=https://test.api.amadeus.com/v1/security/oauth2/token
AMADEUS_BASE_URL=https://test.api.amadeus.com

# Auth0 (Optional)
AUTH0_CLIENT_ID=your_client_id
```

**Note**: The application requires all environment variables to be set. For optional services you're not using, provide dummy values (e.g., `AMADEUS_API_KEY=dummy`).

## Development

### Running the Server

```bash
# FastAPI with hot reload (standard development)
uvicorn main:app --reload

# LangGraph Studio (for testing agent graphs)
langgraph dev
```

The server will be available at `http://localhost:8000`.

### Dependency Management

After adding new dependencies to `pyproject.toml`, update `requirements.txt` for Docker deployment:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

## Docker Deployment

### Build and Run

```bash
# Build the Docker image
docker build -t vacation-agent .

# Run the container
docker run -p 8080:8080 vacation-agent
```

The application will be available at `http://localhost:8080`.

### Environment Variables in Docker

Pass environment variables using a `.env` file:

```bash
docker run -p 8080:8080 --env-file .env vacation-agent
```

## Project Structure

```
agent/
├── graph.py                    # Main agent graph with supervisor
├── state.py                    # LangGraph state definitions
├── nodes/                      # Specialist agents
│   ├── flight_agent.py
│   ├── hotel_agent.py
│   ├── activity_agent.py
│   └── itinerary_agent.py
├── tools/                      # Tool implementations
│   ├── amadeus_flights_tool.py
│   ├── amadeus_activity_tool.py
│   ├── google_maps_tool.py
│   ├── coordinates_tool.py
│   └── itineraryTools.py       # Cosmos DB itinerary operations
└── auth/                       # Authentication
    └── amadeus_auth.py

routes/
└── chat_routes.py              # FastAPI endpoints

utils/
├── utils.py                    # Auth0 token verification
└── user_profile.py             # Cosmos DB user profile fetching

models/
└── models.py                   # Pydantic request/response models

config.py                       # Settings (loads from .env)
main.py                         # FastAPI application entry point
```

## Technology Stack

- **Framework**: FastAPI
- **Agent Framework**: LangChain + LangGraph
- **LLM**: OpenAI GPT-5
- **Conversation Storage**: MongoDB (LangGraph MongoDBSaver)
- **Persistent Data**: Azure Cosmos DB
- **Authentication**: Auth0 with JWT
- **External APIs**:
  - Amadeus API (flights)
  - Google Maps Places API (hotels, activities)
- **Deployment**: Docker, Azure Web Apps
- **Package Management**: uv

## API Testing

Use the LangGraph Studio for interactive agent testing:

```bash
langgraph dev
```

Or test via HTTP:

```bash
curl -X POST http://localhost:8000/api/chat/test-thread \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Find me flights from New York to Tokyo in June",
    "userId": "test-user-123"
  }'
```
