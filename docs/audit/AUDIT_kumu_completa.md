# Auditoría de correctitud y robustez — Núcleo algorítmico de Kumu (consolidado)

**Fecha:** 2026-06-18
**Alcance:** Correctitud algorítmica + robustez con datos reales + portabilidad multi-fuente
**Archivos auditados:**
- `backend/app/api/v1/endpoints/matches.py`
- `backend/app/services/player_team_matcher.py`
- `backend/app/services/scouting_report_generator.py`
**Referencia metodológica externa:** notebook de analítica (StatsBomb + mplsoccer + kloppy + XGBoost).

> Nota de método: este documento contrasta lo que el código de Kumu **efectivamente consume**
> (extraído con `grep` de los `.get(...)` reales) contra lo que el notebook de referencia
> **efectivamente calcula**. No se asume nada sobre prompts o decisiones de desarrollo previas
> que no puedan verificarse contra el código presente.

---

## 0. Resumen ejecutivo

Kumu tiene ~7.000 líneas propias. El núcleo algorítmico vive en `backend/app/services/`.
Dos archivos, dos diagnósticos opuestos:

- **`player_team_matcher.py`:** el algoritmo NO se ejecuta. El endpoint de matching usa
  `random.uniform`. La lógica existe y está importada, pero está cortocircuitada.
- **`scouting_report_generator.py`:** el algoritmo SÍ se ejecuta, sin aleatoriedad, con lógica
  mayormente genuina. Pero su valor analítico está neutralizado por tres capas: benchmarks
  incompletos (2 posiciones × 1 liga), funciones de comparación mock, y placeholders puntuales.

**Patrón transversal (el riesgo central):** en todo Kumu, la *ausencia de datos se transforma
silenciosamente en un resultado de apariencia válida* — percentil 50, "Fair value", "Very
Consistent", métricas en 0. Nada falla; todo devuelve algo plausible pero vacío. Con datos reales
esto es peligroso porque **no se ve como error**: se ven reportes que parecen funcionar pero cuyos
números no significan lo que dicen.

**Para el objetivo de portabilidad multi-fuente (StatsBomb, Scout AI, etc.):** Kumu es
*consumidor* de métricas, no *productor*. El notebook de referencia muestra cómo se calculan las
métricas de verdad (modelo XGBoost de dificultad de pase, detección de runs sobre tracking, etc.),
pero ese cálculo vive **aguas arriba** de Kumu. El riesgo no es que Kumu calcule mal — es el
**contrato de nombres y unidades en la frontera**, que hoy no tiene capa de normalización.

---

## A. CRÍTICO — El algoritmo de matching no se ejecuta

**Ubicación:** `matches.py`, `calculate_matches`.

```python
matcher = PlayerTeamMatcher()      # instanciado, nunca usado para calcular
...
import random
base_score = 75 + random.uniform(-10, 20)     # score real = aleatorio 65–95
score = MatchScore(
    overall=base_score,
    tactical=base_score * 0.9,
    performance=base_score * 0.95,
    financial=base_score * 0.85,
    growth=base_score * 0.88,
)
```

- Los 4 sub-scores son el mismo número escalado → covarían perfectamente.
- `random` se reevalúa por request → los scores cambian al recargar.
- Explica los decimales largos sin redondeo vistos en la UI.
- `matcher.calculate_match_score()` nunca se invoca en este path.
- Efecto colateral peligroso: el endpoint crea equipos default con `db.commit()` si la tabla
  está vacía (un endpoint de lectura que escribe).

**Consecuencia para datos reales:** conectar la API real NO activa el matching. El `random` está
hardcodeado y no depende de la presencia de datos.

---

## B. Hallazgos en `player_team_matcher.py` (aplican al reactivar el algoritmo)

- **B1 (ALTO):** `calculate_tactical_fit` → `style_score = 0.7` hardcodeado. tactical_fit solo
  puede valer 0.88 o 0.58. El 40% del "fit táctico" es constante.
- **B2 (ALTO):** sin granularidad en tactical_fit (binario en position_match).
- **B3 (ALTO con datos reales):** `_update_metrics` usa `g.get(campo, 0)`. Nombres divergentes
  de la fuente → métricas en 0 silenciosas.
