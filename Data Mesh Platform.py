import uvicorn
import logging
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator, ValidationError
from datetime import datetime, timezone
from enum import Enum
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

# --- Configuration ---
class Settings:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
    MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "1000"))
    MAX_LINEAGE_ENTRIES = int(os.getenv("MAX_LINEAGE_ENTRIES", "10000"))
    API_KEY = os.getenv("API_KEY", "your-secret-api-key")

settings = Settings()

# --- Setup Logging ---
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Enums ---
class DataProductStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"

class LineageType(str, Enum):
    DIRECT = "direct"
    DERIVED = "derived"
    AGGREGATED = "aggregated"

# --- Enhanced Data Models ---
class DataProduct(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, regex="^[a-zA-Z0-9_-]+$")
    domain: str = Field(..., min_length=1, max_length=50)
    owner: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    schema: Dict[str, str] = Field(..., min_items=1)
    status: DataProductStatus = DataProductStatus.ACTIVE
    version: str = Field(default="1.0.0", regex="^\\d+\\.\\d+\\.\\d+$")
    tags: List[str] = Field(default_factory=list, max_items=10)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('schema')
    def validate_schema(cls, v):
        if not v:
            raise ValueError('Schema cannot be empty')
        for field_name, field_type in v.items():
            if not field_name or not field_type:
                raise ValueError('Schema fields must have non-empty names and types')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        return [tag.strip().lower() for tag in v if tag.strip()]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class LineageEntry(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    target: str = Field(..., min_length=1, max_length=100)
    transformation: str = Field(..., min_length=1, max_length=1000)
    lineage_type: LineageType = LineageType.DIRECT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('source', 'target')
    def validate_endpoints(cls, v):
        if not v.strip():
            raise ValueError('Source and target cannot be empty')
        return v.strip()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DataProductUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[DataProductStatus] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    schema: Optional[Dict[str, str]] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            return [tag.strip().lower() for tag in v if tag.strip()]
        return v

# --- Response Models ---
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Any = None

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    total_products: int
    total_lineage_entries: int

# --- Security ---
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

# --- Data Persistence ---
class DataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.products_file = self.data_dir / "products.json"
        self.lineage_file = self.data_dir / "lineage.json"
    
    def save_products(self, products: Dict[str, DataProduct]):
        try:
            with open(self.products_file, 'w') as f:
                json.dump(
                    {k: v.dict() for k, v in products.items()}, 
                    f, 
                    indent=2, 
                    default=str
                )
            logger.info(f"Saved {len(products)} products to disk")
        except Exception as e:
            logger.error(f"Failed to save products: {e}")
    
    def load_products(self) -> Dict[str, DataProduct]:
        try:
            if self.products_file.exists():
                with open(self.products_file, 'r') as f:
                    data = json.load(f)
                    products = {}
                    for k, v in data.items():
                        # Convert datetime strings back to datetime objects
                        if 'created_at' in v:
                            v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                        if 'updated_at' in v:
                            v['updated_at'] = datetime.fromisoformat(v['updated_at'].replace('Z', '+00:00'))
                        products[k] = DataProduct(**v)
                    logger.info(f"Loaded {len(products)} products from disk")
                    return products
        except Exception as e:
            logger.error(f"Failed to load products: {e}")
        return {}
    
    def save_lineage(self, lineage: List[LineageEntry]):
        try:
            with open(self.lineage_file, 'w') as f:
                json.dump(
                    [entry.dict() for entry in lineage], 
                    f, 
                    indent=2, 
                    default=str
                )
            logger.info(f"Saved {len(lineage)} lineage entries to disk")
        except Exception as e:
            logger.error(f"Failed to save lineage: {e}")
    
    def load_lineage(self) -> List[LineageEntry]:
        try:
            if self.lineage_file.exists():
                with open(self.lineage_file, 'r') as f:
                    data = json.load(f)
                    lineage = []
                    for entry_data in data:
                        # Convert datetime strings back to datetime objects
                        if 'timestamp' in entry_data:
                            entry_data['timestamp'] = datetime.fromisoformat(entry_data['timestamp'].replace('Z', '+00:00'))
                        lineage.append(LineageEntry(**entry_data))
                    logger.info(f"Loaded {len(lineage)} lineage entries from disk")
                    return lineage
        except Exception as e:
            logger.error(f"Failed to load lineage: {e}")
        return []

# --- Initialize Data Store ---
data_store = DataStore(settings.DATA_DIR)

# --- In-Memory Catalogs with Persistence ---
data_products: Dict[str, DataProduct] = data_store.load_products()
lineage: List[LineageEntry] = data_store.load_lineage()

# --- Startup/Shutdown Events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Data Mesh Platform")
    logger.info(f"Loaded {len(data_products)} products and {len(lineage)} lineage entries")
    yield
    # Shutdown
    logger.info("Shutting down Data Mesh Platform")
    data_store.save_products(data_products)
    data_store.save_lineage(lineage)
    logger.info("Data saved successfully")

# --- FastAPI App ---
app = FastAPI(
    title="Data Mesh Platform",
    description="A robust data mesh platform for managing data products and lineage",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail}
    )

