# Data Mesh Platform 

A robust, production-ready data mesh platform for managing data products and lineage relationships across distributed domains. Built with FastAPI, this platform provides comprehensive APIs for data product registration, lineage tracking, and domain-specific data access.

##  Features

### Core Capabilities
- **Data Product Management**: Register, update, and manage data products across domains
- **Lineage Tracking**: Track data lineage relationships with confidence scoring
- **Domain APIs**: Domain-specific endpoints for sales, marketing, and other business areas
- **Analytics**: Built-in analytics for domain distribution and lineage statistics

### Production-Ready Features
- **Security**: API key authentication for write operations
- **Persistence**: Automatic data persistence to JSON files
- **Validation**: Comprehensive input validation with Pydantic models
- **Monitoring**: Health checks and structured logging
- **Scalability**: Configurable limits and pagination support
- **Error Handling**: Robust error handling with proper HTTP status codes

##  Quick Start

### Prerequisites
- Python 3.8+
- pip or poetry

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/data-mesh-platform.git
cd data-mesh-platform

# Install dependencies
pip install fastapi uvicorn pydantic

# Run the application
python main.py
```

The API will be available at `http://localhost:8000`

### Docker Setup (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

##  API Documentation

Once running, visit:
- **Interactive API Docs**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

##  Configuration

Configure the application using environment variables:

```bash
# Server Configuration
export HOST=0.0.0.0
export PORT=8000
export LOG_LEVEL=INFO

# Security
export API_KEY=your-secure-api-key-here

# Storage
export DATA_DIR=./data

# Limits
export MAX_PRODUCTS=1000
export MAX_LINEAGE_ENTRIES=10000
```

##  API Endpoints

### Authentication
All write operations require an API key in the Authorization header:
```bash
Authorization: Bearer your-api-key-here
```

### Data Products

#### Register a Data Product
```bash
POST /register_product
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "name": "customer-orders",
  "domain": "sales",
  "owner": "sales-team@company.com",
  "description": "Customer order data with transaction details",
  "schema": {
    "order_id": "integer",
    "customer_id": "integer",
    "amount": "decimal",
    "order_date": "date"
  },
  "tags": ["orders", "transactions", "sales"]
}
```

#### List Data Products
```bash
GET /products?domain=sales&status=active&limit=50&offset=0
```

#### Get Specific Product
```bash
GET /product/customer-orders
```

#### Update Product
```bash
PUT /product/customer-orders
Authorization: Bearer your-api-key

{
  "description": "Updated description",
  "status": "active",
  "tags": ["orders", "sales", "updated"]
}
```

#### Delete Product
```bash
DELETE /product/customer-orders
Authorization: Bearer your-api-key
```

### Data Lineage

#### Register Lineage
```bash
POST /register_lineage
Authorization: Bearer your-api-key

{
  "source": "raw-orders",
  "target": "customer-orders",
  "transformation": "Data cleaning and customer lookup",
  "lineage_type": "derived",
  "confidence": 0.95,
  "metadata": {
    "transformation_tool": "Apache Spark",
    "last_run": "2023-07-01T10:00:00Z"
  }
}
```

#### Get Lineage
```bash
GET /lineage?source=raw-orders&lineage_type=derived&limit=100
```

#### Get Upstream Dependencies
```bash
GET /lineage/upstream/customer-orders
```

#### Get Downstream Dependencies
```bash
GET /lineage/downstream/raw-orders
```

### Domain-Specific APIs

#### Sales Domain
```bash
GET /sales/orders?limit=100&start_date=2023-07-01&end_date=2023-07-31
```

#### Marketing Domain
```bash
GET /marketing/campaigns?active_only=true&limit=50
```

### Analytics

#### Domain Analytics
```bash
GET /analytics/domains
```

#### Lineage Statistics
```bash
GET /analytics/lineage-stats
```

##  Data Models

### DataProduct
```python
{
  "name": "string",           # Unique identifier
  "domain": "string",         # Business domain
  "owner": "string",          # Owner contact
  "description": "string",    # Product description
  "schema": {},              # Data schema definition
  "status": "active",        # active|deprecated|inactive
  "version": "1.0.0",        # Semantic version
  "tags": ["string"],        # Searchable tags
  "created_at": "datetime",  # Creation timestamp
  "updated_at": "datetime"   # Last update timestamp
}
```

