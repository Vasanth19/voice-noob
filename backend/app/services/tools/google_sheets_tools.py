"""Google Sheets integration tools for voice agents."""

import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


def parse_markdown_table(rows: list[list[str]]) -> dict[str, Any] | None:
    """Parse markdown table format from sheet data.

    Handles data pasted as markdown tables in a single column, like:
    | Item | Price | Description |
    |------|-------|-------------|
    | Burger | $10 | Delicious |

    Returns parsed data or None if not a markdown table.
    """
    if not rows:
        return None

    # Check if first cell looks like a markdown table row
    first_cell = rows[0][0] if rows[0] else ""
    if not (first_cell.startswith("|") and first_cell.endswith("|")):
        return None

    # Parse markdown table
    headers: list[str] = []
    items: list[dict[str, str]] = []

    for row in rows:
        cell = row[0] if row else ""
        if not cell.startswith("|"):
            continue

        # Skip separator rows (|---|---|---| or |:---|:---:|---:|)
        # Check if all cells contain only dashes, colons, and spaces
        test_cells = [c.strip() for c in cell.split("|")[1:-1]]
        if all(re.match(r"^[:\-]+$", c) for c in test_cells if c):
            continue

        # Parse cells from markdown row
        cells = [c.strip() for c in cell.split("|")[1:-1]]  # Remove empty first/last from split

        if not headers:
            # First non-separator row is headers
            headers = cells
        else:
            # Data row - create dict with headers
            item = {}
            for i, header in enumerate(headers):
                if header and i < len(cells):
                    item[header] = cells[i]
            if item:
                items.append(item)

    if headers and items:
        return {
            "success": True,
            "format": "markdown_table",
            "headers": headers,
            "items": items,
            "total_rows": len(items),
        }

    return None


