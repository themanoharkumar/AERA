"""Report template definitions for the AERA Report Engine.

This module defines the ReportTemplate class, managing report layout, section ordering,
and template rendering structures.
"""

from typing import Any, Dict, List
from src.report.exceptions import TemplateError


class ReportTemplate:
    """Defines layouts and formats report sections into deterministic strings.

    Enforces reproducible layout order and renders sections into plain text representations.
    """

    def __init__(self, name: str = "Standard Incident Report Template") -> None:
        """Initialize the ReportTemplate.

        Args:
            name: The display name of the template.
        """
        self.name = name
        # Enforces deterministic layout ordering
        self.section_order = [
            "header",
            "incident_summary",
            "event_information",
            "decision_information",
            "evidence_information",
            "footer",
        ]

    def render(self, sections: Dict[str, str]) -> str:
        """Render sections dictionary into a deterministic, ordered layout string.

        Args:
            sections: Dictionary of section keys and their pre-formatted string content.

        Returns:
            The combined layout as a single string.

        Raises:
            TemplateError: If required sections are missing.
        """
        if not sections:
            raise TemplateError("Sections data cannot be empty.")

        # Verify all expected sections are present
        missing_sections = [sec for sec in self.section_order if sec not in sections]
        if missing_sections:
            raise TemplateError(f"Missing required sections for rendering: {missing_sections}")

        rendered_blocks: List[str] = []
        for section_key in self.section_order:
            content = sections[section_key]
            rendered_blocks.append(content)

        return "\n\n".join(rendered_blocks)