### LineageEntry
```python
{
  "source": "string",              # Source data product
  "target": "string",              # Target data product
  "transformation": "string",      # Transformation description
  "lineage_type": "direct",        # direct|derived|aggregated
  "confidence": 0.95,              # Confidence score (0-1)
  "metadata": {},                  # Additional metadata
  "timestamp": "datetime"          # Registration timestamp
}
```

##  Architecture

### Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Domain APIs   │    │  Core Platform  │    │   Data Store    │
│                 │    │                 │    │                 │
│ • Sales         │────│ • Products      │────│ • JSON Files    │
│ • Marketing     │    │ • Lineage       │    │ • Persistence   │
│ • Finance       │    │ • Analytics     │    │ • Backup        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Registration**: Domains register their data products
2. **Lineage**: Track transformations and dependencies
3. **Discovery**: Users discover available data products
4. **Access**: Domain-specific APIs provide data access
5. **Analytics**: Monitor usage and relationships

##  Security

- **API Key Authentication**: Required for all write operations
- **Input Validation**: Comprehensive validation using Pydantic
- **Rate Limiting**: Configurable limits on products and lineage entries
- **CORS**: Configurable cross-origin resource sharing
- **Logging**: Audit trail for all operations

##  Data Storage

The platform uses JSON files for persistence:

```
data/
├── products.json     # Data product registry
└── lineage.json      # Lineage relationships
```

Data is automatically:
- Loaded on startup
- Saved on shutdown
- Periodically saved during operation
- Backed up with error handling

##  Deployment

### Production Deployment

```bash
# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Using gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Environment Variables for Production
```bash
export API_KEY=your-super-secure-api-key
export LOG_LEVEL=INFO
export MAX_PRODUCTS=10000
export MAX_LINEAGE_ENTRIES=100000
export DATA_DIR=/app/data
```

### Docker Compose
```yaml
version: '3.8'
services:
  data-mesh:
    build: .
    ports:
      - "8000:8000"
    environment:
      - API_KEY=your-secure-key
      - DATA_DIR=/app/data
    volumes:
      - ./data:/app/data
```

##  Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Logs
The application provides structured logging for:
- Product registrations and updates
- Lineage tracking
- API access patterns
- Error conditions
- Performance metrics

### Metrics
Built-in analytics endpoints provide:
- Product distribution by domain
- Lineage relationship statistics
- Usage patterns
- System health indicators

##  Testing

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest tests/

# Run with coverage
pytest --cov=main tests/
```

Example test:
```python
def test_register_product():
    response = client.post(
        "/register_product",
        json={
            "name": "test-product",
            "domain": "test",
            "owner": "test@example.com",
            "description": "Test product",
            "schema": {"field": "string"}
        },
        headers={"Authorization": "Bearer test-key"}
    )
    assert response.status_code == 200
```

##  Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run pre-commit hooks
pre-commit install

# Format code
black main.py
isort main.py

# Lint code
flake8 main.py
mypy main.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Support

- **Documentation**: Check the `/docs` endpoint when running
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions

##  Roadmap

- [ ] **Database Integration**: PostgreSQL/MongoDB support
- [ ] **Advanced Authentication**: OAuth2, RBAC
- [ ] **Schema Registry**: Avro/JSON Schema support
- [ ] **Event Streaming**: Kafka integration
- [ ] **Data Quality**: Automated quality checks
- [ ] **Visualization**: Lineage graph visualization
- [ ] **Metrics**: Prometheus/Grafana integration
- [ ] **Testing**: Comprehensive test suite
- [ ] **CLI Tool**: Command-line interface
- [ ] **Helm Charts**: Kubernetes deployment

##  Example Usage

```python
import requests

# Configure API
base_url = "http://localhost:8000"
headers = {"Authorization": "Bearer your-api-key"}

# Register a data product
product = {
    "name": "customer-analytics",
    "domain": "marketing",
    "owner": "data-team@company.com",
    "description": "Customer behavior analytics dataset",
    "schema": {
        "customer_id": "string",
        "event_type": "string",
        "timestamp": "datetime",
        "properties": "json"
    },
    "tags": ["analytics", "customer", "behavior"]
}

response = requests.post(f"{base_url}/register_product", json=product, headers=headers)
print(f"Product registered: {response.json()}")

# Register lineage
lineage = {
    "source": "raw-events",
    "target": "customer-analytics",
    "transformation": "Event aggregation and customer attribution",
    "lineage_type": "aggregated",
    "confidence": 0.9
}

response = requests.post(f"{base_url}/register_lineage", json=lineage, headers=headers)
print(f"Lineage registered: {response.json()}")
```

