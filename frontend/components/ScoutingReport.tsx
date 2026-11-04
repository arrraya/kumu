'use client'

import React, { useState, useEffect } from 'react';
import { 
  FileText, TrendingUp, Shield, DollarSign, Target, AlertTriangle, 
  Users, Activity, Calendar, Briefcase, Check, AlertCircle, Download,
  ChevronRight, BarChart3, Eye
} from 'lucide-react';
import { 
  BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, 
  Radar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  ResponsiveContainer, Cell 
} from 'recharts';
import { Player, Match } from '@/types';
import { api } from '@/lib/api';
import PitchMap from '@/components/PitchMap'

interface ScoutingReportProps {
  player: Player | null;
  match: Match | null;
}

interface ScoutingReportData {
  report_metadata: {
    generated_date: string;
    player_name: string;
    player_id: string;
    team_name: string;
    team_id: string;
    report_id?: number;
    data_coverage?: {
      available_fields: number;
      total_fields: number;
      coverage_pct: number;
      missing_fields: string[];
    };
  };
  executive_summary: {
    recommendation: string;
    action: string;
    match_score: number;
    overall_percentile: number;
    key_findings: any[];
    executive_statement: string;
  };
  statistical_overview: {
    position_specific_analysis: any;
    statistical_strengths: string[];
    statistical_weaknesses: string[];
    consistency_rating: { rating: string; score: number };
    form_trajectory: { trend: string; direction: string; slope: number };
  };
  tactical_analysis: {
    formation_compatibility: { fit: string; score: number; note: string };
    style_compatibility: {
      compatibility_score: number;
      player_style: string;
      notes: string[];
    };
    role_suitability: {
      best_role: string;
      recommendation: string;
    };
    tactical_flexibility: {
      primary_position: string;
      alternative_positions: string[];
      versatility_score: number;
      tactical_flexibility: string;
    };
  };
  physical_profile: {
    // Partial, and empty when the source carries no tracking data. The type
    // says so, so a missing block is a case the compiler makes you handle
    // rather than a zero that slips through looking like a measurement.
    athletic_scores: Partial<Record<'speed' | 'endurance' | 'intensity',
      { score: number; rating: string }>>;
    athletic_scores_basis?: string | null;
    physical_age_analysis: {
      current_age: number | null;
      development_stage: string | null;
      peak_years_remaining: number | null;
      basis?: string | null;
    };
    injury_risk_factors: {
      risk_level: string | null;
      risk_score: number | null;
      risk_factors: string[];
      mitigation_suggestions: string[];
      basis?: string | null;
    };
  };
  market_analysis: {
    current_market_value: number | null;
    value_assessment: {
      assessment: string;
      recommendation: string;
      value_ratio: number;
      vs_comparables: string | null;
      basis?: string | null;
    };
    value_projections: {
      [key: string]: { value: number; age: number; change_pct: number };
    };
    roi_analysis: {
      roi_percentage: number;
      breakeven_period: string;
      risk_adjusted_roi: number;
    };
  };
  comparison_analysis: {
    squad_comparison: {
      performance_improvement: string;
      immediate_impact: string;
      position_upgrade: boolean;
    };
    league_comparison: {
      league_percentile: number;
      vs_top_performers: string;
      statistical_rank: string;
    };
    upgrade_assessment: string;
  };
  risk_assessment: {
    overall_risk_level: string | null;
    risk_score: number | null;
    risk_basis?: string | null;
    risk_factors: {
      [key: string]: { score: number; level: string };
    };
    mitigation_plan: string[];
  };
  negotiation_strategy: {
    negotiation_position: {
      strength: string | null;
      score: number | null;
      factors: string[];
      basis?: string | null;
    };
    offer_strategy: {
      opening_offer: number;
      target_offer: number | null;
      maximum_offer: number | null;
      walk_away_price: number | null;
      basis?: string | null;
    };
    timeline: {
      initial_contact: string;
      first_offer: string;
      negotiation_window: string;
      urgency?: string | null;
      basis?: string | null;
    };
    tactics: string[];
  };
}

