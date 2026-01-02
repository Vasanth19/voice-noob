"""Google Docs integration tools for voice agents.

Provides knowledge base functionality by reading content from Google Docs.
Perfect for storing unstructured information like:
- Restaurant info, vibe, location, history
- FAQs and policies
- Product descriptions
- Any free-form content the AI should know about
"""

from http import HTTPStatus
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Constants for content parsing
MIN_HEADING_LENGTH = 3
MIN_COLON_HEADING_LENGTH = 2
SECTION_PREVIEW_LENGTH = 300


class GoogleDocsTools:
    """Google Docs API integration tools.

    Provides tools for:
    - Reading entire documents as knowledge base
    - Searching within document content
    - Getting document metadata
    """

    # Use Drive API for export (works with API key for public docs)
    DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
    DOCS_API_URL = "https://docs.googleapis.com/v1/documents"

    def __init__(self, api_key: str, document_id: str | None = None) -> None:
        """Initialize Google Docs tools.

        Args:
            api_key: Google API key (same as Sheets API key)
            document_id: Default document ID (can be overridden per call)
        """
        self.api_key = api_key
        self.document_id = document_id
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
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
                    "name": "docs_get_knowledge",
                    "description": (
                        "Get knowledge base content from a Google Doc. Use this to retrieve "
                        "information about the business like location, hours, policies, FAQs, "
                        "menu descriptions, vibe, history, or any other reference information. "
                        "The content is returned as plain text that you can use to answer questions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": (
                                    "The Google Doc ID (from the URL). "
                                    "Optional if a default is configured."
                                ),
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docs_search_knowledge",
                    "description": (
                        "Search for specific information within the knowledge base document. "
                        "Use this when you need to find particular details like hours, "
                        "specific menu items, policies, or answers to specific questions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "Search term or question (e.g., 'hours', 'parking', "
                                    "'vegetarian options', 'return policy')"
                                ),
                            },
                            "document_id": {
                                "type": "string",
                                "description": "The Google Doc ID. Optional if default configured.",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docs_get_section",
                    "description": (
                        "Get a specific section from the knowledge base by heading. "
                        "Use this when you know which section contains the information "
                        "(e.g., 'Menu', 'Location', 'FAQ', 'About Us')."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section_name": {
                                "type": "string",
                                "description": (
                                    "The section heading to retrieve "
                                    "(e.g., 'Menu', 'Hours', 'FAQ', 'About')"
                                ),
                            },
                            "document_id": {
                                "type": "string",
                                "description": "The Google Doc ID. Optional if default configured.",
                            },
                        },
                        "required": ["section_name"],
                    },
                },
            },
        ]

    def _get_document_id(self, document_id: str | None) -> str | None:
        """Get document ID from param or default."""
        return document_id or self.document_id

    async def get_document_content(  # noqa: PLR0911
        self,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Get full document content as plain text.

        Args:
            document_id: Document ID (uses default if not provided)

        Returns:
            Document content as text
        """
        doc_id = self._get_document_id(document_id)
        if not doc_id:
            return {
                "success": False,
                "error": "No document ID provided. Please specify the document_id.",
            }

        try:
            # Export document as plain text using Drive API
            response = await self.client.get(
                f"{self.DRIVE_API_URL}/{doc_id}/export",
                params={
                    "key": self.api_key,
                    "mimeType": "text/plain",
                },
            )

            if response.status_code == HTTPStatus.NOT_FOUND:
                return {
                    "success": False,
                    "error": (
                        "Document not found or not accessible. "
                        "Make sure the document is shared as 'Anyone with the link can view'."
                    ),
                }

            if response.status_code == HTTPStatus.FORBIDDEN:
                return {
                    "success": False,
                    "error": (
                        "Access denied. Please ensure the Google Doc is shared publicly "
                        "('Anyone with the link can view')."
                    ),
                }

            if response.status_code != HTTPStatus.OK:
                logger.error(
                    "docs_api_error",
                    status=response.status_code,
                    response=response.text[:500],
                )
                return {
                    "success": False,
                    "error": f"Failed to read document: {response.status_code}",
                }

            content = response.text

            if not content or not content.strip():
                return {
                    "success": True,
                    "message": "Document is empty",
                    "content": "",
                    "word_count": 0,
                }

            # Parse sections from content
            sections = self._parse_sections(content)

            return {
                "success": True,
                "content": content,
                "sections": list(sections.keys()),
                "word_count": len(content.split()),
                "char_count": len(content),
            }

        except httpx.RequestError as e:
            logger.exception("docs_request_error", error=str(e))
            return {"success": False, "error": f"Request failed: {e!s}"}

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse document content into sections based on headings.

        Recognizes:
        - Markdown headings (# Heading, ## Subheading)
        - ALL CAPS lines as headings
        - Lines ending with colon as headings

        Args:
            content: Document text content

        Returns:
            Dict mapping section names to their content
        """
        sections: dict[str, str] = {}
        current_section = "Introduction"
        current_content: list[str] = []

        for line in content.split("\n"):
            stripped = line.strip()

            # Check if this line is a heading
            is_heading = False
            heading_name = ""

            # Markdown headings
            if stripped.startswith("#"):
                is_heading = True
                heading_name = stripped.lstrip("#").strip()

            # ALL CAPS headings (at least 3 chars, all uppercase letters/spaces)
            elif (
                len(stripped) >= MIN_HEADING_LENGTH
                and stripped.replace(" ", "").isalpha()
                and stripped.isupper()
            ):
                is_heading = True
                heading_name = stripped.title()

            # Lines ending with colon (e.g., "Menu:")
            elif (
                stripped.endswith(":")
                and len(stripped) > MIN_COLON_HEADING_LENGTH
                and " " not in stripped
            ):
                is_heading = True
                heading_name = stripped.rstrip(":")

            if is_heading and heading_name:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                current_section = heading_name
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    async def search_content(
        self,
        query: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Search for content within the document.

        Args:
            query: Search term
            document_id: Document ID

        Returns:
            Matching content snippets
        """
        result = await self.get_document_content(document_id)
        if not result.get("success"):
            return result

        content = result.get("content", "")
        if not content:
            return {
                "success": True,
                "query": query,
                "matches": [],
                "message": "Document is empty",
            }

        query_lower = query.lower()
        lines = content.split("\n")
        matches: list[dict[str, Any]] = []

        # Search line by line with context
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Get context (2 lines before and after)
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = "\n".join(lines[start:end])

                matches.append(
                    {
                        "line_number": i + 1,
                        "line": line.strip(),
                        "context": context.strip(),
                    }
                )

        # Also search sections
        sections = self._parse_sections(content)
        matching_sections = []

        for section_name, section_content in sections.items():
            if query_lower in section_name.lower() or query_lower in section_content.lower():
                matching_sections.append(
                    {
                        "section": section_name,
                        "preview": section_content[:SECTION_PREVIEW_LENGTH]
                        + ("..." if len(section_content) > SECTION_PREVIEW_LENGTH else ""),
                    }
                )

        return {
            "success": True,
            "query": query,
            "line_matches": matches[:10],  # Limit to first 10 matches
            "section_matches": matching_sections,
            "total_line_matches": len(matches),
            "total_section_matches": len(matching_sections),
        }

    async def get_section(
        self,
        section_name: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific section by name.

        Args:
            section_name: Section heading to find
            document_id: Document ID

        Returns:
            Section content
        """
        result = await self.get_document_content(document_id)
        if not result.get("success"):
            return result

        content = result.get("content", "")
        if not content:
            return {
                "success": True,
                "found": False,
                "message": "Document is empty",
            }

        sections = self._parse_sections(content)
        section_name_lower = section_name.lower()

        # Try exact match first
        for name, section_content in sections.items():
            if name.lower() == section_name_lower:
                return {
                    "success": True,
                    "found": True,
                    "section_name": name,
                    "content": section_content,
                    "word_count": len(section_content.split()),
                }

        # Try partial match
        for name, section_content in sections.items():
            if section_name_lower in name.lower() or name.lower() in section_name_lower:
                return {
                    "success": True,
                    "found": True,
                    "section_name": name,
                    "content": section_content,
                    "word_count": len(section_content.split()),
                    "partial_match": True,
                }

        return {
            "success": True,
            "found": False,
            "message": f"No section found matching '{section_name}'",
            "available_sections": list(sections.keys()),
        }

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if tool_name == "docs_get_knowledge":
            return await self.get_document_content(
                document_id=arguments.get("document_id"),
            )

        if tool_name == "docs_search_knowledge":
            return await self.search_content(
                query=arguments.get("query", ""),
                document_id=arguments.get("document_id"),
            )

        if tool_name == "docs_get_section":
            return await self.get_section(
                section_name=arguments.get("section_name", ""),
                document_id=arguments.get("document_id"),
            )

        return {"success": False, "error": f"Unknown tool: {tool_name}"}