- **B4 (MEDIO):** `xG_per_shot` → NaN si no hay tiros en la ventana (`np.mean([])`).
- **B5 (BAJO-MEDIO):** `confidence = 1 - volatility` puede ser negativa (CV > 1).
- **B6 (MEDIO):** discontinuidad en `calculate_financial_fit` en el límite del presupuesto;
  `market_value <= 0 → 0.8` premia el dato faltante.
- **B7 (BAJO-MEDIO):** discontinuidad en `age_score` a los 30.
- **B8 (MEDIO):** inconsistencia de unidades en `NegotiationReportGenerator` (millones vs euros);
  origen del `€25000000.0M`.
- **B9 (BAJO):** `key_talking_points` son 3 frases fijas presentadas como análisis.
- **B10 (CONCEPTUAL):** varianza real del score baja → la precisión decimal es ilusoria.

---

## C. Hallazgos en `scouting_report_generator.py`

### Cimiento
- **Benchmarks 2×1:** `_load_benchmarks` solo cubre CAM y CB en Premier League.
  `calculate_percentile` devuelve **50 por defecto** para todo lo demás. Techo estructural:
  toda métrica fuera de ese set sale como "promedio". (CRÍTICO para datos reales)
- La lógica de `calculate_percentile` y `categorize_performance` es **correcta** cuando hay
  benchmark. El problema es cobertura de datos, no lógica.

### Hallazgos
- **C1 (MEDIO):** umbrales de recomendación dependen de `match_score` (que viene del random A).
- **C2 (BAJO/conceptual):** promediar percentiles para "overall_percentile" es metodológicamente
  incorrecto (los percentiles no son aditivos).
- **C3 (BAJO):** `_compare_to_average` tiene 4 ramas que colapsan en 2 (umbrales muertos).
- **C4 (ALTO con datos reales):** `_calculate_consistency` con `rating` ausente → std=0 →
  "Very Consistent / 90" falso. Falso positivo.
- **C5 (MEDIO con datos reales):** `_analyze_form_trajectory` con `rating` ausente → "Stable" inventado.
- **C6 (ESTRUCTURAL):** fortalezas/debilidades salen vacías mientras los percentiles sean 50.
- **C7 (ALTO con datos reales):** `_assess_style_fit` accede a `metrics[...][...]` sin `.get()`
  → KeyError (rompió antes en producción).
- **C8 (MEDIO):** `_assess_style_fit` da 0 si `playing_style` del equipo está vacío (default actual).
- **C9 (MEDIO):** `_score_wide_playmaker_attributes` placeholder fijo (70) → gana el `max` →
  recomendación de rol falsa para CAM.
- **C10 (ESTRUCTURAL):** roles/estilo solo cubren CAM y CB; resto → "Unknown".
- **C11 (DEMO):** con métricas placeholder, todos los jugadores → estilo "Balanced".
- **C12 (MEDIO):** `_score_sweeper_attributes` placeholder fijo (75) → todo CB sale "Sweeper".
- **C13 (BAJO):** `_assess_flexibility` ignora métricas pese a su docstring; versatility depende
  solo de la posición (tabla lookup disfrazada de evaluación).
- **C14 (MEDIO con datos reales):** scores físicos normalizan contra constantes únicas, sin ajuste
  por posición → sesgo (CB/GK siempre "bajos" en endurance/intensity).
- **C15 (MEDIO con datos reales):** scores físicos sensibles a unidades (m/s vs km/h), sin validación.
- **C16 (BAJO):** `physical_comparison` etiqueta el número como "percentil for position" cuando no lo es.
- **C17 (ALTO):** `_find_comparable_transfers` es mock; fees = valor del jugador ×0.9 y ×1.1.
- **C18 (ALTO):** `_assess_value` → value_ratio ≈ 1.0 siempre → **siempre "Fair value"**.
  Cálculo circular (divide el valor por sí mismo).
- **C19 (MEDIO):** `_project_market_value` aplica age_factor de la edad futura elevado a `year`
  → trata el régimen final como retroactivo → distorsiona proyecciones largas.