const ScoutingReport: React.FC<ScoutingReportProps> = ({ player, match }) => {
  const [report, setReport] = useState<ScoutingReportData | null>(null);
  const [activeSection, setActiveSection] = useState('executive');
  const [loading, setLoading] = useState(true);
  // Destination clubs, so a report can be run against any club rather than
  // only the ones that made the player's top-10 match cards.
  const [clubs, setClubs] = useState<any[]>([]);
  const [switchingTeam, setSwitchingTeam] = useState(false);

  useEffect(() => {
    // Load report from localStorage or generate new one
    const savedReport = localStorage.getItem('currentReport');
    if (savedReport) {
      setReport(JSON.parse(savedReport));
      setLoading(false);
    } else if (player && match) {
      setReport(null);
      setLoading(false);
    } else {
      setLoading(false);
    }
  }, [player, match]);

  useEffect(() => {
    const loadClubs = async () => {
      try {
        const teams = await api.teams.getAll({ limit: 100 });
        setClubs((teams || []).filter((t: any) => t.teamType !== 'national'));
      } catch (error) {
        console.error('Could not load clubs:', error);
      }
    };
    loadClubs();
  }, []);

  const regenerateForTeam = async (teamId: string) => {
    const playerId = report?.report_metadata?.player_id;
    if (!playerId || !teamId) return;
    try {
      setSwitchingTeam(true);
      const fresh = await api.reports.generate(String(playerId), String(teamId));
      localStorage.setItem('currentReport', JSON.stringify(fresh));
      setReport(fresh);
    } catch (error) {
      console.error('Could not regenerate report:', error);
      alert('Could not generate the report for that club.');
    } finally {
      setSwitchingTeam(false);
    }
  };

  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const handleDownloadPdf = async () => {
    const reportId = report?.report_metadata?.report_id;
    if (!reportId) {
      alert("PDF not available for this report yet. Please regenerate the report.");
      return;
    }
    try {
      setDownloadingPdf(true);
      await api.reports.downloadPdf(reportId, report?.report_metadata?.player_name);
    } catch (error) {
      console.error("Error downloading PDF:", error);
      alert("Failed to download PDF. Please try again.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  /**
   * There used to be a generateMockReport() here: ~150 lines that invented a
   * complete scouting report — athletic scores, injury risk, negotiation
   * figures — and rendered it exactly like a real one, with no label and no
   * visual difference. It ran whenever no report was in localStorage.
   *
   * A product whose argument is that it marks every figure's provenance
   * cannot have a path that fabricates the whole document. Absence is now
   * shown as absence.
   */

  // Tolerates absence: a client whose feed carries no valuations should see a
  // dash, not "€NaNM".
  const formatCurrency = (value: number | null | undefined) =>
    typeof value === 'number' ? `€${(value / 1000000).toFixed(1)}M` : '—';
  const formatPercentage = (value: number) => `${value.toFixed(1)}%`;

  const sections = [
    { id: 'executive', name: 'Executive Summary', icon: FileText },
    { id: 'statistical', name: 'Statistical Analysis', icon: TrendingUp },
    { id: 'tactical', name: 'Tactical Fit', icon: Target },
    { id: 'physical', name: 'Physical Profile', icon: Activity },
    { id: 'market', name: 'Market Analysis', icon: DollarSign },
    { id: 'comparison', name: 'Comparisons', icon: Users },
    { id: 'risk', name: 'Risk Assessment', icon: Shield },
    { id: 'negotiation', name: 'Negotiation Strategy', icon: Briefcase }
  ];

  /**
   * 1st, 2nd, 3rd, 92nd. The report printed "92th" on a figure set at display
   * size; English ordinals are irregular in the units digit except in the
   * teens, which is the whole rule.
   */
  const ordinal = (n: number): string => {
    const v = Math.abs(Math.round(n)) % 100
    const suffix = v >= 11 && v <= 13 ? 'th'
      : ['th', 'st', 'nd', 'rd'][Math.abs(Math.round(n)) % 10] ?? 'th'
    return `${Math.round(n)}${suffix}`
  }

  const RecommendationBadge = ({ recommendation }: { recommendation: string }) => {
    const getColor = () => {
      if (recommendation.includes('STRONGLY')) return 'bg-ink text-paper border-ink';
      if (recommendation.includes('RECOMMENDED')) return 'bg-paper-sunk text-ink border-ink';
      if (recommendation.includes('CONDITIONALLY')) return 'bg-paper-card text-flag border-flag';
      return 'bg-loss-wash text-loss border-loss';
    };

    return (
      <span className={`px-4 py-2  text-sm font-semibold border ${getColor()}`}>
        {recommendation}
      </span>
    );
  };

  const PercentileBar = ({ percentile, label }: { percentile: number; label: string }) => (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-ink-soft">{label}</span>
        <span className="font-medium">{ordinal(percentile)} percentile</span>
      </div>
      <div className="w-full bg-paper-sunk h-2">
        <div
          className="h-2 bg-clay transition-all duration-500"
          style={{ width: `${percentile}%` }}
        />
      </div>
    </div>
  );

  const RiskMeter = ({
    score,
    level,
    basis,
  }: {
    score: number | null;
    level: string | null;
    // Passed in rather than read off `report` from the enclosing scope:
    // TypeScript narrows `report` where it is rendered, not inside a
    // nested component, so the closure saw it as possibly null and the
    // production build refused to compile. A prop is also the honest
    // shape - the meter already takes everything else it draws.
    basis?: string | null;
  }) => {
    // An unassessed overall risk has no needle to point and no percentage to
    // print. It used to arrive as a number because every sub-risk reported one
    // whether or not it had anything to measure.
    if (score === null || level === null) {
      return (
        <div className="border border-dashed border-rule-strong p-6 max-w-read">
          <h4 className="label mb-2">Overall risk — not assessed</h4>
          <p className="text-sm text-ink-soft">
            {basis ?? 'No risk could be assessed from this source.'}
          </p>
        </div>
      );
    }
    const rotation = (score / 100) * 180 - 90;
    
    return (
      <div className="w-32 mx-auto">
        <svg viewBox="0 0 100 60" className="w-full h-full">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="#D8D7CC"
            strokeWidth="8"
          />
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="url(#riskGradient)"
            strokeWidth="8"
            strokeDasharray={`${score * 1.26} 126`}
          />
          <defs>
            <linearGradient id="riskGradient">
              <stop offset="0%" stopColor="#C25A3A" />
              <stop offset="50%" stopColor="#B07A20" />
              <stop offset="100%" stopColor="#A3372B" />
            </linearGradient>
          </defs>
          <line
            x1="50"
            y1="50"
            x2="50"
            y2="20"
            stroke="#1B1F1A"
            strokeWidth="2"
            transform={`rotate(${rotation} 50 50)`}
          />
          <circle cx="50" cy="50" r="3" fill="#1B1F1A" />
        </svg>
        <div className="text-center mt-2">
          <div className="text-lg font-semibold">{level}</div>
          <div className="text-sm text-ink-soft">{score.toFixed(1)}% risk</div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-field-wash flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-ink mx-auto"></div>
          <p className="mt-4 text-ink-soft">Loading scouting report...</p>
        </div>
      </div>
    );
  }

  if (!report || !player || !match) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-paper-card p-12 rounded-sm shadow-md text-center">
          <FileText className="w-16 h-16 text-ink-faint mx-auto mb-4" />
          <h3 className="text-lg font-medium text-ink-soft">No report available</h3>
          <p className="text-sm text-ink-faint mt-2">
            Select a player and team match to generate a scouting report
          </p>
        </div>
      </div>
    );
  }

  const renderExecutiveSummary = () => (
    <div className="space-y-6">
      <div className="bg-paper-card border border-rule rounded-sm p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold">Assessment</h3>
        </div>
        
        <div className="border-t pt-4">
          <h4 className="font-medium text-ink-soft mb-3">Key Findings</h4>
          <ul className="space-y-2">
            {report.executive_summary.key_findings.map((finding: any, i: number) => {
              // Findings arrive as {text, origin}; older reports stored plain
              // strings, and those still render.
              const text = typeof finding === 'string' ? finding : finding?.text
              const origin = typeof finding === 'string' ? null : finding?.origin
              const mark =
                origin === 'estimated' ? 'is-estimated'
                : origin === 'decided' ? 'is-curated'
                : ''
              return (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-2 w-1 h-1  bg-ink-faint shrink-0" />
                  <span className={`text-ink-soft ${mark}`}>{text}</span>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="mt-6 p-4 bg-paper-sunk rounded-sm">
          <p className="text-sm text-ink-soft italic">"{report.executive_summary.executive_statement}"</p>
        </div>

        {/* A closing line, not a boxed alert. The verdict already leads the
            report; a tinted panel with a warning icon made the same judgement
            read as a second, separate finding. This says what to do next and
            gets out of the way. */}
        <p className="mt-6 pt-4 border-t border-rule text-ink-soft">
          <span className="text-ink-faint">Next step — </span>
          {report.executive_summary.action}
        </p>
      </div>
    </div>
  );

  const renderStatisticalAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-paper-card border border-rule rounded-sm p-6">
        <h3 className="text-xl font-semibold mb-6">Performance Metrics</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div className="bg-field-wash p-4 rounded-sm">
            <h4 className="font-medium text-ink mb-3">Statistical Strengths</h4>
            <ul className="space-y-2">
              {report.statistical_overview.statistical_strengths.map((strength, i) => (
                <li key={i} className="text-sm text-field-dark flex items-start gap-2">
                  <TrendingUp className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{strength}</span>
                </li>
              ))}
            </ul>
          </div>
          
          <div className="bg-flag-wash p-4 rounded-sm">
            <h4 className="font-medium text-flag mb-3">Areas for Development</h4>
            <ul className="space-y-2">
              {report.statistical_overview.statistical_weaknesses.map((weakness, i) => (
                <li key={i} className="text-sm text-flag flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{weakness}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-paper-sunk p-4 rounded-sm">
            <div className="text-sm text-ink-soft">Consistency</div>
            <div className="text-lg font-semibold">{report.statistical_overview.consistency_rating.rating}</div>
            <div className="text-sm text-ink-faint">Score: {report.statistical_overview.consistency_rating.score}/100</div>
          </div>
          <div className="bg-paper-sunk p-4 rounded-sm">
            <div className="text-sm text-ink-soft">Form Trajectory</div>
            <div className="text-lg font-semibold">{report.statistical_overview.form_trajectory.trend}</div>
            <div className="text-sm text-ink-faint">Direction: {report.statistical_overview.form_trajectory.direction}</div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTacticalAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-paper-card border border-rule rounded-sm p-6">
        <h3 className="text-xl font-semibold mb-6">Tactical Fit Analysis</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-field-wash p-6 rounded-sm">
            <h4 className="font-medium text-ink mb-4">Formation Compatibility</h4>
            <div className="text-center">
              <div className="text-4xl font-bold text-field">{report.tactical_analysis.formation_compatibility.score}%</div>
              <div className="text-lg text-field-dark mt-2">{report.tactical_analysis.formation_compatibility.fit}</div>
              <p className="text-sm text-field mt-2">{report.tactical_analysis.formation_compatibility.note}</p>
            </div>
          </div>
          
          <div className="bg-field-wash p-6 rounded-sm">
            <h4 className="font-medium text-ink mb-4">Style Compatibility</h4>
            <div className="text-center">
              <div className="text-4xl font-bold text-field">{report.tactical_analysis.style_compatibility.compatibility_score}%</div>
              <div className="text-lg text-field-dark mt-2">{report.tactical_analysis.style_compatibility.player_style}</div>
            </div>
          </div>
        </div>

        <div className="mt-6">
          <h4 className="font-medium text-ink-soft mb-3">Tactical Notes</h4>
          <ul className="space-y-2">
            {report.tactical_analysis.style_compatibility.notes.map((note, i) => (
              <li key={i} className="flex items-start gap-2 text-ink-soft">
                {/* A tick asserts something was checked and holds. A note that
                    says a thing could NOT be assessed gets a dash instead:
                    the icon is a claim too. */}
                {note.toLowerCase().includes('not assessed') ? (
                  <span aria-hidden="true" className="w-5 mt-0.5 flex-shrink-0 text-ink-faint text-center">—</span>
                ) : (
                  <Check className="w-5 h-5 text-ink mt-0.5 flex-shrink-0" aria-hidden="true" />
                )}
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 p-4 bg-paper-sunk rounded-sm">
          <h4 className="font-medium text-ink mb-2">Best Tactical Role</h4>
          <p className="text-ink-soft">{report.tactical_analysis.role_suitability.recommendation}</p>
          
          <div className="mt-4">
            <h5 className="text-sm font-medium text-ink-soft mb-2">Position Flexibility</h5>
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1 bg-ink text-paper  text-sm">
                {report.tactical_analysis.tactical_flexibility.primary_position}
              </span>
              {report.tactical_analysis.tactical_flexibility.alternative_positions.map((pos, i) => (
                <span key={i} className="px-3 py-1 bg-paper-sunk text-ink  text-sm">
                  {pos}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderPhysicalProfile = () => {
    const athleticData = Object.entries(report.physical_profile.athletic_scores).map(([attr, data]) => ({
      attribute: attr.charAt(0).toUpperCase() + attr.slice(1),
      score: data.score,
      rating: data.rating
    }));

    return (
      <div className="space-y-6">
        {/* Placed first: a scout opening this tab wants to know where the
            player operates before reading reference scores. The athletic
            numbers below are compared against role references rather than
            measured, because tracking data is not in the feed — the map is
            the part of this tab that comes from what actually happened. */}
        <PitchMap
          profile={(player as any)?.spatial_profile ?? (player as any)?.spatialProfile}
          name={player?.name}
        />

        <div className="bg-paper-card border border-rule rounded-sm p-6">
          <h3 className="text-xl font-semibold mb-6">Physical & Athletic Profile</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="label mb-4">Athletic Attributes</h4>
              {/* A GAP, NOT A ZERO. This chart used to draw three bars from
                  metrics the event feed does not carry, so a tracking-free
                  source produced a full athletic profile out of nothing. The
                  chart and its scoring are untouched underneath: the day a
                  provider sends distance, sprints and speed, the bars appear
                  with no change here. */}
              {athleticData.length === 0 ? (
                <div className="border border-dashed border-rule-strong p-6">
                  <p className="text-sm text-ink-soft max-w-read">
                    {report.physical_profile.athletic_scores_basis ??
                      'No athletic profile: this source carries no tracking data.'}
                  </p>
                  <p className="label mt-3">Needs: distance · sprints · speed</p>
                </div>
              ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={athleticData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="attribute" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#3A5A7A" radius={[8, 8, 0, 0]}>
                    {athleticData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={
                        entry.score >= 80 ? '#C25A3A' :
                        entry.score >= 60 ? '#3A5A7A' :
                        '#B07A20'
                      } />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              )}
            </div>

            <div>
              <h4 className="label mb-4">Age & Development</h4>
              {/* The report states on its own masthead that age is not carried
                  by this source. It then printed "26 · Physical prime · 2 peak
                  years remaining" from the constant that stands in for a
                  missing age — an age-dependent judgement on an age the same
                  page had just declared unknown. */}
              {report.physical_profile.physical_age_analysis.current_age === null ? (
                <div className="border border-dashed border-rule-strong p-6">
                  <p className="text-sm text-ink-soft max-w-read">
                    {report.physical_profile.physical_age_analysis.basis ??
                      'Age is not carried by this source, so no career-stage judgement is made.'}
                  </p>
                  <p className="label mt-3">Needs: date of birth</p>
                </div>
              ) : (
                <div className="bg-paper-sunk p-6">
                  <div className="text-center">
                    <div className="figure">{report.physical_profile.physical_age_analysis.current_age}</div>
                    <div className="label mt-2">years old</div>
                  </div>
                  <div className="mt-4 text-center">
                    <p className="font-medium">{report.physical_profile.physical_age_analysis.development_stage}</p>
                    {report.physical_profile.physical_age_analysis.peak_years_remaining !== null && (
                      <p className="text-sm text-ink-soft mt-2">
                        {report.physical_profile.physical_age_analysis.peak_years_remaining} peak years remaining
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* "Injury: 0% · Low Risk" reads as a medical clearance. It was
                  an empty table: no age, no history, no workload, so nothing
                  added to the score and nothing is what it reported. */}
              {report.physical_profile.injury_risk_factors.risk_level === null ? (
                <div className="mt-4 border border-dashed border-rule-strong p-4">
                  <h5 className="label mb-2">Injury risk — not assessed</h5>
                  <p className="text-sm text-ink-soft max-w-read">
                    {report.physical_profile.injury_risk_factors.basis ??
                      'This source carries no age, no injury history and no workload.'}
                  </p>
                </div>
              ) : (
                <div className="mt-4 bg-flag-wash p-4">
                  <h5 className="label text-flag mb-2">Injury Risk Assessment</h5>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-flag">Risk Level</span>
                    <span className="font-semibold text-flag">{report.physical_profile.injury_risk_factors.risk_level}</span>
                  </div>
                  {report.physical_profile.injury_risk_factors.basis && (
                    <p className="text-xs text-flag mt-2">{report.physical_profile.injury_risk_factors.basis}</p>
                  )}
                  {report.physical_profile.injury_risk_factors.mitigation_suggestions.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-flag mb-1">Mitigation:</p>
                      <ul className="text-xs text-flag space-y-1">
                        {report.physical_profile.injury_risk_factors.mitigation_suggestions.map((suggestion, i) => (
                          <li key={i}>• {suggestion}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderMarketAnalysis = () => {
    const projectionData = Object.entries(report.market_analysis.value_projections).map(([year, data]) => ({
      // Labelled in years from today, not ages: the source has no birth
      // dates, so every age here descends from the assumed 26 and would
      // contradict the note that says age is unavailable.
      year: year.replace('year_', 'Year '),
      value: data.value / 1000000,
      change: data.change_pct
    }));

    return (
      <div className="space-y-6">
        <div className="bg-paper-card border border-rule rounded-sm p-6">
          <h3 className="text-xl font-semibold mb-6">Market Value Analysis</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-field-wash p-4 rounded-sm text-center">
              <div className="text-2xl font-bold text-field">{formatCurrency(report.market_analysis.current_market_value)}</div>
              <div className="text-sm text-ink-soft mt-1">Current Value</div>
            </div>
            <div className="bg-field-wash p-4 rounded-sm text-center">
              <div className="text-2xl font-bold text-field">{report.market_analysis.value_assessment.assessment}</div>
              <div className="text-sm text-ink-soft mt-1">Value Assessment</div>
              {/* The verdict compares a Kumu estimate against other Kumu
                  estimates — no observed fee is involved. Saying so is the
                  difference between an analytical construct and a claim about
                  the transfer market. */}
              <div className="text-xs text-ink-faint mt-2 leading-snug">
                Kumu estimate vs Kumu-valued peers, not observed transfer fees
              </div>
            </div>
            <div className="bg-paper-sunk p-4 rounded-sm text-center">
              <div className="text-2xl font-bold text-ink">{formatPercentage(report.market_analysis.roi_analysis.roi_percentage)}</div>
              <div className="text-sm text-ink-soft mt-1">Projected ROI</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-ink-soft mb-4">Value Projections</h4>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={projectionData}>
                <CartesianGrid strokeDasharray="3 3" />
                 <XAxis dataKey="year" />
                 <YAxis />
                 <Tooltip formatter={(value) => `€${Number(value).toFixed(1)}M`} />
                 <Line type="monotone" dataKey="value" stroke="#C25A3A" strokeWidth={3} dot={{ fill: '#C25A3A', r: 6 }} />
               </LineChart>
             </ResponsiveContainer>
           </div>
           
           <div>
             <h4 className="font-medium text-ink-soft mb-4">Financial Assessment</h4>
             <div className="space-y-3">
               <div className="p-3 bg-paper-sunk">
                 <div className="flex justify-between items-center gap-4">
                   <span className="text-ink-soft">vs valued peers</span>
                   <span className="font-medium tabular">
                     {report.market_analysis.value_assessment.vs_comparables ?? '—'}
                   </span>
                 </div>
                 {/* The comparison is against Kumü's own valuations of other
                     players, not against transfers. The row used to be
                     labelled "vs Comparable Transfers" two panels below a
                     caveat saying no observed fee enters any calculation. */}
                 {report.market_analysis.value_assessment.basis && (
                   <p className="mt-2 text-xs text-ink-faint">
                     {report.market_analysis.value_assessment.basis}
                   </p>
                 )}
               </div>
               <div className="flex justify-between items-center p-3 bg-paper-sunk rounded">
                 <span className="text-ink-soft">Breakeven Period</span>
                 <span className="font-medium">{report.market_analysis.roi_analysis.breakeven_period}</span>
               </div>
               <div className="flex justify-between items-center p-3 bg-paper-sunk rounded">
                 <span className="text-ink-soft">Risk-Adjusted ROI</span>
                 <span className="font-medium">{formatPercentage(report.market_analysis.roi_analysis.risk_adjusted_roi)}</span>
               </div>
             </div>
             
             <div className="mt-4 p-4 bg-flag-wash rounded-sm">
               <p className="text-sm text-flag">
                 <span className="font-medium">Recommendation:</span> {report.market_analysis.value_assessment.recommendation}
               </p>
             </div>
           </div>
         </div>
       </div>
     </div>
   );
 };

 const renderComparison = () => (
   <div className="space-y-6">
     <div className="bg-paper-card border border-rule rounded-sm p-6">
       <h3 className="text-xl font-semibold mb-6">Comparative Analysis</h3>
       
       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
         <div className="bg-field-wash p-6 rounded-sm">
           <h4 className="font-medium text-ink mb-4">Squad Comparison</h4>
           <div className="text-center mb-4">
             <div className="text-3xl font-bold text-field">{report.comparison_analysis.squad_comparison.performance_improvement}</div>
             <div className="text-sm text-ink-soft mt-1">Performance Improvement</div>
           </div>
           <div className="bg-paper-card p-3 rounded text-center">
             <span className="text-field-dark font-medium">{report.comparison_analysis.squad_comparison.immediate_impact}</span>
           </div>
          {/* Which group the percentage is measured against: the club's own
              squad when it has one, otherwise database peers. Without this the
              number is ambiguous. */}
          {(report.comparison_analysis.squad_comparison as any).basis && (
            <p className="text-xs text-ink-faint mt-3 text-center italic">
              {(report.comparison_analysis.squad_comparison as any).basis}
            </p>
          )}
          {((report.comparison_analysis.squad_comparison as any).current_options || []).length > 0 && (
            <div className="mt-3 space-y-1">
              {((report.comparison_analysis.squad_comparison as any).current_options || []).map((peer: any) => (
                <div key={peer.name} className="flex justify-between text-xs text-ink-soft">
                  <span>{peer.name}</span>
                  <span className="font-medium">{peer.performance_index}</span>
                </div>
              ))}
            </div>
          )}
         </div>
         
         <div className="bg-field-wash p-6 rounded-sm">
           <h4 className="font-medium text-ink mb-4">League Standing</h4>
           <div className="text-center mb-4">
             <div className="text-3xl font-bold text-field">{ordinal(report.comparison_analysis.league_comparison.league_percentile)}</div>
             <div className="text-sm text-ink-soft mt-1">League Percentile</div>
           </div>
           <div className="bg-paper-card p-3 rounded text-center">
             <span className="text-field-dark font-medium">{report.comparison_analysis.league_comparison.statistical_rank}</span>
           </div>
         </div>
       </div>

       <div className="mt-6 p-4 bg-paper-sunk rounded-sm">
         <div className="flex items-center gap-2 mb-2">
           <Target className="w-5 h-5 text-ink-soft" />
           <h4 className="font-medium text-ink-soft">Overall Assessment</h4>
         </div>
         <p className="text-ink-soft">{report.comparison_analysis.upgrade_assessment}</p>
       </div>
     </div>
   </div>
 );

 const renderRiskAssessment = () => {
   const riskData = Object.entries(report.risk_assessment.risk_factors).map(([type, data]) => ({
     type: type.replace(/_/g, ' ').replace(/risk/g, ''),
     score: data.score,
     level: data.level
   }));

   return (
     <div className="space-y-6">
       <div className="bg-paper-card border border-rule rounded-sm p-6">
         <h3 className="text-xl font-semibold mb-6">Risk Assessment</h3>
         
         <div className="mb-6">
           <RiskMeter
             score={report.risk_assessment.risk_score}
             level={report.risk_assessment.overall_risk_level}
             basis={report.risk_assessment.risk_basis}
           />
         </div>

         <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
           {riskData.map((risk, i) => (
             <div key={i} className={`p-4 rounded-sm ${
               risk.level === 'Low' ? 'bg-field-wash' :
               risk.level === 'Moderate' ? 'bg-flag-wash' :
               'bg-loss-wash'
             }`}>
               <div className="text-sm font-medium capitalize text-ink-soft">{risk.type}</div>
               <div className={`text-lg font-bold mt-1 ${
                 risk.level === 'Low' ? 'text-field' :
                 risk.level === 'Moderate' ? 'text-flag' :
                 'text-loss'
               }`}>
                 {typeof risk.score === 'number' ? `${risk.score.toFixed(0)}%` : '—'}
               </div>
               <div className={`text-xs mt-1 ${
                 risk.level === 'Low' ? 'text-field-dark' :
                 risk.level === 'Moderate' ? 'text-flag' :
                 'text-loss'
               }`}>
                 {risk.level ? `${risk.level} Risk` : 'Not assessed'}
               </div>
             </div>
           ))}
         </div>

         {report.risk_assessment.mitigation_plan.length > 0 && (
           <div className="bg-field-wash p-4 rounded-sm">
             <h4 className="font-medium text-ink mb-3">Risk Mitigation Plan</h4>
             <ul className="space-y-2">
               {report.risk_assessment.mitigation_plan.map((action, i) => (
                 <li key={i} className="flex items-start gap-2 text-field-dark">
                   <Shield className="w-4 h-4 mt-0.5 flex-shrink-0" />
                   <span className="text-sm">{action}</span>
                 </li>
               ))}
             </ul>
           </div>
         )}
       </div>
     </div>
   );
 };

 const renderNegotiationStrategy = () => (
   <div className="space-y-6">
     <div className="bg-paper-card border border-rule rounded-sm p-6">
       <h3 className="text-xl font-semibold mb-6">Negotiation Strategy</h3>
       
       {/* The score was 50 for every player in the database and the label
           read "Weak", because the scale only went up from a base of 50 and
           every input it reads is absent. A constant is not a position. */}
       {report.negotiation_strategy.negotiation_position.strength === null ? (
         <div className="mb-6 border border-dashed border-rule-strong p-4">
           <h4 className="label mb-2">Negotiation position — not assessed</h4>
           <p className="max-w-read text-sm text-ink-soft">
             {report.negotiation_strategy.negotiation_position.basis ??
               'This source carries none of the facts that decide who holds the cards.'}
           </p>
         </div>
       ) : (
         <div className="mb-6 bg-paper-sunk p-4">
           <div className="flex items-center justify-between gap-4 mb-1">
             <span className="label">Negotiation position</span>
             <span className="font-display text-xl font-bold">
               {report.negotiation_strategy.negotiation_position.strength}
             </span>
           </div>
           <div className="text-sm text-ink-soft tabular">
             {report.negotiation_strategy.negotiation_position.score}/100
           </div>
           {report.negotiation_strategy.negotiation_position.basis && (
             <p className="mt-2 text-xs text-ink-faint">
               {report.negotiation_strategy.negotiation_position.basis}
             </p>
           )}
         </div>
       )}

       {/* Three prices that mean three things. There used to be a separate
           "Maximum Offer" and "Walk-away Price" seven million apart, which is
           a gap where a buyer would neither bid nor leave: they are one number
           seen from either side. The middle tile is now the target, which is
           where these settle. */}
       <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
         <div className="bg-paper-sunk p-4 text-center">
           <div className="label">Opening offer</div>
           <div className="figure mt-2">{formatCurrency(report.negotiation_strategy.offer_strategy.opening_offer)}</div>
         </div>
         <div className="bg-paper-sunk p-4 text-center">
           <div className="label">Target</div>
           <div className="figure mt-2">{formatCurrency(report.negotiation_strategy.offer_strategy.target_offer)}</div>
         </div>
         <div className="bg-flag-wash p-4 text-center">
           <div className="label text-flag">Maximum — and walk-away</div>
           <div className="figure mt-2 text-flag">{formatCurrency(report.negotiation_strategy.offer_strategy.maximum_offer)}</div>
         </div>
       </div>
       {report.negotiation_strategy.offer_strategy.basis && (
         <p className="mb-6 max-w-read text-sm text-ink-soft">
           {report.negotiation_strategy.offer_strategy.basis}
         </p>
       )}

       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
         <div>
           <h4 className="font-medium text-ink-soft mb-3">Timeline</h4>
           <div className="space-y-2">
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-ink-faint" />
               <div className="flex-1">
                 <div className="text-sm font-medium">Initial Contact</div>
                 <div className="text-sm text-ink-soft">{report.negotiation_strategy.timeline.initial_contact}</div>
               </div>
             </div>
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-ink-faint" />
               <div className="flex-1">
                 <div className="text-sm font-medium">First Offer</div>
                 <div className="text-sm text-ink-soft">{report.negotiation_strategy.timeline.first_offer}</div>
               </div>
             </div>
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-ink-faint" />
               <div className="flex-1">
                 <div className="text-sm font-medium">Negotiation Window</div>
                 <div className="text-sm text-ink-soft">{report.negotiation_strategy.timeline.negotiation_window}</div>
               </div>
             </div>
           </div>
           {report.negotiation_strategy.timeline.basis && (
             <p className="mt-3 max-w-read text-xs text-ink-faint">
               {report.negotiation_strategy.timeline.basis}
             </p>
           )}
         </div>
         
         <div>
           <h4 className="font-medium text-ink-soft mb-3">Key Tactics</h4>
           <ul className="space-y-2">
             {report.negotiation_strategy.tactics.map((tactic, i) => (
               <li key={i} className="flex items-start gap-2">
                 <ChevronRight className="w-4 h-4 text-ink-faint mt-0.5 flex-shrink-0" />
                 <span className="text-sm text-ink-soft">{tactic}</span>
               </li>
             ))}
           </ul>
         </div>
       </div>

       <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
         {report.negotiation_strategy.negotiation_position.factors.map((factor, i) => (
           <div key={i} className="flex items-center gap-2 p-3 bg-paper-sunk rounded">
             <Check className="w-5 h-5 text-field flex-shrink-0" />
             <span className="text-sm text-ink-soft">{factor}</span>
           </div>
         ))}
       </div>
     </div>
   </div>
 );

 const renderContent = () => {
   switch (activeSection) {
     case 'executive': return renderExecutiveSummary();
     case 'statistical': return renderStatisticalAnalysis();
     case 'tactical': return renderTacticalAnalysis();
     case 'physical': return renderPhysicalProfile();
     case 'market': return renderMarketAnalysis();
     case 'comparison': return renderComparison();
     case 'risk': return renderRiskAssessment();
     case 'negotiation': return renderNegotiationStrategy();
     default: return null;
   }
 };

 return (
   <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
     {/* Masthead. A sporting director opens this to answer one question —
        does this player fit, and can I defend saying so — so the name, the
        destination and the verdict come first, and the reading rules sit
        beside them rather than in a footnote nobody gets to. */}
    <header className="mb-10">
      <div className="flex flex-wrap items-start justify-between gap-6 pb-6 border-b-[3px] border-ink">
        <div className="min-w-0">
          <div className="label text-clay-ink mb-3">Scouting report</div>
          <h1 className="font-display text-4xl md:text-5xl leading-none m-0">
            {report.report_metadata.player_name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-ink-soft">
            <span className="text-sm">Assessed for</span>
            {clubs.length > 0 ? (
              <select
                value={String(report.report_metadata.team_id ?? '')}
                onChange={(e) => regenerateForTeam(e.target.value)}
                disabled={switchingTeam}
                className="border border-rule rounded-sm px-2 py-1 text-sm bg-paper-card
                           text-ink disabled:opacity-60"
                title="Run this report against another club"
              >
                {clubs.map((c: any) => (
                  <option key={c.id} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            ) : (
              <span className="text-ink">{report.report_metadata.team_name}</span>
            )}
            {switchingTeam && (
              <span className="text-sm text-ink-faint">regenerating…</span>
            )}
          </div>
          <p className="mt-2 text-sm text-ink-faint">
            {new Date(report.report_metadata.generated_date).toLocaleDateString()}
            {report.report_metadata.data_coverage &&
              ` · ${report.report_metadata.data_coverage.available_fields} of ${report.report_metadata.data_coverage.total_fields} data sources available`}
          </p>
        </div>

        <div className="flex items-start gap-10 shrink-0">
          <div>
            <div className="figure">
              {report.executive_summary?.match_score != null
                ? `${Number(report.executive_summary.match_score).toFixed(1)}%`
                : '—'}
            </div>
            <div className="text-xs text-ink-faint mt-1">Match compatibility</div>
            {report.executive_summary?.recommendation && (
              <div className="text-xs text-field font-medium mt-0.5">
                {report.executive_summary.recommendation.toLowerCase()}
              </div>
            )}
          </div>
          <div>
            <div className="figure">
              {report.executive_summary?.overall_percentile != null
                ? report.executive_summary.overall_percentile
                : '—'}
            </div>
            <div className="text-xs text-ink-faint mt-1">League percentile</div>
          </div>
          <button
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="btn-quiet flex items-center gap-2 disabled:opacity-60
                       disabled:cursor-not-allowed mt-2"
          >
            <Download className="w-4 h-4" />
            {downloadingPdf ? "Generating…" : "Export PDF"}
          </button>
        </div>
      </div>

      {/* The legend for the marks used throughout. Stated once, here, so the
          figures below can carry their origin without repeating a caveat. */}
      <div className="mt-5 flex flex-wrap gap-x-8 gap-y-2 text-xs text-ink-soft">
        <span><span className="is-measured font-medium">Measured</span> from match events</span>
        <span><span className="is-estimated font-medium">Estimated</span> by Kumü where the source carries nothing</span>
        <span><span className="is-curated font-medium">Decided</span> in advance and replaced as data arrives</span>
      </div>
      <p className="mt-3 max-w-read text-sm text-ink-soft leading-relaxed">
        Age is not carried by this source, so no age-dependent judgement is made. Market
        values are estimated from performance. Club playing styles and expected
        levels are declared judgements, and roles that rely on aerial duels or
        blocks score low because the source does not record them.
      </p>
    </header>

     <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
       {/* Sidebar Navigation */}
       <div className="lg:col-span-1">
         {/* A document's contents, not a toolbar. Nine labelled sections do
             not need nine icons competing with the report beside them; a rule
             marking the current one is enough to say where the reader is. */}
         <nav className="sticky top-24 border-l border-rule">
           {sections.map((section) => (
             <button
               key={section.id}
               onClick={() => setActiveSection(section.id)}
               aria-current={activeSection === section.id ? 'true' : undefined}
               className={`w-full text-left pl-4 py-2.5 -ml-px border-l-2 transition-colors ${
                 activeSection === section.id
                   ? 'border-field text-ink font-medium'
                   : 'border-transparent text-ink-faint hover:text-ink-soft'
               }`}
             >
               <span className="text-sm">{section.name}</span>
             </button>
           ))}
         </nav>
       </div>

       {/* Main Content */}
       <div className="lg:col-span-3">
         {renderContent()}
       </div>
     </div>
   </div>
 );
};

export default ScoutingReport;
