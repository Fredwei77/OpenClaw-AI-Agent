from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from .auth import get_db_pool, get_current_user, UserResponse

router = APIRouter()

VALID_CATEGORIES = {
    "electronics", "clothing", "home", "beauty", "sports",
    "toys", "food", "books", "automotive", "other"
}


class ProductCreate(BaseModel):
    store_id: int
    product_name: str = Field(..., min_length=1, max_length=500)
    price: float = Field(..., gt=0)
    category: str
    rating: Optional[float] = Field(default=None, ge=0, le=5)

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of {VALID_CATEGORIES}")
        return v


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=500)
    price: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of {VALID_CATEGORIES}")
        return v


class ProductResponse(BaseModel):
    id: int
    store_id: int
    product_name: str
    price: float
    category: str
    rating: Optional[float]
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=ProductListResponse)
async def get_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    store_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=255),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get paginated list of products with optional filters."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price must be <= max_price")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions = ["p.user_id = $1"]
        params = [current_user.id]
        param_idx = 2

        if category:
            if category not in VALID_CATEGORIES:
                raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of {VALID_CATEGORIES}")
            conditions.append(f"p.category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if store_id:
            # Verify store ownership
            store = await conn.fetchrow("SELECT user_id FROM stores WHERE id = $1", store_id)
            if not store or store['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied to this store")
            conditions.append(f"p.store_id = ${param_idx}")
            params.append(store_id)
            param_idx += 1

        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(f"p.product_name ILIKE ${param_idx}")
            params.append(f"%{escaped}%")
            param_idx += 1

        if min_price is not None:
            conditions.append(f"p.price >= ${param_idx}")
            params.append(min_price)
            param_idx += 1

        if max_price is not None:
            conditions.append(f"p.price <= ${param_idx}")
            params.append(max_price)
            param_idx += 1

        if min_rating is not None:
            conditions.append(f"p.rating >= ${param_idx}")
            params.append(min_rating)
            param_idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        count_query = f"SELECT COUNT(*) as count FROM products p {where_clause}"
        total = await conn.fetchval(count_query, *params)

        offset = (page - 1) * page_size
        query = f"""
            SELECT p.id, p.store_id, p.product_name, p.price, p.category, p.rating, p.user_id, p.created_at
            FROM products p
            {where_clause}
            ORDER BY p.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await conn.fetch(query, *params)

        products = [
            ProductResponse(
                id=row['id'],
                store_id=row['store_id'],
                product_name=row['product_name'],
                price=float(row['price']),
                category=row['category'],
                rating=float(row['rating']) if row['rating'] is not None else None,
                user_id=row['user_id'],
                created_at=row['created_at']
            )
            for row in rows
        ]

        return ProductListResponse(
            products=products,
            total=total,
            page=page,
            page_size=page_size
        )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific product by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, store_id, product_name, price, category, rating, user_id, created_at FROM products WHERE id = $1 AND user_id = $2",
            product_id, current_user.id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(
            id=row['id'],
            store_id=row['store_id'],
            product_name=row['product_name'],
            price=float(row['price']),
            category=row['category'],
            rating=float(row['rating']) if row['rating'] is not None else None,
            user_id=row['user_id'],
            created_at=row['created_at']
        )


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new product."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Verify store ownership
        store = await conn.fetchrow("SELECT user_id FROM stores WHERE id = $1", product.store_id)
        if not store or store['user_id'] != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this store")

        row = await conn.fetchrow(
            """INSERT INTO products (store_id, product_name, price, category, rating, user_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING id, store_id, product_name, price, category, rating, user_id, created_at""",
            product.store_id, product.product_name, product.price,
            product.category, product.rating, current_user.id
        )
        return ProductResponse(
            id=row['id'],
            store_id=row['store_id'],
            product_name=row['product_name'],
            price=float(row['price']),
            category=row['category'],
            rating=float(row['rating']) if row['rating'] else None,
            user_id=row['user_id'],
            created_at=row['created_at']
        )


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    update: ProductUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update a product."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, user_id FROM products WHERE id = $1 AND user_id = $2", product_id, current_user.id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")

        updates = []
        params = []
        param_idx = 1

        if update.product_name is not None:
            updates.append(f"product_name = ${param_idx}")
            params.append(update.product_name)
            param_idx += 1

        if update.price is not None:
            updates.append(f"price = ${param_idx}")
            params.append(update.price)
            param_idx += 1

        if update.category is not None:
            if update.category not in VALID_CATEGORIES:
                raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of {VALID_CATEGORIES}")
            updates.append(f"category = ${param_idx}")
            params.append(update.category)
            param_idx += 1

        if update.rating is not None:
            updates.append(f"rating = ${param_idx}")
            params.append(update.rating)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([product_id, current_user.id])
        query = f"""
            UPDATE products SET {', '.join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING id, store_id, product_name, price, category, rating, user_id, created_at
        """

        row = await conn.fetchrow(query, *params)
        return ProductResponse(
            id=row['id'],
            store_id=row['store_id'],
            product_name=row['product_name'],
            price=float(row['price']),
            category=row['category'],
            rating=float(row['rating']) if row['rating'] else None,
            user_id=row['user_id'],
            created_at=row['created_at']
        )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a product."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, user_id FROM products WHERE id = $1 AND user_id = $2", product_id, current_user.id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        await conn.execute("DELETE FROM products WHERE id = $1 AND user_id = $2", product_id, current_user.id)
