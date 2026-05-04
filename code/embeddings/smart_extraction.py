"""Smart section extraction from documents based on query relevance."""

import re
from typing import List, Tuple, Optional


class SmartExtractor:
    """Extracts relevant sections from markdown documents intelligently."""

    @staticmethod
    def parse_yaml_front_matter(content: str) -> Tuple[dict, str]:
        """Extract YAML front matter and body from markdown.

        Args:
            content: Full document content

        Returns:
            Tuple of (metadata_dict, body_text)
        """
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if not match:
            return {}, content

        yaml_text = match.group(1)
        body = match.group(2)

        metadata = {}
        for line in yaml_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip().strip('"')

        return metadata, body

    @staticmethod
    def split_into_sections(content: str) -> List[Tuple[str, str]]:
        """Split markdown into sections with headers.

        Args:
            content: Markdown body text

        Returns:
            List of (header, section_content) tuples
        """
        sections = []
        current_header = "Introduction"
        current_content = []

        # Match headers (# ## ###, etc.) and collect content under them
        lines = content.split('\n')

        for line in lines:
            # Check if this is a header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if header_match:
                # Save previous section if it has content
                if current_content and any(c.strip() for c in current_content):
                    sections.append((current_header, '\n'.join(current_content).strip()))
                    current_content = []

                # Start new section
                level = len(header_match.group(1))
                current_header = header_match.group(2).strip()

            else:
                current_content.append(line)

        # Add last section
        if current_content and any(c.strip() for c in current_content):
            sections.append((current_header, '\n'.join(current_content).strip()))

        return sections

    @staticmethod
    def score_section(header: str, content: str, query: str) -> float:
        """Score a section's relevance to the query.

        Args:
            header: Section header/title
            content: Section body content
            query: User's search query

        Returns:
            Relevance score (0-1)
        """
        query_words = set(query.lower().split())
        header_lower = header.lower()
        content_lower = content.lower()

        score = 0.0

        # Header match (highest weight)
        for word in query_words:
            if word in header_lower:
                score += 0.3

        # Content match (lower weight)
        for word in query_words:
            # Count occurrences in content
            count = content_lower.count(word)
            if count > 0:
                score += min(0.1, count * 0.02)  # Max 0.1 per word

        return min(1.0, score)

    @staticmethod
    def extract_relevant_section(
        document_content: str,
        query: str,
        max_chars: int = 800
    ) -> str:
        """Extract the most relevant section from a document.

        Args:
            document_content: Full document markdown
            query: User's search query
            max_chars: Maximum characters to return

        Returns:
            Relevant section text (< max_chars)
        """
        # Parse document structure
        metadata, body = SmartExtractor.parse_yaml_front_matter(document_content)
        sections = SmartExtractor.split_into_sections(body)

        if not sections:
            return document_content[:max_chars]

        # Score and sort sections
        scored_sections = [
            (header, content, SmartExtractor.score_section(header, content, query))
            for header, content in sections
        ]

        # Sort by score (descending)
        scored_sections.sort(key=lambda x: -x[2])

        # Get the best section(s)
        result_parts = []
        total_chars = 0

        for header, content, score in scored_sections[:2]:  # Top 2 sections
            if score <= 0:  # Skip low-scoring sections
                continue

            # Add header
            header_text = f"\n## {header}\n"
            if total_chars + len(header_text) <= max_chars:
                result_parts.append(header_text)
                total_chars += len(header_text)

            # Add content (truncate if needed)
            remaining = max_chars - total_chars
            if remaining <= 100:
                break

            if len(content) > remaining:
                content = content[:remaining].rsplit('\n', 1)[0] + "\n[...more]"

            result_parts.append(content)
            total_chars += len(content)

            if total_chars >= max_chars:
                break

        result = "".join(result_parts).strip()

        # If empty, return first section
        if not result and sections:
            result = f"## {sections[0][0]}\n{sections[0][1]}"

        return result[:max_chars]

    @staticmethod
    def extract_action_items(content: str) -> List[str]:
        """Extract actionable steps from document content.

        Args:
            content: Document text

        Returns:
            List of action items (steps, commands, etc.)
        """
        items = []

        # Find numbered lists
        for match in re.finditer(r'^\d+\.\s+(.+)$', content, re.MULTILINE):
            items.append(match.group(1).strip())

        # Find bullet points
        for match in re.finditer(r'^[-*]\s+(.+)$', content, re.MULTILINE):
            items.append(match.group(1).strip())

        # Find code blocks
        for match in re.finditer(r'```\n(.+?)\n```', content, re.DOTALL):
            code = match.group(1).strip()
            if code:
                items.append(f"Code: {code[:100]}")

        return items[:5]  # Return top 5 items


def extract_relevant_content(
    full_content: str,
    query: str,
    max_chars: int = 1000
) -> str:
    """Smart extraction wrapper.

    Args:
        full_content: Full document content
        query: User's search query
        max_chars: Maximum output size

    Returns:
        Condensed relevant content (< max_chars)
    """
    try:
        extractor = SmartExtractor()
        relevant = extractor.extract_relevant_section(full_content, query, max_chars)

        # Add action items if present
        action_items = extractor.extract_action_items(relevant)
        if action_items:
            items_text = "\nKey steps:\n" + "\n".join(f"- {item}" for item in action_items[:3])
            if len(relevant) + len(items_text) <= max_chars:
                relevant += items_text

        return relevant

    except Exception as e:
        # Fallback to simple truncation
        return full_content[:max_chars]