- **C20 (BAJO):** constantes mágicas sin justificar (ancla 70 en performance_factor).
- **C21 (MEDIO):** `_estimate_commercial_value` usa `marketability_score` inexistente → default 50
  → valor comercial depende solo de edad.
- **C22 (BAJO):** constantes mágicas en valoración deportiva (ancla 50M) y salario (0.2%).
- **C23 (BAJO):** `buyout_clause = None` para veteranos puede propagar None a UI/PDF.
- **C24 (TRANSVERSAL):** todo el bloque económico es aritméticamente correcto pero descansa sobre
  la unidad de `market_value`. El riesgo de unidades es sistémico.
- **C25 (ALTO):** `_compare_with_squad` mock (jugadores 72/68); coincide con default 70 → todo
  demo es "squad depth, no upgrade".
- **C26 (ALTO):** `_compare_with_league_peers` pide percentil de métrica inexistente
  ("overall_performance") → siempre 50 → "Mid-tier" para todos; `statistical_rank` siempre "6th".
- **C27 (MEDIO con datos reales):** `_historical_performance_comparison` accede a `h["rating"]`
  sin `.get()` → KeyError si falta rating.
- **C28 (BAJO):** `_assess_upgrade_potential` parsea string→float (`.strip("%+")`) en vez de usar
  el float original (anti-patrón frágil).
- **C29 (MEDIO):** `_assess_adaptation_risk` usa `style_difference = 20` constante → +20 de riesgo
  de adaptación fijo para todo fichaje.
- **C30 (MEDIO con datos reales):** `current_league`/`nationality` ausentes → falso +25/+15 de riesgo.
- **C31 (COSMÉTICO):** `_create_risk_mitigation_plan` usa `set()` → orden no determinista.
- **C32 (MEDIO, conecta con C18):** `_calculate_opening_offer` ajusta por valoración de mercado,
  pero como `_assess_value` siempre da "Fair value", la rama Overvalued/Undervalued es código muerto.
- **C33 (BAJO):** pocas funciones acceden a campos core sin `.get()` (inconsistente).

### Lo que está bien (no tocar)
`_assess_injury_risk`, `_calculate_risk_factor`, `_assess_age_risk`, `_recommend_contract_structure`,
`_calculate_total_package`, `_assess_negotiation_position`, `_identify_leverage_factors`,
`_create_negotiation_timeline`, `_recommend_payment_structure`, `generate_risk_assessment`
(promedio legítimo de scores en misma escala). Arquitectura sólida; manejo conservador de ausencia.

---

## D. Mapeo métrica-por-métrica: notebook de referencia ↔ campos que Kumu consume

> Campos de Kumu extraídos verbatim de los `.get(...)` del código. Ningún nombre coincide
> directamente con la salida del notebook → confirma necesidad de capa traductora.

### D1. Métricas analíticas (el notebook las produce / deberían venir de la fuente de eventos)

| Concepto | Cómo se calcula de verdad (notebook / método) | Campo que Kumu espera | Unidad / escala esperada por Kumu | Riesgo |
|---|---|---|---|---|
| Dificultad de pase | Modelo XGBoost sobre (x1,y1,x2,y2), salida prob. 0–1, validado ROC/AUC; col. `difficulty` | `pass_difficulty` (default 0.5) | 0–1 | Nombre divergente (`difficulty` vs `pass_difficulty`) |
| Runs de alta intensidad | Tracking 25fps, `speed_threshold=6 m/s` sostenido ≥10 frames, conteo | `sprints` / `high_intensity_runs` | conteo entero | Nombre divergente; depende de tracking |
| Distancia recorrida | Suma de desplazamientos sobre tracking, escalada a euclidiano | `distance_km` / `distance_covered_per_90` | km por 90' | Unidad (km vs m); ventana (por 90) |
| Velocidad media | `np.linalg.norm(Δpos) * frame_rate` | `avg_speed` / `average_speed` | m/s (notebook) vs ¿? (Kumu /8.5) | **C15** — unidad sin validar |
| Pases progresivos | Filtrado de eventos por avance hacia portería | `progressive_passes` / `_per_90` | conteo por 90' | Nombre; agregación |
| Completitud de pase | `1 - pass_outcome` agregado (StatsBomb) | `pass_completion` / `completion_rate` | proporción 0–1 | Nombre; ya agregado |
| Tiros / xG | Eventos de tiro + `shot_statsbomb_xg` | `shots`, `xG` | conteo; xG 0–1 | `xG` puede faltar → **B4** NaN |
| Goles / asistencias | Conteo de eventos | `goals`, `assists` | conteo | OK si la fuente los da |
| Acciones defensivas | Conteo de eventos (tackle/intercept) | `tackles`, `interceptions`, `aerial_won_pct` | conteo; aerial 0–1 | Nombre; fuente |

### D2. Campos que Kumu consume pero el notebook NO produce
`goals`, `assists`, `tackles`, `interceptions`, `aerial_won_pct`, `rating`, `key_passes`.
→ Vienen de la fuente de eventos (StatsBomb los tiene), no del tracking del notebook.
`rating` es crítico: lo usan consistency y form trajectory; si la fuente no lo da → **C4/C5/C27**.

### D3. Campos contextuales / de mercado (ni notebook ni eventos; usuario o fuente de mercado)
`wants_move`, `club_needs_sale`, `key_player`, `long_contract`, `multiple_suitors`,
`other_interested_clubs`, `marketability_score`, `contract_expires_months`,
`alternative_targets`, `priority_positions`, `playing_style`, `possession`,
`pressing_intensity`, `formation`, `positions`, `style`.
→ Mayormente bien manejados con `.get()` conservador. `marketability_score` es el único que se
consume sin existir nunca (**C21**).

---

## E. Contrato de datos esperado (especificación para cualquier fuente)

Para que una fuente (StatsBomb, Scout AI, u otra) alimente Kumu correctamente, debe entregar un
`player_data` con esta forma. La capa de normalización (sección F) es responsable de mapear el
formato nativo de cada fuente a este contrato.

```
player_data = {
  "id": str|int,
  "name": str,
  "age": int,
  "position": str,              # taxonomía controlada: GK, CB, RB, LB, CDM, CM, CAM, RW, LW, ST...
  "nationality": str,
  "current_league": str,        # debe matchear taxonomía de ligas de los benchmarks
  "market_value": float,        # EUROS absolutos (no millones) — fijar unidad única
  "performance_index": {"value": float(0-100), "trend": float, "volatility": float(0-1), "confidence": float(0-1)},
  "metrics": {
     "passing":   {"completion_rate":0-1, "progressive_passes_per_90":num, "key_passes_per_90":num, "pass_difficulty_score":0-1},
     "shooting":  {"shots_per_90":num, "xG_per_shot":0-1, "conversion_rate":0-1, "goals_per_90":num, "assists_per_90":num},
     "movement":  {"distance_covered_per_90":km, "high_intensity_runs":int, "average_speed":<unidad-fija>},
     "defensive": {"tackles_per_90":num, "interceptions_per_90":num, "aerial_duels_won":0-1, "blocks_per_90":num}
  },
  "performance_history": [ {"rating":0-10, "goals":int, "assists":int, ...}, ... ],   # ideal ≥20 entradas
  "injury_history": [ {"days_missed":int, "date":str, ...}, ... ],
  # contextuales opcionales (defaults conservadores): contract_expires_months, wants_move, ...
}
```

Reglas de contrato:
1. **Unidad única de dinero:** euros absolutos en todo el sistema (elimina B8/C24).
2. **Unidad fija de velocidad:** declarar m/s o km/h y normalizar en la frontera (cierra C15).
3. **`rating` obligatorio** en performance_history o consistency/form quedan inválidos (C4/C5).
4. **Taxonomía controlada** de posiciones y ligas, alineada con los benchmarks (sección C cimiento).
5. **Ausencia explícita:** un campo faltante debe marcarse como `None`/“no data”, NO como 0,
   para que el código pueda distinguir "cero real" de "sin dato" (raíz del patrón transversal).

---

