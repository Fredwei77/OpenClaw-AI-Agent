"""
Shopify Agent - Shopify 电商平台集成 Agent
用于 Shopify 店铺管理、产品同步、订单处理

功能：
1. Shopify API 集成 (REST Admin API)
2. 产品目录同步
3. 库存监控
4. 订单处理
5. 数据分析
"""

import os
import sys
import asyncio
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent


@dataclass
class ShopifyProduct:
    """Shopify 产品"""
    id: int
    title: str
    description: str = ""
    price: float = 0.0
    inventory: int = 0
    images: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    variants: List[Dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ShopifyAgent(BaseAgent):
    """
    Shopify 电商平台 Agent

    需要配置：
    - SHOPIFY_SHOP_URL: 店铺 URL (e.g., mystore.myshopify.com)
    - SHOPIFY_ACCESS_TOKEN: API Access Token
    """

    def __init__(
        self,
        name: str = "ShopifyAgent",
        browser_manager=None,
        db=None,
        shop_url: str = None,
        access_token: str = None
    ):
        super().__init__(name, browser_manager, db)

        self.shop_url = shop_url or os.getenv("SHOPIFY_SHOP_URL", "")
        self.access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        self.api_version = "2024-01"
        self._session = None

    def _get_api_headers(self) -> Dict:
        """获取 API 请求头"""
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _get_base_url(self) -> str:
        """获取 API 基础 URL"""
        return f"https://{self.shop_url}/admin/api/{self.api_version}"

    def _is_configured(self) -> bool:
        """检查是否配置了 Shopify 凭证"""
        return bool(self.shop_url and self.access_token)

    async def run(self, task: dict) -> Dict:
        """
        执行 Shopify 任务

        Args:
            task: {
                "action": str,           # sync_products | get_orders | update_inventory | analytics | scan_store
                "params": Dict           # 任务参数
            }

        Returns:
            Dict: 执行结果
        """
        if not self._is_configured():
            return await self._mock_result("Shopify credentials not configured")

        action = task.get("action", "sync_products")
        params = task.get("params", {})

        print(f"[ShopifyAgent] Running action: {action}")

        try:
            if action == "sync_products":
                return await self._sync_products(params)
            elif action == "get_orders":
                return await self._get_orders(params)
            elif action == "update_inventory":
                return await self._update_inventory(params)
            elif action == "analytics":
                return await self._analytics(params)
            elif action == "scan_store":
                return await self._scan_store(params)
            elif action == "get_product":
                return await self._get_product(params)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            print(f"[ShopifyAgent] Error running action {action}: {e}")
            return {"error": str(e), "action": action}

    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """
        发起 HTTP 请求到 Shopify API
        """
        import aiohttp

        url = f"{self._get_base_url()}{endpoint}"
        headers = self._get_api_headers()

        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        return await response.json()
                elif method == "POST":
                    async with session.post(url, headers=headers, json=data) as response:
                        return await response.json()
                elif method == "PUT":
                    async with session.put(url, headers=headers, json=data) as response:
                        return await response.json()
                elif method == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        return await response.json()
            except aiohttp.ClientError as e:
                print(f"[ShopifyAgent] HTTP request failed: {e}")
                return {"error": str(e)}

    async def _sync_products(self, params: Dict) -> Dict:
        """同步产品目录"""
        limit = params.get("limit", 250)
        status = params.get("status", "active")

        response = await self._make_request(
            "GET",
            f"/products.json?limit={limit}&status={status}"
        )

        if "error" in response:
            return await self._mock_result(f"API Error: {response['error']}")

        products = response.get("products", [])

        formatted_products = []
        for p in products:
            product = self._format_product(p)
            formatted_products.append(product)

            if self.db:
                try:
                    await self._save_product(product)
                except Exception as e:
                    print(f"[ShopifyAgent] Failed to save product {p.get('id')}: {e}")

        return {
            "action": "sync_products",
            "total_products": len(formatted_products),
            "saved_to_db": len(formatted_products) if self.db else 0,
            "products": formatted_products[:10]
        }

    def _format_product(self, p: Dict) -> Dict:
        """格式化 Shopify 产品数据"""
        tags = p.get("tags", "").split(", ") if p.get("tags") else []
        images = [img.get("src", "") for img in p.get("images", []) if img.get("src")]
        variants = p.get("variants", [])
        price = float(variants[0].get("price", 0)) if variants else 0.0

        inventory_quantity = sum(int(v.get("inventory_quantity", 0)) for v in variants)

        return {
            "id": p.get("id"),
            "title": p.get("title"),
            "description": p.get("body_html", "")[:500],
            "price": price,
            "inventory": inventory_quantity,
            "tags": tags,
            "images": images,
            "variants": variants,
            "created_at": p.get("created_at", ""),
            "updated_at": p.get("updated_at", ""),
            "vendor": p.get("vendor", ""),
            "product_type": p.get("product_type", ""),
            "shopify_url": f"https://{self.shop_url}/admin/products/{p.get('id')}"
        }

    async def _get_product(self, params: Dict) -> Dict:
        """获取单个产品详情"""
        product_id = params.get("product_id")

        if not product_id:
            return {"error": "product_id is required"}

        response = await self._make_request("GET", f"/products/{product_id}.json")

        if "error" in response:
            return await self._mock_result(f"API Error: {response['error']}")

        product = response.get("product")
        if not product:
            return {"error": "Product not found"}

        return {
            "action": "get_product",
            "product": self._format_product(product)
        }

    async def _scan_store(self, params: Dict) -> Dict:
        """扫描 Shopify 店铺"""
        all_products = []
        limit = 250
        page_info = None

        while True:
            endpoint = f"/products.json?limit={limit}"
            if page_info:
                endpoint += f"&page_info={page_info}"

            response = await self._make_request("GET", endpoint)

            if "error" in response:
                break

            products = response.get("products", [])
            if not products:
                break

            for p in products:
                all_products.append(self._format_product(p))

            link_header = response.get("link_header") or ""
            next_link = None
            for link in link_header.split(",") if isinstance(link_header, str) else []:
                if 'rel="next"' in link:
                    import re
                    match = re.search(r'page_info=([^&>]+)', link)
                    if match:
                        next_link = match.group(1)
                        break

            if next_link:
                page_info = next_link
            else:
                break

            if len(all_products) >= 1000:
                break

        stats = self._calculate_store_stats(all_products)

        return {
            "action": "scan_store",
            "shop_url": self.shop_url,
            "total_products": len(all_products),
            "products": all_products[:50],
            "statistics": stats
        }

    def _calculate_store_stats(self, products: List[Dict]) -> Dict:
        """计算店铺统计信息"""
        if not products:
            return {}

        total_inventory = sum(p.get("inventory", 0) for p in products)
        prices = [p.get("price", 0) for p in products if p.get("price", 0) > 0]

        tag_counts = {}
        for p in products:
            for tag in p.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        type_counts = {}
        for p in products:
            ptype = p.get("product_type", "Unknown")
            if ptype:
                type_counts[ptype] = type_counts.get(ptype, 0) + 1

        return {
            "total_inventory": total_inventory,
            "average_price": sum(prices) / len(prices) if prices else 0,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "product_types": type_counts
        }

    async def _get_orders(self, params: Dict) -> Dict:
        """获取订单列表"""
        limit = min(params.get("limit", 50), 250)
        status = params.get("status", "any")
        created_at_min = params.get("created_at_min")

        endpoint = f"/orders.json?limit={limit}&status={status}"
        if created_at_min:
            endpoint += f"&created_at_min={created_at_min}"

        response = await self._make_request("GET", endpoint)

        if "error" in response:
            return await self._mock_result(f"API Error: {response['error']}")

        orders = response.get("orders", [])

        formatted_orders = []
        for o in orders:
            formatted_orders.append({
                "id": o.get("id"),
                "order_number": o.get("order_number"),
                "email": o.get("email", ""),
                "customer": f"{o.get('first_name', '')} {o.get('last_name', '')}".strip(),
                "total": float(o.get("total_price", 0)),
                "subtotal": float(o.get("subtotal_price", 0)),
                "tax": float(o.get("total_tax", 0)),
                "shipping": float(o.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", 0)),
                "status": o.get("financial_status"),
                "fulfillment_status": o.get("fulfillment_status"),
                "created_at": o.get("created_at"),
                "line_items_count": len(o.get("line_items", []))
            })

        return {
            "action": "get_orders",
            "total_orders": len(formatted_orders),
            "orders": formatted_orders
        }

    async def _update_inventory(self, params: Dict) -> Dict:
        """更新库存"""
        inventory_item_id = params.get("inventory_item_id")
        location_id = params.get("location_id")
        quantity = params.get("quantity")

        if not all([inventory_item_id, location_id, quantity is not None]):
            return {"error": "inventory_item_id, location_id, and quantity are required"}

        endpoint = "/inventory_levels/set.json"
        data = {
            "location_id": location_id,
            "inventory_item_id": inventory_item_id,
            "available": quantity
        }

        response = await self._make_request("POST", endpoint, data)

        if "error" in response:
            return await self._mock_result(f"API Error: {response['error']}")

        return {
            "action": "update_inventory",
            "inventory_item_id": inventory_item_id,
            "location_id": location_id,
            "new_quantity": quantity,
            "updated": True
        }

    async def _analytics(self, params: Dict) -> Dict:
        """获取分析数据"""
        days = params.get("days", 30)
        created_at_min = (datetime.now() - timedelta(days=days)).isoformat()

        response = await self._make_request(
            "GET",
            f"/orders.json?created_at_min={created_at_min}&status=any&limit=250"
        )

        if "error" in response:
            return await self._mock_result(f"API Error: {response['error']}")

        orders = response.get("orders", [])

        total_sales = sum(float(o.get("total_price", 0)) for o in orders)
        total_orders = len(orders)
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0

        sales_by_day = {}
        for o in orders:
            date = o.get("created_at", "")[:10]
            if date:
                sales_by_day[date] = sales_by_day.get(date, 0) + float(o.get("total_price", 0))

        product_sales = {}
        for o in orders:
            for item in o.get("line_items", []):
                title = item.get("title", "Unknown")
                product_sales[title] = product_sales.get(title, 0) + item.get("quantity", 0)

        top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "action": "analytics",
            "period_days": days,
            "total_sales": round(total_sales, 2),
            "total_orders": total_orders,
            "average_order_value": round(avg_order_value, 2),
            "top_products": [{"name": p[0], "quantity": p[1]} for p in top_products],
            "sales_by_day": [{"date": k, "sales": round(v, 2)} for k, v in sorted(sales_by_day.items())]
        }

    async def _save_product(self, product: Dict):
        """保存产品到数据库"""
        if not self.db:
            return

        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO products (shopify_product_id, title, description, price, inventory, tags, images, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (shopify_product_id)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        price = EXCLUDED.price,
                        inventory = EXCLUDED.inventory,
                        tags = EXCLUDED.tags,
                        images = EXCLUDED.images,
                        updated_at = NOW()
                """,
                    product.get("id"),
                    product.get("title"),
                    product.get("description", ""),
                    product.get("price", 0),
                    product.get("inventory", 0),
                    product.get("tags", []),
                    json.dumps(product.get("images", []))
                )
        except Exception as e:
            print(f"[ShopifyAgent] Database save error: {e}")

    async def _mock_result(self, message: str) -> Dict:
        """返回模拟结果"""
        return {
            "status": "mock",
            "message": message,
            "note": "Configure SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN for real integration"
        }


# Standalone execution
async def execute_shopify_task(task: dict) -> Dict:
    """Execute Shopify task"""
    agent = ShopifyAgent()
    return await agent.run(task)


shopify_agent = ShopifyAgent
