"""PDF generation service for scouting reports."""
from io import BytesIO
from typing import Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime


class PDFReportGenerator:
    """Generate PDF reports from scouting report data."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        # Section header style
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#2c3e50"),
                spaceAfter=12,
                spaceBefore=12,
                fontName="Helvetica-Bold",
                borderWidth=1,
                borderColor=colors.HexColor("#3498db"),
                borderPadding=5,
                backColor=colors.HexColor("#ecf0f1"),
            )
        )

        # Subsection style
        self.styles.add(
            ParagraphStyle(
                name="SubSection",
                parent=self.styles["Heading3"],
                fontSize=12,
                textColor=colors.HexColor("#34495e"),
                spaceAfter=8,
                fontName="Helvetica-Bold",
            )
        )

    def generate_pdf(self, report_data: Dict[str, Any]) -> BytesIO:
        """
        Generate a PDF from scouting report data.

        Args:
            report_data: The scouting report data dictionary

        Returns:
            BytesIO: PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # Container for the 'Flowable' objects
        elements = []

        # Add title
        elements.extend(self._generate_title(report_data.get("report_metadata", {})))

        # Add executive summary
        if "executive_summary" in report_data:
            elements.extend(self._generate_executive_summary(report_data["executive_summary"]))

        # Add statistical overview
        if "statistical_overview" in report_data:
            elements.extend(self._generate_statistical_overview(report_data["statistical_overview"]))

        # Add tactical analysis
        if "tactical_analysis" in report_data:
            elements.extend(self._generate_tactical_analysis(report_data["tactical_analysis"]))

        # Add physical profile
        if "physical_profile" in report_data:
            elements.extend(self._generate_physical_profile(report_data["physical_profile"]))

        # Add market analysis
        if "market_analysis" in report_data:
            elements.extend(self._generate_market_analysis(report_data["market_analysis"]))

        # Add comparison analysis
        if "comparison_analysis" in report_data:
            elements.extend(self._generate_comparison_analysis(report_data["comparison_analysis"]))

        # Add risk assessment
        if "risk_assessment" in report_data:
            elements.extend(self._generate_risk_assessment(report_data["risk_assessment"]))

        # Add negotiation strategy
        if "negotiation_strategy" in report_data:
            elements.extend(self._generate_negotiation_strategy(report_data["negotiation_strategy"]))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer

    def _generate_title(self, metadata: Dict[str, Any]) -> list:
        """Generate title page elements."""
        elements = []

        # Main title
        title_text = f"Scouting Report"
        elements.append(Paragraph(title_text, self.styles["CustomTitle"]))
        elements.append(Spacer(1, 0.2 * inch))

        # Player and team info
        player_name = metadata.get("player_name", "Unknown Player")
        team_name = metadata.get("team_name", "Unknown Team")
        generated_date = metadata.get("generated_date", datetime.now().strftime("%Y-%m-%d"))

        info_data = [
            ["Player:", player_name],
            ["Team:", team_name],
            ["Generated:", generated_date],
        ]

        info_table = Table(info_data, colWidths=[2 * inch, 4 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(info_table)
        elements.append(Spacer(1, 0.5 * inch))

        return elements

    def _generate_executive_summary(self, data: Dict[str, Any]) -> list:
        """Generate executive summary section."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))

        # Recommendation and action
        recommendation = data.get("recommendation", "N/A")
        action = data.get("action", "N/A")
        match_score = data.get("match_score", 0)
        percentile = data.get("overall_percentile", 0)

        summary_data = [
            ["Recommendation:", recommendation],
            ["Action:", action],
            ["Match Score:", f"{match_score:.1f}%"],
            ["Overall Percentile:", f"{percentile}th"],
        ]

        summary_table = Table(summary_data, colWidths=[2 * inch, 4 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 0.2 * inch))

        # Executive statement
        statement = data.get("executive_statement", "")
        if statement:
            elements.append(Paragraph("<b>Executive Statement:</b>", self.styles["SubSection"]))
            elements.append(Paragraph(statement, self.styles["BodyText"]))
            elements.append(Spacer(1, 0.1 * inch))

        # Key findings
        key_findings = data.get("key_findings", [])
        if key_findings:
            elements.append(Paragraph("<b>Key Findings:</b>", self.styles["SubSection"]))
            for finding in key_findings:
                elements.append(Paragraph(f"• {finding}", self.styles["BodyText"]))
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _generate_statistical_overview(self, data: Dict[str, Any]) -> list:
        """Generate statistical overview section."""
        elements = []

        elements.append(Paragraph("Statistical Overview", self.styles["SectionHeader"]))

        # Statistical strengths
        strengths = data.get("statistical_strengths", [])
        if strengths:
            elements.append(Paragraph("<b>Strengths:</b>", self.styles["SubSection"]))
            for strength in strengths[:5]:  # Limit to top 5
                elements.append(Paragraph(f"• {strength}", self.styles["BodyText"]))
            elements.append(Spacer(1, 0.1 * inch))

        # Statistical weaknesses
        weaknesses = data.get("statistical_weaknesses", [])
        if weaknesses:
            elements.append(Paragraph("<b>Weaknesses:</b>", self.styles["SubSection"]))
            for weakness in weaknesses[:5]:  # Limit to top 5
                elements.append(Paragraph(f"• {weakness}", self.styles["BodyText"]))
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _generate_tactical_analysis(self, data: Dict[str, Any]) -> list:
        """Generate tactical analysis section."""
        elements = []

        elements.append(Paragraph("Tactical Analysis", self.styles["SectionHeader"]))

        # Formation compatibility
        formation = data.get("formation_compatibility", {})
        if formation:
            elements.append(Paragraph("<b>Formation Compatibility:</b>", self.styles["SubSection"]))
            best_fit = formation.get("best_fit", "N/A")
            score = formation.get("compatibility_score", 0)
            elements.append(
                Paragraph(
                    f"Best Formation: {best_fit} (Score: {score:.1f}%)",
                    self.styles["BodyText"],
                )
            )
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_physical_profile(self, data: Dict[str, Any]) -> list:
        """Generate physical profile section."""
        elements = []

        elements.append(Paragraph("Physical Profile", self.styles["SectionHeader"]))

        # Athletic scores
        athletic_scores = data.get("athletic_scores", {})
        if athletic_scores:
            elements.append(Paragraph("<b>Athletic Attributes:</b>", self.styles["SubSection"]))
            for attr, value in athletic_scores.items():
                if isinstance(value, dict):
                    score = value.get("score", 0)
                    percentile = value.get("percentile", 0)
                    elements.append(
                        Paragraph(
                            f"• {attr.replace('_', ' ').title()}: {score:.1f} ({percentile}th percentile)",
                            self.styles["BodyText"],
                        )
                    )
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_market_analysis(self, data: Dict[str, Any]) -> list:
        """Generate market analysis section."""
        elements = []

        elements.append(Paragraph("Market Analysis", self.styles["SectionHeader"]))

        # Current market value
        market_value = data.get("current_market_value", 0)
        elements.append(
            Paragraph(
                f"<b>Current Market Value:</b> €{market_value:,.0f}",
                self.styles["BodyText"],
            )
        )
        elements.append(Spacer(1, 0.1 * inch))

        # Value assessment
        value_assessment = data.get("value_assessment", {})
        if value_assessment:
            assessment = value_assessment.get("assessment", "N/A")
            elements.append(
                Paragraph(f"<b>Assessment:</b> {assessment}", self.styles["BodyText"])
            )
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_comparison_analysis(self, data: Dict[str, Any]) -> list:
        """Generate comparison analysis section."""
        elements = []

        elements.append(Paragraph("Comparison Analysis", self.styles["SectionHeader"]))

        # Upgrade assessment
        upgrade = data.get("upgrade_assessment", "")
        if upgrade:
            elements.append(Paragraph(upgrade, self.styles["BodyText"]))
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_risk_assessment(self, data: Dict[str, Any]) -> list:
        """Generate risk assessment section."""
        elements = []

        elements.append(Paragraph("Risk Assessment", self.styles["SectionHeader"]))

        # Overall risk
        risk_level = data.get("overall_risk_level", "N/A")
        risk_score = data.get("risk_score", 0)

        risk_data = [
            ["Risk Level:", risk_level],
            ["Risk Score:", f"{risk_score:.1f}"],
        ]

        risk_table = Table(risk_data, colWidths=[2 * inch, 4 * inch])
        risk_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(risk_table)
        elements.append(Spacer(1, 0.2 * inch))

        # Mitigation plan
        mitigation = data.get("mitigation_plan", [])
        if mitigation:
            elements.append(Paragraph("<b>Mitigation Plan:</b>", self.styles["SubSection"]))
            for item in mitigation:
                elements.append(Paragraph(f"• {item}", self.styles["BodyText"]))
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_negotiation_strategy(self, data: Dict[str, Any]) -> list:
        """Generate negotiation strategy section."""
        elements = []

        elements.append(Paragraph("Negotiation Strategy", self.styles["SectionHeader"]))

        # Offer strategy
        offer_strategy = data.get("offer_strategy", {})
        if offer_strategy:
            elements.append(Paragraph("<b>Offer Strategy:</b>", self.styles["SubSection"]))
            for key, value in offer_strategy.items():
                elements.append(
                    Paragraph(
                        f"• {key.replace('_', ' ').title()}: €{value:,.0f}",
                        self.styles["BodyText"],
                    )
                )
            elements.append(Spacer(1, 0.1 * inch))

        # Timeline
        timeline = data.get("timeline", {})
        if timeline:
            elements.append(Paragraph("<b>Timeline:</b>", self.styles["SubSection"]))
            for phase, date in timeline.items():
                elements.append(
                    Paragraph(
                        f"• {phase.replace('_', ' ').title()}: {date}",
                        self.styles["BodyText"],
                    )
                )
            elements.append(Spacer(1, 0.1 * inch))

        # Tactics
        tactics = data.get("tactics", [])
        if tactics:
            elements.append(Paragraph("<b>Tactics:</b>", self.styles["SubSection"]))
            for tactic in tactics:
                elements.append(Paragraph(f"• {tactic}", self.styles["BodyText"]))

        return elements