# --- Health Check ---
@app.get("/health", response_model=HealthCheck)
async def health_check():
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        total_products=len(data_products),
        total_lineage_entries=len(lineage)
    )

# --- Data Product Management ---
@app.post("/register_product", response_model=APIResponse, dependencies=[Depends(verify_api_key)])
async def register_product(product: DataProduct):
    if len(data_products) >= settings.MAX_PRODUCTS:
        raise HTTPException(
            status_code=429, 
            detail=f"Maximum number of products ({settings.MAX_PRODUCTS}) reached"
        )
    
    if product.name in data_products:
        raise HTTPException(status_code=409, detail="Product already exists")
    
    data_products[product.name] = product
    logger.info(f"Registered new product: {product.name} in domain: {product.domain}")
    
    # Save to disk periodically (every 10 products)
    if len(data_products) % 10 == 0:
        data_store.save_products(data_products)
    
    return APIResponse(
        success=True,
        message="Product registered successfully",
        data=product.dict()
    )

@app.get("/products", response_model=List[DataProduct])
async def list_products(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    status: Optional[DataProductStatus] = Query(None, description="Filter by status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    products = list(data_products.values())
    
    # Apply filters
    if domain:
        products = [p for p in products if p.domain.lower() == domain.lower()]
    if status:
        products = [p for p in products if p.status == status]
    if tag:
        products = [p for p in products if tag.lower() in p.tags]
    
    # Apply pagination
    total = len(products)
    products = products[offset:offset + limit]
    
    logger.info(f"Listed {len(products)} products (total: {total})")
    return products

@app.get("/product/{name}", response_model=DataProduct)
async def get_product(name: str):
    if name not in data_products:
        raise HTTPException(status_code=404, detail="Product not found")
    return data_products[name]

@app.put("/product/{name}", response_model=APIResponse, dependencies=[Depends(verify_api_key)])
async def update_product(name: str, update: DataProductUpdate):
    if name not in data_products:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = data_products[name]
    update_data = update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.now(timezone.utc)
    logger.info(f"Updated product: {name}")
    
    return APIResponse(
        success=True,
        message="Product updated successfully",
        data=product.dict()
    )

@app.delete("/product/{name}", response_model=APIResponse, dependencies=[Depends(verify_api_key)])
async def delete_product(name: str):
    if name not in data_products:
        raise HTTPException(status_code=404, detail="Product not found")
    
    del data_products[name]
    # Also remove related lineage entries
    global lineage
    lineage = [entry for entry in lineage if entry.source != name and entry.target != name]
    
    logger.info(f"Deleted product: {name}")
    
    return APIResponse(
        success=True,
        message="Product deleted successfully"
    )

# --- Lineage Management ---
@app.post("/register_lineage", response_model=APIResponse, dependencies=[Depends(verify_api_key)])
async def register_lineage(entry: LineageEntry):
    if len(lineage) >= settings.MAX_LINEAGE_ENTRIES:
        raise HTTPException(
            status_code=429, 
            detail=f"Maximum number of lineage entries ({settings.MAX_LINEAGE_ENTRIES}) reached"
        )
    
    # Validate that source and target products exist
    if entry.source not in data_products:
        raise HTTPException(status_code=400, detail=f"Source product '{entry.source}' not found")
    if entry.target not in data_products:
        raise HTTPException(status_code=400, detail=f"Target product '{entry.target}' not found")
    
    lineage.append(entry)
    logger.info(f"Registered lineage: {entry.source} -> {entry.target}")
    
    # Save to disk periodically (every 50 entries)
    if len(lineage) % 50 == 0:
        data_store.save_lineage(lineage)
    
    return APIResponse(
        success=True,
        message="Lineage registered successfully",
        data=entry.dict()
    )

@app.get("/lineage", response_model=List[LineageEntry])
async def get_lineage(
    source: Optional[str] = Query(None, description="Filter by source"),
    target: Optional[str] = Query(None, description="Filter by target"),
    lineage_type: Optional[LineageType] = Query(None, description="Filter by lineage type"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    filtered_lineage = lineage
    
    # Apply filters
    if source:
        filtered_lineage = [entry for entry in filtered_lineage if entry.source == source]
    if target:
        filtered_lineage = [entry for entry in filtered_lineage if entry.target == target]
    if lineage_type:
        filtered_lineage = [entry for entry in filtered_lineage if entry.lineage_type == lineage_type]
    
    # Apply pagination
    total = len(filtered_lineage)
    filtered_lineage = filtered_lineage[offset:offset + limit]
    
    logger.info(f"Retrieved {len(filtered_lineage)} lineage entries (total: {total})")
    return filtered_lineage

@app.get("/lineage/upstream/{product_name}", response_model=List[LineageEntry])
async def get_upstream_lineage(product_name: str):
    """Get all upstream dependencies for a product"""
    if product_name not in data_products:
        raise HTTPException(status_code=404, detail="Product not found")
    
    upstream = [entry for entry in lineage if entry.target == product_name]
    logger.info(f"Retrieved {len(upstream)} upstream dependencies for {product_name}")
    return upstream

@app.get("/lineage/downstream/{product_name}", response_model=List[LineageEntry])
async def get_downstream_lineage(product_name: str):
    """Get all downstream dependencies for a product"""
    if product_name not in data_products:
        raise HTTPException(status_code=404, detail="Product not found")
    
    downstream = [entry for entry in lineage if entry.source == product_name]
    logger.info(f"Retrieved {len(downstream)} downstream dependencies for {product_name}")
    return downstream

# --- Enhanced Domain APIs ---
@app.get("/sales/orders")
async def get_sales_orders(
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get sales orders with filtering and pagination"""
    # Mock data - in production, this would query the actual sales domain
    orders = [
        {"order_id": 1, "customer_id": 101, "amount": 250.0, "order_date": "2023-07-01"},
        {"order_id": 2, "customer_id": 102, "amount": 99.0, "order_date": "2023-07-02"},
        {"order_id": 3, "customer_id": 103, "amount": 175.0, "order_date": "2023-07-03"},
    ]
    
    # Apply date filtering if provided
    if start_date or end_date:
        # In production, implement proper date filtering
        pass
    
    logger.info(f"Retrieved {len(orders[:limit])} sales orders")
    return orders[:limit]

@app.get("/marketing/campaigns")
async def get_marketing_campaigns(
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False, description="Return only active campaigns")
):
    """Get marketing campaigns with filtering"""
    # Mock data - in production, this would query the actual marketing domain
    campaigns = [
        {"campaign_id": "A1", "name": "Summer Sale", "budget": 10000, "start_date": "2023-06-01", "active": True},
        {"campaign_id": "B2", "name": "Back to School", "budget": 8000, "start_date": "2023-08-01", "active": False},
        {"campaign_id": "C3", "name": "Holiday Special", "budget": 15000, "start_date": "2023-11-01", "active": True},
    ]
    
    if active_only:
        campaigns = [c for c in campaigns if c.get("active", True)]
    
    logger.info(f"Retrieved {len(campaigns[:limit])} marketing campaigns")
    return campaigns[:limit]

# --- Analytics Endpoints ---
@app.get("/analytics/domains", response_model=Dict[str, int])
async def get_domain_analytics():
    """Get analytics about products per domain"""
    domain_counts = {}
    for product in data_products.values():
        domain_counts[product.domain] = domain_counts.get(product.domain, 0) + 1
    
    return domain_counts

@app.get("/analytics/lineage-stats", response_model=Dict[str, Any])
async def get_lineage_analytics():
    """Get analytics about lineage relationships"""
    if not lineage:
        return {"total_entries": 0, "unique_sources": 0, "unique_targets": 0}
    
    sources = set(entry.source for entry in lineage)
    targets = set(entry.target for entry in lineage)
    
    return {
        "total_entries": len(lineage),
        "unique_sources": len(sources),
        "unique_targets": len(targets),
        "lineage_types": {lt.value: sum(1 for entry in lineage if entry.lineage_type == lt) for lt in LineageType}
    }

# --- Run the API ---
if __name__ == "__main__":
    uvicorn.run(
        app, 
        host=settings.HOST, 
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )