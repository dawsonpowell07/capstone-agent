# System Design Document: Vacation Planning Agent

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [API Design](#api-design)
6. [External Integrations](#external-integrations)
7. [Security & Authentication](#security--authentication)
8. [Database & State Management](#database--state-management)
9. [Agent Architecture](#agent-architecture)
10. [Technology Stack](#technology-stack)
11. [Deployment Architecture](#deployment-architecture)
12. [Scalability & Performance](#scalability--performance)

---

## System Overview

### Purpose
The Vacation Planning Agent is an AI-powered backend service that helps users plan complete trips through natural conversation. It uses a multi-agent architecture to coordinate flight searches, hotel bookings, and activity recommendations.

### Key Features
- **Conversational Interface**: Natural language trip planning
- **Multi-Agent Coordination**: Specialized agents for flights, hotels, and activities
- **Itinerary Management**: Store and retrieve complete trip plans
- **User Personalization**: Integrates user preferences and profiles
- **Persistent Conversations**: Resume conversations across sessions
- **Real-time Search**: Live queries to flight and accommodation APIs

### Design Philosophy
- **Minimal User Friction**: Make smart assumptions to reduce back-and-forth
- **Specialized Agents**: Each agent focuses on one domain (flights, hotels, activities)
- **Supervisor Pattern**: Central coordinator manages delegation and synthesis
- **API-First**: Clean REST interface for frontend integration

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Client                         │
│              (React/Next.js Application)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/REST
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    FastAPI Server                            │
│  ┌────────────────────────────────────────────────────┐     │
│  │              API Routes Layer                       │     │
│  │  - /api/chat/{thread_id}                           │     │
│  │  - /api/chat/pc/{thread_id} (protected)            │     │
│  │  - /api/chat/threads/{thread_id}/messages          │     │
│  └────────────────────┬───────────────────────────────┘     │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────┐     │
│  │         LangGraph Agent System                      │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────┐     │     │
│  │  │      Supervisor Agent (Orchestrator)     │     │     │
│  │  │  - GPT-4o-nano                           │     │     │
│  │  │  - Conversation management               │     │     │
│  │  │  - Delegation logic                      │     │     │
│  │  │  - Result synthesis                      │     │     │
│  │  └─────┬────────────────────────────────────┘     │     │
│  │        │                                           │     │
│  │        │ Delegates to:                             │     │
│  │        │                                           │     │
│  │  ┌─────▼──────┐  ┌──────────┐  ┌──────────────┐  │     │
│  │  │   Flight   │  │  Hotel   │  │   Activity   │  │     │
│  │  │   Agent    │  │  Agent   │  │    Agent     │  │     │
│  │  └─────┬──────┘  └────┬─────┘  └──────┬───────┘  │     │
│  │        │              │                │          │     │
│  │  ┌─────▼──────────────▼────────────────▼───────┐  │     │
│  │  │         Itinerary Agent                     │  │     │
│  │  │  - Retrieve/Update itineraries              │  │     │
│  │  └─────────────────────────────────────────────┘  │     │
│  └─────────────────────────────────────────────────┘     │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌─────────────┐ ┌────────────┐
│   Amadeus    │ │   Google    │ │  MongoDB   │
│     API      │ │   Maps API  │ │  Database  │
│   (Flights)  │ │(Hotels/Acts)│ │  (State)   │
└──────────────┘ └─────────────┘ └────────────┘
```

### Architectural Pattern: Supervisor-Agent

The system implements a **supervisor-agent pattern** where:
- **Supervisor Agent**: Main orchestrator that handles conversation and delegates tasks
- **Specialist Agents**: Domain-specific agents that execute searches
- **Communication**: Supervisor delegates to specialists via tool calls
- **Control Flow**: Specialists return results to supervisor, who synthesizes final response

---

## Core Components

### 1. FastAPI Application (`main.py`)

**Responsibilities:**
- HTTP server setup and routing
- CORS middleware configuration
- Health check endpoints
- Route registration

**Key Configuration:**
```python
CORS Origins:
- https://purple-sand-06148da0f.1.azurestaticapps.net (production)
- http://localhost:3000 (development)
- Azure deployment URL
```

### 2. Chat Routes (`routes/chat_routes.py`)

**Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/chat/{thread_id}` | POST | No | Unauthenticated chat |
| `/api/chat/pc/{thread_id}` | POST | Yes (Auth0) | Protected chat |
| `/api/chat/threads/{thread_id}/messages` | GET | No | Fetch thread history |
| `/api/chat/pc/threads/{thread_id}/messages` | GET | Yes | Protected thread history |

**Request Format:**
```json
{
  "role": "user",
  "content": "Find me flights to Tokyo",
  "userId": "optional_user_id",
  "itineraryId": "optional_itinerary_id"
}
```

**Response Format:**
```json
{
  "id": "thread_123_msg_5",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I found 3 flights to Tokyo..."
    }
  ],
  "createdAt": "2025-11-20T12:00:00Z"
}
```

### 3. Supervisor Agent (`agent/graph.py`)

**Core Functionality:**
- Conversation management with users
- Extract trip requirements (destination, dates, travelers)
- Make intelligent assumptions to reduce friction
- Delegate to specialist agents via tools
- Synthesize results into coherent responses
- Prevent duplicate tool calls

**Tools Available:**
1. `find_flights(request: str)` → Delegates to Flight Agent
2. `find_hotels(request: str)` → Delegates to Hotel Agent
3. `find_activities(request: str)` → Delegates to Activity Agent
4. `itinerary_operations(request: str)` → Manages user itineraries

**Model:** GPT-4o-nano (OpenAI)

**Context Schema:**
```python
{
  "user_id": str,
  "user_info": dict,  # User preferences/profile
  "itinerary_id": str
}
```

**State Schema:**
```python
{
  "messages": List[BaseMessage],
  "user_preferences": dict
}
```

### 4. Specialist Agents

#### Flight Agent (`agent/nodes/flight_agent.py`)
- **Tool:** `search_flights_with_amadeus`
- **API:** Amadeus Flight Search API
- **Responsibilities:**
  - Extract origin, destination, dates, passenger count
  - Execute flight searches
  - Return formatted results (price, duration, airline, stops)
- **Assumptions:** Economy class, round-trip, flexible departure times

#### Hotel Agent (`agent/nodes/hotel_agent.py`)
- **Tool:** Google Maps Places API search
- **Responsibilities:**
  - Search hotels by location and dates
  - Filter by rating, price range
  - Return hotel options with amenities
- **Assumptions:** Mid-range hotels (3-5 star), 1 room per 2 guests

#### Activity Agent (`agent/nodes/activity_agent.py`)
- **Tool:** Google Maps Places API search
- **Responsibilities:**
  - Find attractions, tours, experiences
  - Filter by category and popularity
  - Return activity suggestions
- **Assumptions:** Mix of popular attractions and local experiences

#### Itinerary Agent (`agent/nodes/itinerary_agent.py`)
- **Tools:** CRUD operations on itineraries
- **Responsibilities:**
  - Retrieve itineraries by ID
  - Add flights/hotels/activities to trips
  - Update itinerary components
- **Storage:** Cosmos DB/MongoDB

### 5. Tools Layer (`agent/tools/`)

#### Amadeus Flight Tool (`amadeus_flights_tool.py`)
- **Authentication:** OAuth2 token-based (`agent/auth/amadeus_auth.py`)
- **Endpoints:** Flight search, availability
- **Response:** Parsed flight offers with pricing

#### Google Maps Tool (`google_maps_tool.py`)
- **Authentication:** API key
- **Endpoints:** Places search, geocoding
- **Response:** Hotel/activity listings with details

#### Coordinates Tool (`coordinates_tool.py`)
- **Purpose:** Convert city names to lat/long for Google Maps
- **Method:** Geocoding API

#### Itinerary Tools (`itineraryTools.py`)
- **Operations:** CRUD for user itineraries
- **Storage:** Cosmos DB collections

---

## Data Flow

### User Message Flow

```
1. User sends message → POST /api/chat/{thread_id}
   {
     "role": "user",
     "content": "Find flights to Paris next week",
     "userId": "user123"
   }

2. Chat route fetches user profile from database
   └─> user_profile = fetch_user_profile(user_id)

3. Create HumanMessage and invoke supervisor agent
   └─> supervisor_agent.ainvoke(
         messages=[HumanMessage(content)],
         context={user_id, user_info, itinerary_id},
         config={thread_id, recursion_limit: 15}
       )

4. Supervisor agent processes request:
   a. Analyze message for trip requirements
   b. Identify needed information (origin, destination, dates)
   c. Decide to delegate or ask clarification

5. If delegating → Supervisor calls tool (e.g., find_flights)
   └─> find_flights("Paris next week, 1 passenger")

6. Flight agent receives delegation:
   a. Parse request for search parameters
   b. Call search_flights_with_amadeus tool
   c. Format results
   d. Return to supervisor

7. Supervisor synthesizes results
   └─> Generate user-friendly response with options

8. Response formatted and returned to client
   └─> format_message_for_frontend(assistant_message)

9. State saved to MongoDB checkpointer
   └─> MongoDBSaver persists conversation state
```

### State Persistence Flow

```
Request → MongoDB Checkpointer → Retrieve State
                ↓
          Agent Execution
                ↓
          Updated State → Save to MongoDB
                ↓
          Response to User
```

---

## API Design

### REST Endpoints

#### 1. Chat Endpoint
```http
POST /api/chat/{thread_id}
Content-Type: application/json

{
  "role": "user",
  "content": "string",
  "userId": "string (optional)",
  "itineraryId": "string (optional)"
}

Response 200:
{
  "id": "string",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "string"
    }
  ],
  "createdAt": "ISO-8601 timestamp"
}
```

#### 2. Protected Chat Endpoint
```http
POST /api/chat/pc/{thread_id}
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "role": "user",
  "content": "string",
  "itineraryId": "string (optional)"
}

Response: Same as above
```

#### 3. Thread History
```http
GET /api/chat/threads/{thread_id}/messages

Response 200:
{
  "thread_id": "string",
  "messages": [
    {
      "id": "string",
      "role": "user|assistant|tool",
      "content": [...],
      "createdAt": "ISO-8601"
    }
  ]
}
```

#### 4. Health Check
```http
GET /
GET /health

Response 200:
{
  "status": "ok"
}
```

---

## External Integrations

### 1. Amadeus API
**Purpose:** Flight search and booking data

**Endpoints Used:**
- `/v1/security/oauth2/token` - OAuth2 authentication
- `/v2/shopping/flight-offers` - Flight search
- `/v1/shopping/activities` - Activity search

**Authentication:** OAuth2 client credentials flow
```python
POST /v1/security/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&
client_id={AMADEUS_API_KEY}&
client_secret={AMADEUS_API_SECRET}
```

**Rate Limits:** Check Amadeus documentation
**Error Handling:** Retry with exponential backoff

### 2. Google Maps API
**Purpose:** Hotel and activity search, geocoding

**APIs Used:**
- Places API - Search hotels and attractions
- Geocoding API - Convert locations to coordinates

**Authentication:** API key in request headers
```python
GET /maps/api/place/textsearch/json
  ?query={search_query}
  &key={GOOGLE_MAPS_API}
```

**Rate Limits:** Based on billing tier
**Error Handling:** Fallback to alternative searches

### 3. OpenAI API
**Purpose:** LLM for all agents

**Model:** GPT-4o-nano (gpt-5-nano)
**Configuration:**
- Temperature: 0 (deterministic)
- Max recursion: 15 steps

**Cost Optimization:**
- Use nano model for cost efficiency
- Limit recursion to prevent runaway costs

---

## Security & Authentication

### Auth0 Integration

**Configuration:**
```python
AUTH0_DOMAIN: Your Auth0 tenant domain
AUTH0_API_AUDIENCE: API identifier
AUTH0_ISSUER: Token issuer URL
AUTH0_ALGORITHMS: ["RS256"]
```

**Token Verification Flow:**
```
1. Client sends request with Bearer token
   └─> Authorization: Bearer {jwt}

2. VerifyToken middleware extracts token
   └─> HTTPBearer() dependency

3. Fetch JWKS from Auth0
   └─> GET https://{domain}/.well-known/jwks.json

4. Verify token signature
   └─> jwt.decode(token, signing_key, algorithms, audience, issuer)

5. Extract user claims
   └─> payload["sub"] = user_id

6. Proceed with authenticated request
```

**Security Features:**
- JWT signature verification using JWKS
- Audience and issuer validation
- Scope-based authorization (optional)
- HTTPS-only in production
- CORS restricted to known origins

### Environment Security
- All secrets in `.env` file (not committed)
- API keys stored as environment variables
- MongoDB connection string secured
- No secrets in code or logs

---

## Database & State Management

### MongoDB Architecture

**Database:** `agent-database-v2`

**Collections:**

1. **Checkpoints** (managed by LangGraph)
   - Stores conversation state
   - Schema: LangGraph checkpoint format
   - Key: `thread_id`
   - Indexed on thread_id for fast retrieval

2. **User Profiles**
   - User preferences and history
   - Schema: User-defined
   - Key: `user_id`

3. **Itineraries** (Cosmos DB)
   - Complete trip plans
   - Schema:
   ```json
   {
     "itinerary_id": "string",
     "user_id": "string",
     "destination": "string",
     "start_date": "date",
     "end_date": "date",
     "flights": [...],
     "hotels": [...],
     "activities": [...],
     "created_at": "timestamp",
     "updated_at": "timestamp"
   }
   ```

### State Persistence

**LangGraph Checkpointer:**
```python
from langgraph.checkpoint.mongodb import MongoDBSaver

checkpointer = MongoDBSaver(
    mongo_client,
    db_name="agent-database-v2"
)
```

**Checkpointing Behavior:**
- Automatic state save after each agent step
- Conversation history preserved
- Resume from any checkpoint
- Thread-based isolation

**State Schema:**
```python
{
  "messages": List[BaseMessage],
  "user_preferences": dict,
  "channel_values": {
    "messages": [...],
    "user_info": {...}
  }
}
```

---

## Agent Architecture

### LangGraph Implementation

**Graph Structure:**
```
Entry → Supervisor Agent → Specialist Agents → Exit
         ↑                   ↓
         └─── Iteration ─────┘
```

**Key Concepts:**

1. **Nodes:** Agent functions that process state
   - `supervisor_agent` - Main coordinator
   - Tools delegate to specialist agents

2. **Edges:** Control flow between nodes
   - Conditional edges based on agent decisions
   - Tool results flow back to supervisor

3. **State:** Shared context across nodes
   - Messages list (conversation history)
   - User info and preferences
   - Current itinerary ID

4. **Checkpointer:** Persistence layer
   - MongoDB-backed state storage
   - Thread-based isolation

### Agent Communication Pattern

```python
# Supervisor delegates to specialist
@tool
async def find_flights(request: str) -> str:
    result = await flight_agent.ainvoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text

# Specialist executes and returns
flight_agent = create_agent(
    model=model,
    system_prompt=FLIGHT_AGENT_PROMPT,
    tools=[search_flights_with_amadeus]
)
```

### Middleware & Context Injection

**Dynamic Prompt Middleware:**
```python
@dynamic_prompt
def create_dynamic_prompt(request: ModelRequest) -> str:
    context = request.runtime.context
    user_id = context.get("user_id")
    user_info = context.get("user_info")
    itinerary_id = context.get("itinerary_id")

    return SUPERVISOR_PROMPT + f"""
    user_id: {user_id}
    user_info: {user_info}
    itinerary_id: {itinerary_id}
    """
```

**Benefits:**
- Runtime context injection
- User-specific prompts
- Access to user preferences
- Itinerary awareness

---

## Technology Stack

### Backend Framework
- **FastAPI** - Modern async web framework
  - Auto-generated OpenAPI docs
  - Pydantic validation
  - Async request handling
  - Dependency injection

### AI/ML Stack
- **LangGraph** - Agent orchestration framework
  - Multi-agent coordination
  - State management
  - Checkpointing
  - Tool/function calling

- **LangChain** - LLM framework
  - Message abstractions
  - Tool definitions
  - Model integrations

- **OpenAI** - LLM provider
  - GPT-4o-nano model
  - Function calling
  - Chat completions

### Database
- **MongoDB** - Document database
  - Conversation state storage
  - User profiles
  - Checkpoint persistence

- **Azure Cosmos DB** - Cloud database
  - Itinerary storage
  - Global distribution
  - Multi-model support

### External APIs
- **Amadeus API** - Travel data
- **Google Maps API** - Location services
- **Auth0** - Authentication

### Development Tools
- **uv** - Fast Python package manager
- **Pydantic** - Data validation
- **PyJWT** - JWT verification
- **python-dotenv** - Environment management

---

## Deployment Architecture

### Docker Containerization

**Dockerfile:**
```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & Run:**
```bash
docker build -t vacation-agent .
docker run -p 8000:8000 vacation-agent
```

### Azure Deployment

**Platform:** Azure App Service

**Configuration:**
- Runtime: Python 3.13
- Port: Derived from environment variable `PORT`
- Auto-scaling enabled
- HTTPS enforced

**Deployment File (`azure.yaml`):**
```yaml
name: vacation-agent
services:
  - name: vacation-agent
    language: python
```

### Environment Variables

**Required in Production:**
```bash
OPENAI_API_KEY=...
MONGO_URI=...
GOOGLE_MAPS_API=...
AUTH0_DOMAIN=...
AUTH0_API_AUDIENCE=...
AUTH0_ISSUER=...
AUTH0_ALGORITHMS=RS256
PORT=8000
```

### Production URLs

- **Frontend:** https://purple-sand-06148da0f.1.azurestaticapps.net
- **Backend:** https://vacai-b2gccfdrfde4bdbm.canadacentral-01.azurewebsites.net
- **Health:** https://{backend}/health

---

## Scalability & Performance

### Performance Optimizations

1. **Async/Await Throughout**
   - All I/O operations are async
   - Non-blocking API calls
   - Concurrent agent execution

2. **Database Indexing**
   - Index on `thread_id` for fast lookup
   - Index on `user_id` for profile queries

3. **Response Streaming** (Future)
   - Stream agent responses as they generate
   - Reduce perceived latency

4. **Caching** (Future)
   - Cache frequent searches
   - Redis for session state

### Scalability Strategies

1. **Horizontal Scaling**
   - Stateless FastAPI instances
   - Load balancer distribution
   - Shared MongoDB backend

2. **Agent Parallelization**
   - Multiple specialist agents run concurrently
   - Independent tool executions

3. **Rate Limiting**
   - Recursion limit prevents infinite loops (max 15)
   - API rate limiting on external calls

4. **Monitoring**
   - LangSmith for agent tracing (optional)
   - Application logs via Python logging
   - Health check endpoint for uptime monitoring

### Cost Optimization

1. **Model Selection**
   - GPT-4o-nano for cost efficiency
   - Temperature 0 for deterministic responses (fewer retries)

2. **Recursion Limits**
   - Max 15 agent steps prevents runaway costs

3. **Tool Call Prevention**
   - Explicit checks to prevent duplicate API calls
   - Prompt engineering to minimize iterations

---

## Development Workflow

### Local Development

```bash
# Setup
uv sync
source .venv/bin/activate

# Run FastAPI (production mode)
uvicorn main:app --reload

# Run LangGraph Studio (development mode)
langgraph dev

# Update dependencies
uv pip compile pyproject.toml -o requirements.txt
```

### LangGraph Studio

**Configuration (`langgraph.json`):**
```json
{
  "graph": "agent.graph_dev:graph",
  "checkpointer": "memory"
}
```

**Benefits:**
- Visual graph debugging
- Step-by-step execution
- State inspection
- Message history viewer

### Testing

```bash
# Test endpoint
curl -X POST http://localhost:8000/api/chat/test-thread \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "Find flights to Tokyo"}'

# Health check
curl http://localhost:8000/health
```

---

## Future Enhancements

### Planned Features
1. **Booking Integration** - Actually book flights/hotels
2. **Payment Processing** - Handle transactions
3. **Multi-language Support** - i18n for global users
4. **Voice Interface** - Speech-to-text integration
5. **Mobile App** - Native iOS/Android clients
6. **Calendar Integration** - Sync with Google Calendar
7. **Price Alerts** - Monitor price changes
8. **Collaborative Planning** - Share trips with friends

### Technical Improvements
1. **GraphQL API** - More flexible data fetching
2. **WebSocket Support** - Real-time updates
3. **Redis Caching** - Faster response times
4. **Prometheus Metrics** - Advanced monitoring
5. **A/B Testing Framework** - Optimize prompts
6. **Circuit Breakers** - Better fault tolerance
7. **Service Mesh** - Advanced microservice features

---

## Conclusion

This system provides a robust, scalable foundation for AI-powered vacation planning. The supervisor-agent architecture enables specialization while maintaining conversational coherence, and the FastAPI/MongoDB stack ensures performance and reliability.

For questions or contributions, refer to the README.md and CLAUDE.md files.