class GoogleSheetsTools:
    """Google Sheets API integration tools.

    Provides tools for:
    - Reading data from Google Sheets
    - Searching for items in sheets (e.g., menu items)
    - Getting specific rows/items by name or category
    """

    BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, api_key: str, spreadsheet_id: str | None = None) -> None:
        """Initialize Google Sheets tools.

        Args:
            api_key: Google Sheets API key
            spreadsheet_id: Default spreadsheet ID (can be overridden per call)
        """
        self.api_key = api_key
        self.spreadsheet_id = spreadsheet_id
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def get_tool_definitions() -> list[dict[str, Any]]:
        """Get OpenAI function calling tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "sheets_get_data",
                    "description": "Get data from a Google Sheet. Use this to read menu items, product lists, pricing, or any tabular data stored in a spreadsheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {
                                "type": "string",
                                "description": "The Google Spreadsheet ID (from the URL). Optional if a default is configured.",
                            },
                            "range": {
                                "type": "string",
                                "description": "The range to read (e.g., 'Sheet1', 'Menu!A:E', 'A1:D10'). Default is 'Sheet1'.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sheets_search",
                    "description": "Search for items in a Google Sheet by keyword. Great for finding menu items, products by category, or any text search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search term (e.g., 'burger', 'vegetarian', 'dessert')",
                            },
                            "spreadsheet_id": {
                                "type": "string",
                                "description": "The Google Spreadsheet ID. Optional if a default is configured.",
                            },
                            "range": {
                                "type": "string",
                                "description": "The range to search in (default: 'Sheet1')",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sheets_get_item",
                    "description": "Get a specific item from a Google Sheet by exact name match. Use when asking about a specific menu item or product.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The exact name of the item to find (e.g., 'Cheeseburger', 'Caesar Salad')",
                            },
                            "spreadsheet_id": {
                                "type": "string",
                                "description": "The Google Spreadsheet ID. Optional if a default is configured.",
                            },
                            "range": {
                                "type": "string",
                                "description": "The range to search in (default: 'Sheet1')",
                            },
                        },
                        "required": ["item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sheets_list_sheets",
                    "description": "List all sheet tabs in a Google Spreadsheet. Useful to discover what data is available.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {
                                "type": "string",
                                "description": "The Google Spreadsheet ID. Optional if a default is configured.",
                            },
                        },
                        "required": [],
                    },
                },
            },
        ]

    def _get_spreadsheet_id(self, spreadsheet_id: str | None) -> str | None:
        """Get spreadsheet ID from param or default."""
        return spreadsheet_id or self.spreadsheet_id

    async def get_sheet_data(
        self,
        spreadsheet_id: str | None = None,
        range_: str = "Sheet1",
    ) -> dict[str, Any]:
        """Get data from a Google Sheet.

        Args:
            spreadsheet_id: Spreadsheet ID (uses default if not provided)
            range_: Range to read (e.g., 'Sheet1', 'Menu!A:E')

        Returns:
            Sheet data with headers and rows
        """
        sheet_id = self._get_spreadsheet_id(spreadsheet_id)
        if not sheet_id:
            return {
                "success": False,
                "error": "No spreadsheet ID provided. Please specify the spreadsheet_id.",
            }

        try:
            response = await self.client.get(
                f"/{sheet_id}/values/{range_}",
                params={"key": self.api_key},
            )

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": f"Spreadsheet not found or not accessible. Make sure the sheet is public or shared.",
                }

            if response.status_code != 200:
                logger.error(
                    "sheets_api_error",
                    status=response.status_code,
                    response=response.text,
                )
                return {
                    "success": False,
                    "error": f"Failed to read sheet: {response.status_code}",
                }

            data = response.json()
            values = data.get("values", [])

            if not values:
                return {
                    "success": True,
                    "message": "Sheet is empty",
                    "headers": [],
                    "rows": [],
                    "total_rows": 0,
                }

            # Try parsing as markdown table first (handles pasted markdown tables)
            md_result = parse_markdown_table(values)
            if md_result:
                return md_result

            # Skip empty rows at the start to find headers
            header_row_idx = 0
            for idx, row in enumerate(values):
                if row and any(cell.strip() for cell in row if isinstance(cell, str)):
                    header_row_idx = idx
                    break

            headers = values[header_row_idx] if header_row_idx < len(values) else []
            rows = values[header_row_idx + 1:] if header_row_idx + 1 < len(values) else []

            # Check if this looks like a key-value format (pairs like "Key", "Value", "Key2", "Value2")
            # This handles sheets structured as metadata rather than tabular data
            if headers and len(headers) >= 2 and not rows:
                # Convert alternating key-value pairs to a single item
                kv_item = {}
                for i in range(0, len(headers) - 1, 2):
                    key = headers[i]
                    value = headers[i + 1] if i + 1 < len(headers) else ""
                    if key:
                        kv_item[key] = value
                if kv_item:
                    return {
                        "success": True,
                        "format": "key_value",
                        "data": kv_item,
                        "message": "Sheet contains key-value pairs (metadata format)",
                        "total_items": 1,
                    }

            # Convert rows to dicts with headers (standard tabular format)
            items = []
            for row in rows:
                item = {}
                for i, header in enumerate(headers):
                    if header:  # Skip empty header columns
                        item[header] = row[i] if i < len(row) else ""
                if item:  # Only add non-empty items
                    items.append(item)

            return {
                "success": True,
                "headers": [h for h in headers if h],  # Filter empty headers
                "items": items,
                "total_rows": len(items),
            }

        except httpx.RequestError as e:
            logger.error("sheets_request_error", error=str(e))
            return {"success": False, "error": f"Request failed: {e!s}"}

    async def search_sheet(
        self,
        query: str,
        spreadsheet_id: str | None = None,
        range_: str = "Sheet1",
    ) -> dict[str, Any]:
        """Search for items in a sheet by keyword.

        Args:
            query: Search term
            spreadsheet_id: Spreadsheet ID
            range_: Range to search

        Returns:
            Matching rows
        """
        # First get all data
        result = await self.get_sheet_data(spreadsheet_id, range_)
        if not result.get("success"):
            return result

        items = result.get("items", [])
        query_lower = query.lower()

        # Search all fields for the query
        matches = []
        for item in items:
            for value in item.values():
                if query_lower in str(value).lower():
                    matches.append(item)
                    break

        return {
            "success": True,
            "query": query,
            "matches": matches,
            "total_matches": len(matches),
        }

    async def get_item(
        self,
        item_name: str,
        spreadsheet_id: str | None = None,
        range_: str = "Sheet1",
    ) -> dict[str, Any]:
        """Get a specific item by name.

        Args:
            item_name: Item name to find
            spreadsheet_id: Spreadsheet ID
            range_: Range to search

        Returns:
            Matching item or not found
        """
        result = await self.get_sheet_data(spreadsheet_id, range_)
        if not result.get("success"):
            return result

        items = result.get("items", [])
        item_name_lower = item_name.lower()

        # Look for exact or close match in first column (usually name/item column)
        for item in items:
            # Check all columns for the item name
            for key, value in item.items():
                if item_name_lower == str(value).lower():
                    return {
                        "success": True,
                        "found": True,
                        "item": item,
                    }

        # Try partial match
        for item in items:
            for key, value in item.items():
                if item_name_lower in str(value).lower():
                    return {
                        "success": True,
                        "found": True,
                        "item": item,
                        "partial_match": True,
                    }

        return {
            "success": True,
            "found": False,
            "message": f"No item found matching '{item_name}'",
        }

    async def list_sheets(
        self,
        spreadsheet_id: str | None = None,
    ) -> dict[str, Any]:
        """List all sheet tabs in a spreadsheet.

        Args:
            spreadsheet_id: Spreadsheet ID

        Returns:
            List of sheet names
        """
        sheet_id = self._get_spreadsheet_id(spreadsheet_id)
        if not sheet_id:
            return {
                "success": False,
                "error": "No spreadsheet ID provided.",
            }

        try:
            response = await self.client.get(
                f"/{sheet_id}",
                params={
                    "key": self.api_key,
                    "fields": "sheets.properties.title",
                },
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get spreadsheet info: {response.status_code}",
                }

            data = response.json()
            sheets = [
                sheet["properties"]["title"]
                for sheet in data.get("sheets", [])
            ]

            return {
                "success": True,
                "sheets": sheets,
                "total_sheets": len(sheets),
            }

        except httpx.RequestError as e:
            logger.error("sheets_request_error", error=str(e))
            return {"success": False, "error": f"Request failed: {e!s}"}

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if tool_name == "sheets_get_data":
            return await self.get_sheet_data(
                spreadsheet_id=arguments.get("spreadsheet_id"),
                range_=arguments.get("range", "Sheet1"),
            )

        if tool_name == "sheets_search":
            return await self.search_sheet(
                query=arguments.get("query", ""),
                spreadsheet_id=arguments.get("spreadsheet_id"),
                range_=arguments.get("range", "Sheet1"),
            )

        if tool_name == "sheets_get_item":
            return await self.get_item(
                item_name=arguments.get("item_name", ""),
                spreadsheet_id=arguments.get("spreadsheet_id"),
                range_=arguments.get("range", "Sheet1"),
            )

        if tool_name == "sheets_list_sheets":
            return await self.list_sheets(
                spreadsheet_id=arguments.get("spreadsheet_id"),
            )

        return {"success": False, "error": f"Unknown tool: {tool_name}"}