## F. Diseño de la capa de normalización multi-fuente (clave de portabilidad)

Objetivo: liberar a Kumu de cualquier fuente específica. Kumu consume **solo** el contrato (E);
cada fuente tiene un adaptador que traduce su formato nativo al contrato.

```
Fuente nativa (StatsBomb / Scout AI / CSV / ...)
        │
        ▼
  [ Adapter por fuente ]   ← mapea nombres + convierte unidades + valida taxonomía
        │
        ▼
  Contrato canónico (sección E)
        │
        ▼
  [ Validador de contrato ]  ← rechaza/registra campos faltantes como None (no 0)
        │
        ▼
  PlayerTeamMatcher  /  ScoutingReportGenerator
```

Componentes:
1. **Interfaz `MetricsSource` (abstracta):** método `get_player(id) -> player_data` que devuelve
   el contrato canónico. Una implementación por fuente (`StatsBombSource`, `ScoutAISource`, ...).
2. **Tabla de mapeo declarativa por fuente:** `{campo_canónico: (campo_nativo, conversión)}`.
   Ej. StatsBomb: `pass_difficulty_score -> ("difficulty", identidad)`,
   `average_speed -> ("speed_ms", identidad)`; otra fuente podría requerir `*3.6` (m/s→km/h).
3. **Validador de contrato:** verifica presencia, tipos, rangos y unidades; lo ausente queda
   `None` (no 0). Emite un reporte de cobertura ("este jugador tiene 8/12 métricas") que la UI
   puede mostrar en vez de fingir un análisis completo.
4. **Política de degradación honesta:** cuando falta una métrica, el reporte lo dice
   ("dato no disponible"), en lugar de devolver percentil 50 / "Fair value" silencioso.
   Esto convierte el patrón transversal de riesgo en transparencia.

Beneficio: agregar Scout AI (u otra) = escribir un adaptador + su tabla de mapeo. Cero cambios
en matcher/generador. La portabilidad deja de depender de `.get(campo, default)` disperso.

---

## G. Plan de reconexión y reparación (orden sugerido)

**Fase 1 — Reconectar el matcher (cierra A):**
1. Adaptador DB-model → objeto `Player`/`Team` del matcher.
2. Reescribir `calculate_matches` para llamar `matcher.calculate_match_score()` en vez de `random`.
3. Sacar la creación de equipos default fuera del endpoint de lectura.
4. Mantener fallback a demo SOLO cuando falten métricas, marcado explícitamente (no silencioso).

**Fase 2 — Reparar correctitud del matcher:** B1–B8 (priorizar B1/B2 placeholder táctico, B3
nombres, B8 unidades).

**Fase 3 — Destapar el generador:**
1. Poblar benchmarks (cargar de DB como indica el comentario) → elimina el techo del percentil 50.
2. Reemplazar los 3 mocks por queries reales: `_find_comparable_transfers`, `_compare_with_squad`,
   `_compare_with_league_peers` (cierra C17/C18/C25/C26).
3. Completar placeholders: scorers wide_playmaker/sweeper (C9/C12), `style_difference` (C29),
   `marketability_score` (C21).
4. Endurecer accesos: `.get()` en `_assess_style_fit` y `_historical_...` (C7/C27).

**Fase 4 — Capa de normalización (sección F):** habilita multi-fuente y degradación honesta.
Idealmente antes de conectar la primera fuente real, para no propagar el patrón silencioso.

**Fase 5 — Transparencia de datos:** que la UI muestre cobertura de métricas y marque secciones
con datos insuficientes, en vez de rellenar con neutros.

---

## H. Nota sobre mejoras analíticas (fuera de Kumu, en el pipeline)
El notebook ya incluye mejoras razonables (p. ej. el `tti` modificado que penaliza velocidad
inicial mal orientada vs. la aproximación de Shaw). Estas mejoras pertenecen al pipeline que
**produce** las métricas, no a Kumu. Kumu solo debe recibirlas vía el contrato (E). Hay margen de
perfeccionamiento metodológico (otras fuentes, modelos de xG propios, pitch control), pero es
trabajo separable y no bloquea la reparación de Kumu.
