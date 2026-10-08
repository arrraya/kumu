"""PDF generation service for scouting reports."""
from io import BytesIO
from typing import Dict, Any
from reportlab.graphics.shapes import Drawing, Line, Rect, String
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

    # Same palette as the interface. A report that is printed and taken into a
    # meeting is the product's most important artefact, so it should not look
    # like a different product from the screen it came from.
    INK = colors.HexColor("#0F2E22")
    INK_SOFT = colors.HexColor("#3D5A4C")
    INK_FAINT = colors.HexColor("#7C9387")
    FIELD = colors.HexColor("#1A7A4C")
    FIELD_WASH = colors.HexColor("#E8F2EC")
    RULE = colors.HexColor("#DCE4DF")
    PAPER_SUNK = colors.HexColor("#F3F6F4")
    FLAG = colors.HexColor("#9A5B0B")
    FLAG_WASH = colors.HexColor("#FDF6EC")

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
                textColor=self.INK_SOFT,
                spaceAfter=8,
                fontName="Helvetica-Bold",
            )
        )

        # A page opener, so each vertex of the analysis starts somewhere.
        self.styles.add(
            ParagraphStyle(
                name="PageTitle",
                parent=self.styles["Heading1"],
                fontSize=22,
                leading=26,
                textColor=self.INK,
                spaceAfter=4,
                fontName="Times-Roman",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="Standfirst",
                parent=self.styles["Normal"],
                fontSize=10.5,
                leading=15,
                textColor=self.INK_SOFT,
                spaceAfter=16,
                fontName="Helvetica",
            )
        )

        # What a number means and how it was produced. The reader of this
        # report has to defend its conclusions to someone else, and a figure
        # he cannot explain is a figure he cannot use.
        self.styles.add(
            ParagraphStyle(
                name="Explain",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=13,
                textColor=self.INK_SOFT,
                fontName="Helvetica",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="Caveat",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=13,
                textColor=self.FLAG,
                fontName="Helvetica",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="BigFigure",
                parent=self.styles["Normal"],
                fontSize=34,
                leading=36,
                textColor=self.INK,
                fontName="Times-Roman",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="FigureLabel",
                parent=self.styles["Normal"],
                fontSize=8.5,
                textColor=self.INK_FAINT,
                fontName="Helvetica",
                spaceBefore=2,
            )
        )

    # ---------------------------------------------------------------- pieces
    #
    # The report used to be three pages of prose and tables. A sporting
    # director reading it had the conclusions but not the reasoning, so every
    # figure had to be taken on trust — which is the opposite of what Kumü
    # claims to offer. These pieces exist so each number arrives with its
    # meaning, its method and its limits attached.

    def _explain(self, what: str, how: str, caveat: str = None) -> list:
        """A box that says what a figure means and how it was produced."""
        filas = [
            [Paragraph(f"<b>What this is.</b> {what}", self.styles["Explain"])],
            [Paragraph(f"<b>How it is produced.</b> {how}", self.styles["Explain"])],
        ]
        if caveat:
            filas.append([Paragraph(f"<b>Read with care.</b> {caveat}",
                                    self.styles["Caveat"])])
        t = Table(filas, colWidths=[6.3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.PAPER_SUNK),
            ("LINEBEFORE", (0, 0), (0, -1), 2, self.FIELD),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return [Spacer(1, 8), t, Spacer(1, 14)]

    def _figure_row(self, items: list) -> Table:
        """Two or three headline numbers across the page, each with a label."""
        celdas, anchos = [], []
        for valor, etiqueta in items:
            celdas.append([
                Paragraph(str(valor), self.styles["BigFigure"]),
                Paragraph(etiqueta, self.styles["FigureLabel"]),
            ])
            anchos.append(6.3 * inch / len(items))
        t = Table([[Table([[c[0]], [c[1]]]) for c in celdas]], colWidths=anchos)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        return t

    def _percentile_bars(self, pares: list) -> Drawing:
        """Percentiles as bars against the same baseline.

        A column of '73rd percentile' strings is accurate and unreadable; the
        point of a percentile is the comparison, so it should be seen at once.
        """
        pares = [(n, v) for n, v in pares if isinstance(v, (int, float))][:8]
        if not pares:
            return None

        fila = 17
        d = Drawing(440, len(pares) * fila + 18)
        ancho_barra = 250
        x0 = 150

        # Reference lines at the quartiles, so a bar means something.
        for marca in (25, 50, 75):
            x = x0 + ancho_barra * marca / 100
            d.add(Line(x, 10, x, len(pares) * fila + 10,
                       strokeColor=self.RULE, strokeWidth=0.5))
            d.add(String(x - 6, 2, f"p{marca}", fontSize=6,
                         fillColor=self.INK_FAINT))

        for i, (nombre, valor) in enumerate(reversed(pares)):
            y = 14 + i * fila
            d.add(String(0, y, nombre[:26], fontSize=8, fillColor=self.INK_SOFT))
            largo = max(2, ancho_barra * float(valor) / 100)
            d.add(Rect(x0, y - 2, largo, 9,
                       fillColor=self.FIELD if valor >= 50 else self.INK_FAINT,
                       strokeColor=None))
            d.add(String(x0 + largo + 5, y, f"{int(valor)}", fontSize=8,
                         fillColor=self.INK_SOFT))
        return d

    def _pitch(self, perfil: Dict[str, Any]) -> Drawing:
        """The player's zone map, drawn from the stored spatial profile."""
        if not perfil:
            return None
        zonas = perfil.get("touch_zones") or {}
        flujos = perfil.get("pass_flows") or {}
        if not zonas and not flujos:
            return None

        grid = perfil.get("grid") or {}
        cols, rows = grid.get("cols", 6), grid.get("rows", 4)
        W, H = 420.0, 280.0
        cw, ch = W / cols, H / rows
        d = Drawing(W, H + 6)

        d.add(Rect(0, 0, W, H, fillColor=colors.white,
                   strokeColor=self.RULE, strokeWidth=1))

        maximo = max(zonas.values()) if zonas else 1
        for z, n in zonas.items():
            z = int(z)
            x, y = (z % cols) * cw, H - (z // cols + 1) * ch
            intensidad = 0.08 + 0.55 * (n / maximo)
            d.add(Rect(x, y, cw, ch, strokeColor=None,
                       fillColor=colors.Color(0.102, 0.478, 0.298, alpha=intensidad)))

        for i in range(1, cols):
            d.add(Line(i * cw, 0, i * cw, H, strokeColor=self.RULE, strokeWidth=0.4))
        for i in range(1, rows):
            d.add(Line(0, i * ch, W, i * ch, strokeColor=self.RULE, strokeWidth=0.4))
        d.add(Line(W / 2, 0, W / 2, H, strokeColor=self.RULE.clone(), strokeWidth=0.8))

        # The strongest passing links, so the shape of his game is visible.
        fuertes = sorted(flujos.items(), key=lambda kv: -kv[1])[:10]
        if fuertes:
            tope = fuertes[0][1]
            for clave, n in fuertes:
                a, b = (int(x) for x in clave.split("-"))
                if a == b:
                    continue
                ax = (a % cols + 0.5) * cw
                ay = H - (a // cols + 0.5) * ch
                bx = (b % cols + 0.5) * cw
                by = H - (b // cols + 0.5) * ch
                d.add(Line(ax, ay, bx, by, strokeColor=self.FIELD,
                           strokeWidth=0.4 + 1.6 * n / tope))
        return d

    def _percentiles_from(self, report_data: Dict[str, Any]) -> list:
        """Pull whatever percentiles the report carries, in a stable order."""
        stats = report_data.get("statistical_overview") or {}
        salida = []
        for clave in ("percentile_rankings", "percentiles", "metric_percentiles"):
            bloque = stats.get(clave)
            if isinstance(bloque, dict):
                for nombre, valor in bloque.items():
                    v = valor.get("percentile") if isinstance(valor, dict) else valor
                    if isinstance(v, (int, float)):
                        salida.append((nombre.replace("_", " ").capitalize(), v))
                break
        comp = (report_data.get("comparison_analysis") or {}).get("league_comparison") or {}
        if not salida and isinstance(comp.get("league_percentile"), (int, float)):
            salida.append(("Overall", comp["league_percentile"]))
        return salida

    def _market_explanation(self, market: Dict[str, Any]) -> list:
        """Say which market each side of the valuation was measured on.

        A return computed across two markets is expected to look large — that
        gap is the opportunity being described — so the reader has to see that
        two scales were involved, and whether either was measured or assumed.
        """
        roi = market.get("roi_analysis") or {}
        base = roi.get("market_basis") or {}
        vende = (base.get("fee_market") or "unknown").replace("_", " ")
        compra = (base.get("value_market") or "unknown").replace("_", " ")
        proy = base.get("projected_index") or {}

        caveat = None
        if base.get("cross_market"):
            caveat = (
                f"This is a move between markets, so the return is large by "
                f"construction: the fee is priced in {vende} and the value he "
                f"produces in {compra}. "
            )
            if proy.get("adjusted") and proy.get("value") is not None:
                caveat += (
                    f"His index is projected from {proy.get('factor')}× the "
                    f"league-strength ratio to {proy['value']} at the buyer, "
                    f"because a rating earned against weaker opposition is worth "
                    f"less against stronger."
                )
        fuentes = [base.get("fee_anchor_source"), base.get("value_anchor_source")]
        if "curated" in fuentes:
            caveat = (caveat or "") + (
                " At least one market anchor is still declared curation rather "
                "than measurement, and will be replaced once enough observed "
                "values exist for that league."
            )

        return self._explain(
            "What the player costs, what he is worth to this club, and the "
            "return over the contract.",
            f"The fee is priced on the scale of the market he leaves ({vende}); "
            f"the value he generates on the scale of the market he joins "
            f"({compra}), counting only what he adds above a replacement-level "
            f"player a club could sign cheaply.",
            caveat,
        )

    def _generate_method(self, report_data: Dict[str, Any]) -> list:
        """Closing page: what was measured, what was estimated, what was decided.

        Kumü's claim is not that its numbers are better than anyone else's. It
        is that each one states where it came from, so a reader can weigh it
        rather than trust it. That claim is worth a page.
        """
        e = [Paragraph("Method and limits", self.styles["PageTitle"])]
        e.append(Paragraph(
            "Every figure in this report is one of three things. None of them "
            "is hidden.", self.styles["Standfirst"]))

        filas = [
            [Paragraph("<b>Measured</b>", self.styles["Explain"]),
             Paragraph(
                 "Computed from match events: per-90 rates, match ratings, the "
                 "performance index and every percentile. The index is normalised "
                 "within each position, so a centre-back and a striker are "
                 "comparable.", self.styles["Explain"])],
            [Paragraph("<b>Estimated</b>", self.styles["Explain"]),
             Paragraph(
                 "Derived by Kumü where the source carries nothing: market value "
                 "when the club supplies none, and any figure built on it, "
                 "including the return. Age is not in this data source and is "
                 "held constant; any age-dependent figure is an assumption.",
                 self.styles["Explain"])],
            [Paragraph("<b>Decided</b>", self.styles["Explain"]),
             Paragraph(
                 "Judgements declared in advance: club playing styles, the level "
                 "each club operates at, league strength, and what a point of "
                 "performance is worth in each market. These are replaced by "
                 "measurement as licensed data arrives.", self.styles["Explain"])],
        ]
        t = Table(filas, colWidths=[1.1 * inch, 5.2 * inch])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, self.RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        e.append(t)

        e.append(Spacer(1, 18))
        e.append(Paragraph("What this report cannot tell you",
                           self.styles["SubSection"]))
        for linea in (
            "Whether a high compatibility score predicts a successful signing. "
            "The engine has not been tested against completed transfers, and "
            "saying so is more useful than implying otherwise.",
            "How the player performs in roles the source does not record. Aerial "
            "duels and blocks are absent from this data, so roles built on them "
            "score low for everyone — a gap in the data, not in the player.",
            "What a club actually pays. No observed transfer fee enters any "
            "calculation here.",
        ):
            e.append(Paragraph(f"• {linea}", self.styles["Explain"]))
            e.append(Spacer(1, 5))

        meta = report_data.get("report_metadata") or {}
        e.append(Spacer(1, 20))
        e.append(Paragraph(
            f"Kumü · generated {str(meta.get('generated_date', ''))[:10]}",
            self.styles["FigureLabel"]))
        return e

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

        # One vertex of the analysis per page, each opening with what the
        # figures on it mean. Three dense pages left the reader with
        # conclusions and no way to check them.
        elements.extend(self._generate_title(report_data.get("report_metadata", {})))

        if "executive_summary" in report_data:
            elements.extend(self._generate_executive_summary(report_data["executive_summary"]))
            elements.extend(self._explain(
                "A single compatibility figure and where the player ranks against "
                "others in his position.",
                "Four components, weighted: how he performs in the role, whether "
                "the club needs that position and suits his style, how far the fee "
                "stretches the budget, and how much room he has to develop there.",
                "Compatibility is a judgement about fit, not a prediction of "
                "success. Kumü has not yet been validated against completed "
                "transfers.",
            ))

        if "statistical_overview" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_statistical_overview(
                report_data["statistical_overview"]))
            barras = self._percentile_bars(self._percentiles_from(report_data))
            if barras:
                elements.append(Spacer(1, 10))
                elements.append(barras)
            elements.extend(self._explain(
                "Where this player sits against others in the same position.",
                "Every metric is a per-90 rate computed from match events, then "
                "ranked against players in the same position in the reference "
                "population. The 50th percentile is the typical player for that "
                "role.",
            ))

        if "tactical_analysis" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_tactical_analysis(
                report_data["tactical_analysis"]))
            base = (report_data["tactical_analysis"] or {}).get("style_basis") or {}
            medido = base.get("measured_territory")
            elements.extend(self._explain(
                "Whether the club needs this position, and whether his game suits "
                "how they play.",
                "Need is read from the club's actual squad — how many players it "
                "has in the position and how good they are. Style compares his "
                "output to the club's declared possession and pressing profile.",
                (f"The club's style used in the score is declared curation. Measured "
                 f"from its squad's passing, territory reads {medido}; it is shown "
                 f"for reference and not used, because territory over one tournament "
                 f"reflects game state as much as intent.") if medido is not None else None,
            ))

        if "physical_profile" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_physical_profile(report_data["physical_profile"]))
            cancha = self._pitch(report_data.get("spatial_profile"))
            if cancha:
                elements.append(Paragraph("Where he plays", self.styles["SubSection"]))
                elements.append(cancha)
                elements.extend(self._explain(
                    "The zones he is involved in, and the passing links he repeats.",
                    "Shading is how often he touched the ball in each zone; lines "
                    "are his most frequent completed passes between zones. Failed "
                    "passes are excluded, because their destination is where the "
                    "ball was cut off rather than where it was aimed.",
                ))

        if "market_analysis" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_market_analysis(report_data["market_analysis"]))
            elements.extend(self._market_explanation(report_data["market_analysis"]))

        if "comparison_analysis" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_comparison_analysis(
                report_data["comparison_analysis"]))
            elements.extend(self._explain(
                "How he measures against the players the club already has, and "
                "against his positional peers.",
                "Squad comparison uses the destination club's real squad where one "
                "is on file. Where it is not, the comparison falls back to players "
                "around the positional median and says so.",
            ))

        if "risk_assessment" in report_data:
            elements.append(PageBreak())
            elements.extend(self._generate_risk_assessment(report_data["risk_assessment"]))

        if "negotiation_strategy" in report_data:
            elements.extend(self._generate_negotiation_strategy(
                report_data["negotiation_strategy"]))

        elements.append(PageBreak())
        elements.extend(self._generate_method(report_data))

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
        """Generate tactical analysis section.

        Previously read formation keys the generator never produced
        ("best_fit"/"compatibility_score" instead of "fit"/"score"), and left
        out style fit, role suitability and flexibility entirely, so this
        section printed little more than its heading.
        """
        elements = [Paragraph("Tactical Analysis", self.styles["SectionHeader"])]

        formation = data.get("formation_compatibility", {})
        if formation:
            elements.append(Paragraph("<b>Formation Compatibility:</b>", self.styles["SubSection"]))
            elements.append(
                Paragraph(
                    f"{formation.get('fit', 'Unknown')} — score {formation.get('score', 0)}%"
                    f" ({formation.get('note', '')})",
                    self.styles["BodyText"],
                )
            )
            elements.append(Spacer(1, 0.15 * inch))

        style = data.get("style_compatibility", {})
        if style:
            elements.append(Paragraph("<b>Style Compatibility:</b>", self.styles["SubSection"]))
            elements.append(
                Paragraph(
                    f"Player style: {style.get('player_style', 'Unknown')} — "
                    f"compatibility {style.get('compatibility_score', 0)}%",
                    self.styles["BodyText"],
                )
            )
            for note in style.get("notes", [])[:4]:
                elements.append(Paragraph(f"• {note}", self.styles["BodyText"]))
            elements.append(Spacer(1, 0.15 * inch))

        roles = data.get("role_suitability", {})
        role_scores = roles.get("role_scores", {})
        if role_scores:
            elements.append(Paragraph("<b>Role Suitability:</b>", self.styles["SubSection"]))
            elements.append(
                Paragraph(f"Best role: {roles.get('best_role', 'Unknown')}", self.styles["BodyText"])
            )
            for role, detail in role_scores.items():
                if isinstance(detail, dict):
                    elements.append(
                        Paragraph(f"• {role}: {detail.get('score', 0)}%", self.styles["BodyText"])
                    )
            elements.append(Spacer(1, 0.15 * inch))

        flexibility = data.get("tactical_flexibility", {})
        if flexibility:
            alternatives = ", ".join(flexibility.get("alternative_positions", [])) or "none listed"
            elements.append(
                Paragraph(
                    f"<b>Versatility:</b> {flexibility.get('tactical_flexibility', 'Unknown')}"
                    f" ({flexibility.get('versatility_score', 0)}%) — also covers: {alternatives}",
                    self.styles["BodyText"],
                )
            )
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_physical_profile(self, data: Dict[str, Any]) -> list:
        """Generate physical profile section.

        Asked for a "percentile" the generator never emits; it provides
        "score" and "rating", so every attribute printed 0th percentile.
        """
        elements = [Paragraph("Physical Profile", self.styles["SectionHeader"])]

        athletic_scores = data.get("athletic_scores", {})
        if athletic_scores:
            elements.append(Paragraph("<b>Athletic Attributes:</b>", self.styles["SubSection"]))
            for attr, value in athletic_scores.items():
                if isinstance(value, dict):
                    score = value.get("score")
                    rating = value.get("rating", "")
                    score_text = f"{score:.1f}" if isinstance(score, (int, float)) else "n/a"
                    elements.append(
                        Paragraph(
                            f"• {attr.replace('_', ' ').title()}: {score_text} ({rating})",
                            self.styles["BodyText"],
                        )
                    )
            elements.append(Spacer(1, 0.15 * inch))

        age_analysis = data.get("physical_age_analysis", {})
        if age_analysis:
            elements.append(
                Paragraph(
                    f"<b>Development stage:</b> {age_analysis.get('development_stage', 'Unknown')}"
                    f" — {age_analysis.get('peak_years_remaining', 0)} peak years remaining",
                    self.styles["BodyText"],
                )
            )

        injury = data.get("injury_risk_factors", {})
        if injury:
            elements.append(
                Paragraph(
                    f"<b>Injury risk:</b> {injury.get('risk_level', 'Unknown')}"
                    f" (score {injury.get('risk_score', 0)})",
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
        """Generate comparison analysis section.

        Only printed the upgrade verdict, discarding the real positional peers
        and league percentile the generator now computes from the database.
        """
        elements = [Paragraph("Comparison Analysis", self.styles["SectionHeader"])]

        squad = data.get("squad_comparison", {})
        if squad:
            elements.append(
                Paragraph(
                    f"<b>Versus peers:</b> {squad.get('performance_improvement', 'n/a')}"
                    f" — {squad.get('immediate_impact', '')}",
                    self.styles["BodyText"],
                )
            )
            basis = squad.get("basis")
            if basis:
                elements.append(Paragraph(f"<i>{basis}</i>", self.styles["BodyText"]))
            for peer in squad.get("current_options", [])[:5]:
                if isinstance(peer, dict):
                    elements.append(
                        Paragraph(
                            f"• {peer.get('name', 'Unknown')} ({peer.get('team', '')}):"
                            f" index {peer.get('performance_index', 'n/a')}",
                            self.styles["BodyText"],
                        )
                    )
            elements.append(Spacer(1, 0.15 * inch))

        league = data.get("league_comparison", {})
        if league:
            percentile = league.get("league_percentile")
            percentile_text = f"{percentile}th percentile" if percentile is not None else "n/a"
            elements.append(
                Paragraph(
                    f"<b>League standing:</b> {percentile_text} — "
                    f"{league.get('vs_top_performers', '')}. {league.get('statistical_rank', '')}",
                    self.styles["BodyText"],
                )
            )
            elements.append(Spacer(1, 0.15 * inch))

        upgrade = data.get("upgrade_assessment", "")
        if upgrade:
            elements.append(Paragraph(f"<b>Assessment:</b> {upgrade}", self.styles["BodyText"]))
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
                label = key.replace('_', ' ').title()
                if isinstance(value, dict):
                    # Nested structure (e.g. payment_structure): render sub-items
                    parts = []
                    for sub_key, sub_value in value.items():
                        sub_label = sub_key.replace('_', ' ').title()
                        if isinstance(sub_value, (int, float)):
                            parts.append(f"{sub_label}: {sub_value}")
                        else:
                            parts.append(f"{sub_label}: {sub_value}")
                    display = ", ".join(parts)
                elif isinstance(value, (int, float)):
                    display = f"€{value:,.0f}"
                else:
                    display = str(value)
                elements.append(
                    Paragraph(
                        f"• {label}: {display}",
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
