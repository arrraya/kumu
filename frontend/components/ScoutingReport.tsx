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
  };
  executive_summary: {
    recommendation: string;
    action: string;
    match_score: number;
    overall_percentile: number;
    key_findings: string[];
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
    athletic_scores: {
      speed: { score: number; rating: string };
      endurance: { score: number; rating: string };
      intensity: { score: number; rating: string };
    };
    physical_age_analysis: {
      current_age: number;
      development_stage: string;
      peak_years_remaining: number;
    };
    injury_risk_factors: {
      risk_level: string;
      risk_score: number;
      risk_factors: string[];
      mitigation_suggestions: string[];
    };
  };
  market_analysis: {
    current_market_value: number;
    value_assessment: {
      assessment: string;
      recommendation: string;
      value_ratio: number;
      vs_comparables: string;
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
    overall_risk_level: string;
    risk_score: number;
    risk_factors: {
      [key: string]: { score: number; level: string };
    };
    mitigation_plan: string[];
  };
  negotiation_strategy: {
    negotiation_position: {
      strength: string;
      score: number;
      factors: string[];
    };
    offer_strategy: {
      opening_offer: number;
      maximum_offer: number;
      walk_away_price: number;
    };
    timeline: {
      initial_contact: string;
      first_offer: string;
      negotiation_window: string;
    };
    tactics: string[];
  };
}

const ScoutingReport: React.FC<ScoutingReportProps> = ({ player, match }) => {
  const [report, setReport] = useState<ScoutingReportData | null>(null);
  const [activeSection, setActiveSection] = useState('executive');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load report from localStorage or generate new one
    const savedReport = localStorage.getItem('currentReport');
    if (savedReport) {
      setReport(JSON.parse(savedReport));
      setLoading(false);
    } else if (player && match) {
      // In production, this would fetch from API
      generateMockReport();
    } else {
      setLoading(false);
    }
  }, [player, match]);

  const generateMockReport = () => {
    // This would be replaced with actual API call
    const mockReport: ScoutingReportData = {
      report_metadata: {
        generated_date: new Date().toISOString(),
        player_name: player?.name || '',
        player_id: player?.id || '',
        team_name: match?.team.name || '',
        team_id: match?.team.id || ''
      },
      executive_summary: {
        recommendation: "STRONGLY RECOMMENDED",
        action: "Proceed immediately with negotiations",
        match_score: match?.score.overall || 0,
        overall_percentile: 82,
        key_findings: [
          `Player ranks in the 82nd percentile overall`,
          `Match compatibility score: ${match?.score.overall || 0}%`,
          `Age profile: ${player?.age} years - ${player?.age && player.age < 26 ? 'Optimal' : 'Prime'}`,
          `Financial fit: ${match?.score.financial && match.score.financial > 80 ? 'Within budget' : 'Requires negotiation'}`
        ],
        executive_statement: `${player?.name} represents a strongly recommended acquisition for ${match?.team.name}. Statistical analysis places the player in the 82nd percentile for their position in ${match?.team.league}.`
      },
      statistical_overview: {
        position_specific_analysis: {},
        statistical_strengths: [
          "Key Passes Per 90: Elite (85th percentile)",
          "High Intensity Runs: Excellent (80th percentile)",
          "Progressive Passes Per 90: Excellent (78th percentile)"
        ],
        statistical_weaknesses: ["Aerial Duels Won: Below Average (35th percentile)"],
        consistency_rating: { rating: "Consistent", score: 75 },
        form_trajectory: { trend: "Improving", direction: "positive", slope: 0.15 }
      },
      tactical_analysis: {
        formation_compatibility: { 
          fit: "Perfect", 
          score: 100, 
          note: "Natural position in 4-3-3" 
        },
        style_compatibility: {
          compatibility_score: 85,
          player_style: "Creative Playmaker",
          notes: [
            "Excellent fit for possession-based system",
            "High work rate suits pressing system"
          ]
        },
        role_suitability: {
          best_role: "Playmaker",
          recommendation: "Best suited as Playmaker with 85% compatibility"
        },
        tactical_flexibility: {
          primary_position: player?.position || "CAM",
          alternative_positions: ["CM", "RW", "LW"],
          versatility_score: 80,
          tactical_flexibility: "High"
        }
      },
      physical_profile: {
        athletic_scores: {
          speed: { score: 78, rating: "Excellent" },
          endurance: { score: 82, rating: "Excellent" },
          intensity: { score: 85, rating: "Elite" }
        },
        physical_age_analysis: {
          current_age: player?.age || 23,
          development_stage: "Still developing physically",
          peak_years_remaining: 5
        },
        injury_risk_factors: {
          risk_level: "Low",
          risk_score: 15,
          risk_factors: ["Some injury history"],
          mitigation_suggestions: ["Comprehensive medical assessment before signing"]
        }
      },
      market_analysis: {
        current_market_value: player?.marketValue || 25000000,
        value_assessment: {
          assessment: "Fair value",
          recommendation: "Market-appropriate pricing",
          value_ratio: 1.05,
          vs_comparables: "+5.0% vs similar transfers"
        },
        value_projections: {
          year_1: { value: 28750000, age: 24, change_pct: 15.0 },
          year_2: { value: 31625000, age: 25, change_pct: 26.5 },
          year_3: { value: 33200000, age: 26, change_pct: 32.8 }
        },
        roi_analysis: {
          roi_percentage: 42.5,
          breakeven_period: "2-3 years",
          risk_adjusted_roi: 38.2
        }
      },
      comparison_analysis: {
        squad_comparison: {
          performance_improvement: "+18.5%",
          immediate_impact: "Likely starter",
          position_upgrade: true
        },
        league_comparison: {
          league_percentile: 82,
          vs_top_performers: "Top tier",
          statistical_rank: "Ranks approximately 2nd in position"
        },
        upgrade_assessment: "Clear upgrade - would improve squad quality"
      },
      risk_assessment: {
        overall_risk_level: "Moderate",
        risk_score: 28.5,
        risk_factors: {
          performance_risk: { score: 15, level: "Low" },
          injury_risk: { score: 25, level: "Moderate" },
          adaptation_risk: { score: 35, level: "Moderate" },
          financial_risk: { score: 20, level: "Low" },
          age_related_risk: { score: 10, level: "Low" }
        },
        mitigation_plan: [
          "Comprehensive medical examination",
          "Assign integration mentor",
          "Gradual tactical integration"
        ]
      },
      negotiation_strategy: {
        negotiation_position: {
          strength: "Strong",
          score: 75,
          factors: ["Contract expiring soon", "Multiple alternative targets available"]
        },
        offer_strategy: {
          opening_offer: (match?.offer.min || 20) * 1000000,
          maximum_offer: (match?.offer.max || 28) * 1000000,
          walk_away_price: (match?.offer.max || 28) * 1.1 * 1000000
        },
        timeline: {
          initial_contact: "Immediately",
          first_offer: "Within 48 hours",
          negotiation_window: "1-2 weeks"
        },
        tactics: [
          "Start with aggressive opening offer",
          "Set firm deadlines",
          "Emphasize alternative options"
        ]
      }
    };
    
    setReport(mockReport);
    setLoading(false);
  };

  const formatCurrency = (value: number) => `€${(value / 1000000).toFixed(1)}M`;
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

  const RecommendationBadge = ({ recommendation }: { recommendation: string }) => {
    const getColor = () => {
      if (recommendation.includes('STRONGLY')) return 'bg-green-100 text-green-800 border-green-200';
      if (recommendation.includes('RECOMMENDED')) return 'bg-blue-100 text-blue-800 border-blue-200';
      if (recommendation.includes('CONDITIONALLY')) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      return 'bg-red-100 text-red-800 border-red-200';
    };

    return (
      <span className={`px-4 py-2 rounded-full text-sm font-semibold border ${getColor()}`}>
        {recommendation}
      </span>
    );
  };

  const PercentileBar = ({ percentile, label }: { percentile: number; label: string }) => (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{percentile}th percentile</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${
            percentile >= 80 ? 'bg-green-600' :
            percentile >= 60 ? 'bg-blue-600' :
            percentile >= 40 ? 'bg-yellow-600' : 'bg-red-600'
          }`}
          style={{ width: `${percentile}%` }}
        />
      </div>
    </div>
  );

  const RiskMeter = ({ score, level }: { score: number; level: string }) => {
    const rotation = (score / 100) * 180 - 90;
    
    return (
      <div className="relative w-32 h-16 mx-auto">
        <svg viewBox="0 0 100 60" className="w-full h-full">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="#e5e7eb"
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
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="50%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
          </defs>
          <line
            x1="50"
            y1="50"
            x2="50"
            y2="20"
            stroke="#1f2937"
            strokeWidth="2"
            transform={`rotate(${rotation} 50 50)`}
          />
          <circle cx="50" cy="50" r="3" fill="#1f2937" />
        </svg>
        <div className="text-center mt-2">
          <div className="text-lg font-semibold">{level}</div>
          <div className="text-sm text-gray-600">{score.toFixed(1)}% risk</div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-green-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading scouting report...</p>
        </div>
      </div>
    );
  }

  if (!report || !player || !match) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white p-12 rounded-lg shadow-md text-center">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-600">No report available</h3>
          <p className="text-sm text-gray-500 mt-2">
            Select a player and team match to generate a scouting report
          </p>
        </div>
      </div>
    );
  }

  const renderExecutiveSummary = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold">Match Assessment</h3>
          <RecommendationBadge recommendation={report.executive_summary.recommendation} />
        </div>
        
        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <div className="text-3xl font-bold text-blue-600">{report.executive_summary.match_score}%</div>
            <div className="text-sm text-gray-600 mt-1">Match Compatibility</div>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-3xl font-bold text-green-600">{report.executive_summary.overall_percentile}th</div>
            <div className="text-sm text-gray-600 mt-1">League Percentile</div>
          </div>
        </div>

        <div className="border-t pt-4">
          <h4 className="font-medium text-gray-700 mb-3">Key Findings</h4>
          <ul className="space-y-2">
            {report.executive_summary.key_findings.map((finding, i) => (
              <li key={i} className="flex items-start gap-2">
                <Check className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                <span className="text-gray-600">{finding}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-700 italic">"{report.executive_summary.executive_statement}"</p>
        </div>

        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2 text-green-800">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Recommended Action:</span>
          </div>
          <p className="text-green-700 mt-1">{report.executive_summary.action}</p>
        </div>
      </div>
    </div>
  );

  const renderStatisticalAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-xl font-semibold mb-6">Performance Metrics</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div className="bg-green-50 p-4 rounded-lg">
            <h4 className="font-medium text-green-800 mb-3">Statistical Strengths</h4>
            <ul className="space-y-2">
              {report.statistical_overview.statistical_strengths.map((strength, i) => (
                <li key={i} className="text-sm text-green-700 flex items-start gap-2">
                  <TrendingUp className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{strength}</span>
                </li>
              ))}
            </ul>
          </div>
          
          <div className="bg-yellow-50 p-4 rounded-lg">
            <h4 className="font-medium text-yellow-800 mb-3">Areas for Development</h4>
            <ul className="space-y-2">
              {report.statistical_overview.statistical_weaknesses.map((weakness, i) => (
                <li key={i} className="text-sm text-yellow-700 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{weakness}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">Consistency</div>
            <div className="text-lg font-semibold">{report.statistical_overview.consistency_rating.rating}</div>
            <div className="text-sm text-gray-500">Score: {report.statistical_overview.consistency_rating.score}/100</div>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">Form Trajectory</div>
            <div className="text-lg font-semibold">{report.statistical_overview.form_trajectory.trend}</div>
            <div className="text-sm text-gray-500">Direction: {report.statistical_overview.form_trajectory.direction}</div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTacticalAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-xl font-semibold mb-6">Tactical Fit Analysis</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-blue-50 p-6 rounded-lg">
            <h4 className="font-medium text-blue-800 mb-4">Formation Compatibility</h4>
            <div className="text-center">
              <div className="text-4xl font-bold text-blue-600">{report.tactical_analysis.formation_compatibility.score}%</div>
              <div className="text-lg text-blue-700 mt-2">{report.tactical_analysis.formation_compatibility.fit}</div>
              <p className="text-sm text-blue-600 mt-2">{report.tactical_analysis.formation_compatibility.note}</p>
            </div>
          </div>
          
          <div className="bg-green-50 p-6 rounded-lg">
            <h4 className="font-medium text-green-800 mb-4">Style Compatibility</h4>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-600">{report.tactical_analysis.style_compatibility.compatibility_score}%</div>
              <div className="text-lg text-green-700 mt-2">{report.tactical_analysis.style_compatibility.player_style}</div>
            </div>
          </div>
        </div>

        <div className="mt-6">
          <h4 className="font-medium text-gray-700 mb-3">Tactical Notes</h4>
          <ul className="space-y-2">
            {report.tactical_analysis.style_compatibility.notes.map((note, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-600">
                <Check className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 p-4 bg-purple-50 rounded-lg">
          <h4 className="font-medium text-purple-800 mb-2">Best Tactical Role</h4>
          <p className="text-purple-700">{report.tactical_analysis.role_suitability.recommendation}</p>
          
          <div className="mt-4">
            <h5 className="text-sm font-medium text-purple-700 mb-2">Position Flexibility</h5>
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1 bg-purple-600 text-white rounded-full text-sm">
                {report.tactical_analysis.tactical_flexibility.primary_position}
              </span>
              {report.tactical_analysis.tactical_flexibility.alternative_positions.map((pos, i) => (
                <span key={i} className="px-3 py-1 bg-purple-200 text-purple-800 rounded-full text-sm">
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
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-xl font-semibold mb-6">Physical & Athletic Profile</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-700 mb-4">Athletic Attributes</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={athleticData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="attribute" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#3B82F6" radius={[8, 8, 0, 0]}>
                    {athleticData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={
                        entry.score >= 80 ? '#10B981' :
                        entry.score >= 60 ? '#3B82F6' :
                        '#F59E0B'
                      } />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            
            <div>
              <h4 className="font-medium text-gray-700 mb-4">Age & Development</h4>
              <div className="bg-blue-50 p-6 rounded-lg">
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600">{report.physical_profile.physical_age_analysis.current_age}</div>
                  <div className="text-sm text-gray-600 mt-1">years old</div>
                </div>
                <div className="mt-4 text-center">
                  <p className="text-blue-700 font-medium">{report.physical_profile.physical_age_analysis.development_stage}</p>
                  <p className="text-sm text-blue-600 mt-2">
                    {report.physical_profile.physical_age_analysis.peak_years_remaining} peak years remaining
                  </p>
                </div>
              </div>
              
              <div className="mt-4 bg-yellow-50 p-4 rounded-lg">
                <h5 className="font-medium text-yellow-800 mb-2">Injury Risk Assessment</h5>
                <div className="flex items-center justify-between">
                  <span className="text-yellow-700">Risk Level:</span>
                  <span className="font-semibold text-yellow-800">{report.physical_profile.injury_risk_factors.risk_level}</span>
                </div>
                {report.physical_profile.injury_risk_factors.mitigation_suggestions.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-yellow-700 mb-1">Mitigation:</p>
                    <ul className="text-xs text-yellow-600 space-y-1">
                      {report.physical_profile.injury_risk_factors.mitigation_suggestions.map((suggestion, i) => (
                        <li key={i}>• {suggestion}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderMarketAnalysis = () => {
    const projectionData = Object.entries(report.market_analysis.value_projections).map(([year, data]) => ({
      year: `Age ${data.age}`,
      value: data.value / 1000000,
      change: data.change_pct
    }));

    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-xl font-semibold mb-6">Market Value Analysis</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-blue-600">{formatCurrency(report.market_analysis.current_market_value)}</div>
              <div className="text-sm text-gray-600 mt-1">Current Value</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-green-600">{report.market_analysis.value_assessment.assessment}</div>
              <div className="text-sm text-gray-600 mt-1">Value Assessment</div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-purple-600">{formatPercentage(report.market_analysis.roi_analysis.roi_percentage)}</div>
              <div className="text-sm text-gray-600 mt-1">Projected ROI</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-700 mb-4">Value Projections</h4>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={projectionData}>
                <CartesianGrid strokeDasharray="3 3" />
                 <XAxis dataKey="year" />
                 <YAxis />
                 <Tooltip formatter={(value) => `€${Number(value).toFixed(1)}M`} />
                 <Line type="monotone" dataKey="value" stroke="#22c55e" strokeWidth={3} dot={{ fill: '#22c55e', r: 6 }} />
               </LineChart>
             </ResponsiveContainer>
           </div>
           
           <div>
             <h4 className="font-medium text-gray-700 mb-4">Financial Assessment</h4>
             <div className="space-y-3">
               <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                 <span className="text-gray-600">vs Comparable Transfers</span>
                 <span className="font-medium">{report.market_analysis.value_assessment.vs_comparables}</span>
               </div>
               <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                 <span className="text-gray-600">Breakeven Period</span>
                 <span className="font-medium">{report.market_analysis.roi_analysis.breakeven_period}</span>
               </div>
               <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                 <span className="text-gray-600">Risk-Adjusted ROI</span>
                 <span className="font-medium">{formatPercentage(report.market_analysis.roi_analysis.risk_adjusted_roi)}</span>
               </div>
             </div>
             
             <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
               <p className="text-sm text-yellow-800">
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
     <div className="bg-white rounded-lg shadow-md p-6">
       <h3 className="text-xl font-semibold mb-6">Comparative Analysis</h3>
       
       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
         <div className="bg-blue-50 p-6 rounded-lg">
           <h4 className="font-medium text-blue-800 mb-4">Squad Comparison</h4>
           <div className="text-center mb-4">
             <div className="text-3xl font-bold text-blue-600">{report.comparison_analysis.squad_comparison.performance_improvement}</div>
             <div className="text-sm text-gray-600 mt-1">Performance Improvement</div>
           </div>
           <div className="bg-white p-3 rounded text-center">
             <span className="text-blue-700 font-medium">{report.comparison_analysis.squad_comparison.immediate_impact}</span>
           </div>
         </div>
         
         <div className="bg-green-50 p-6 rounded-lg">
           <h4 className="font-medium text-green-800 mb-4">League Standing</h4>
           <div className="text-center mb-4">
             <div className="text-3xl font-bold text-green-600">{report.comparison_analysis.league_comparison.league_percentile}th</div>
             <div className="text-sm text-gray-600 mt-1">League Percentile</div>
           </div>
           <div className="bg-white p-3 rounded text-center">
             <span className="text-green-700 font-medium">{report.comparison_analysis.league_comparison.statistical_rank}</span>
           </div>
         </div>
       </div>

       <div className="mt-6 p-4 bg-gray-50 rounded-lg">
         <div className="flex items-center gap-2 mb-2">
           <Target className="w-5 h-5 text-gray-700" />
           <h4 className="font-medium text-gray-700">Overall Assessment</h4>
         </div>
         <p className="text-gray-600">{report.comparison_analysis.upgrade_assessment}</p>
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
       <div className="bg-white rounded-lg shadow-md p-6">
         <h3 className="text-xl font-semibold mb-6">Risk Assessment</h3>
         
         <div className="mb-6">
           <RiskMeter score={report.risk_assessment.risk_score} level={report.risk_assessment.overall_risk_level} />
         </div>

         <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
           {riskData.map((risk, i) => (
             <div key={i} className={`p-4 rounded-lg ${
               risk.level === 'Low' ? 'bg-green-50' :
               risk.level === 'Moderate' ? 'bg-yellow-50' :
               'bg-red-50'
             }`}>
               <div className="text-sm font-medium capitalize text-gray-700">{risk.type}</div>
               <div className={`text-lg font-bold mt-1 ${
                 risk.level === 'Low' ? 'text-green-600' :
                 risk.level === 'Moderate' ? 'text-yellow-600' :
                 'text-red-600'
               }`}>
                 {risk.score.toFixed(0)}%
               </div>
               <div className={`text-xs mt-1 ${
                 risk.level === 'Low' ? 'text-green-700' :
                 risk.level === 'Moderate' ? 'text-yellow-700' :
                 'text-red-700'
               }`}>
                 {risk.level} Risk
               </div>
             </div>
           ))}
         </div>

         {report.risk_assessment.mitigation_plan.length > 0 && (
           <div className="bg-blue-50 p-4 rounded-lg">
             <h4 className="font-medium text-blue-800 mb-3">Risk Mitigation Plan</h4>
             <ul className="space-y-2">
               {report.risk_assessment.mitigation_plan.map((action, i) => (
                 <li key={i} className="flex items-start gap-2 text-blue-700">
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
     <div className="bg-white rounded-lg shadow-md p-6">
       <h3 className="text-xl font-semibold mb-6">Negotiation Strategy</h3>
       
       <div className="mb-6 p-4 bg-blue-50 rounded-lg">
         <div className="flex items-center justify-between mb-2">
           <span className="font-medium text-blue-800">Negotiation Position:</span>
           <span className="text-lg font-bold text-blue-600">{report.negotiation_strategy.negotiation_position.strength}</span>
         </div>
         <div className="text-sm text-blue-700">
           Score: {report.negotiation_strategy.negotiation_position.score}/100
         </div>
       </div>

       <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
         <div className="bg-green-50 p-4 rounded-lg text-center">
           <div className="text-sm text-gray-600">Opening Offer</div>
           <div className="text-2xl font-bold text-green-600 mt-1">{formatCurrency(report.negotiation_strategy.offer_strategy.opening_offer)}</div>
         </div>
         <div className="bg-yellow-50 p-4 rounded-lg text-center">
           <div className="text-sm text-gray-600">Maximum Offer</div>
           <div className="text-2xl font-bold text-yellow-600 mt-1">{formatCurrency(report.negotiation_strategy.offer_strategy.maximum_offer)}</div>
         </div>
         <div className="bg-red-50 p-4 rounded-lg text-center">
           <div className="text-sm text-gray-600">Walk-away Price</div>
           <div className="text-2xl font-bold text-red-600 mt-1">{formatCurrency(report.negotiation_strategy.offer_strategy.walk_away_price)}</div>
         </div>
       </div>

       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
         <div>
           <h4 className="font-medium text-gray-700 mb-3">Timeline</h4>
           <div className="space-y-2">
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-gray-500" />
               <div className="flex-1">
                 <div className="text-sm font-medium">Initial Contact</div>
                 <div className="text-sm text-gray-600">{report.negotiation_strategy.timeline.initial_contact}</div>
               </div>
             </div>
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-gray-500" />
               <div className="flex-1">
                 <div className="text-sm font-medium">First Offer</div>
                 <div className="text-sm text-gray-600">{report.negotiation_strategy.timeline.first_offer}</div>
               </div>
             </div>
             <div className="flex items-center gap-3">
               <Calendar className="w-5 h-5 text-gray-500" />
               <div className="flex-1">
                 <div className="text-sm font-medium">Negotiation Window</div>
                 <div className="text-sm text-gray-600">{report.negotiation_strategy.timeline.negotiation_window}</div>
               </div>
             </div>
           </div>
         </div>
         
         <div>
           <h4 className="font-medium text-gray-700 mb-3">Key Tactics</h4>
           <ul className="space-y-2">
             {report.negotiation_strategy.tactics.map((tactic, i) => (
               <li key={i} className="flex items-start gap-2">
                 <ChevronRight className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
                 <span className="text-sm text-gray-600">{tactic}</span>
               </li>
             ))}
           </ul>
         </div>
       </div>

       <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
         {report.negotiation_strategy.negotiation_position.factors.map((factor, i) => (
           <div key={i} className="flex items-center gap-2 p-3 bg-gray-50 rounded">
             <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
             <span className="text-sm text-gray-700">{factor}</span>
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
     {/* Report Header */}
     <div className="bg-white rounded-lg shadow-md p-6 mb-6">
       <div className="flex items-center justify-between">
         <div>
           <h1 className="text-2xl font-bold text-gray-900">Scouting Report</h1>
           <p className="text-gray-600 mt-1">
             {report.report_metadata.player_name} → {report.report_metadata.team_name}
           </p>
           <p className="text-sm text-gray-500 mt-1">
             Generated: {new Date(report.report_metadata.generated_date).toLocaleDateString()}
           </p>
         </div>
         <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2">
           <Download className="w-4 h-4" />
           Export PDF
         </button>
       </div>
     </div>

     <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
       {/* Sidebar Navigation */}
       <div className="lg:col-span-1">
         <nav className="bg-white rounded-lg shadow-md p-4 sticky top-24">
           {sections.map((section) => {
             const Icon = section.icon;
             return (
               <button
                 key={section.id}
                 onClick={() => setActiveSection(section.id)}
                 className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors mb-2 ${
                   activeSection === section.id
                     ? 'bg-green-50 text-green-700'
                     : 'text-gray-700 hover:bg-gray-50'
                 }`}
               >
                 <Icon className="w-5 h-5" />
                 <span className="text-sm font-medium">{section.name}</span>
               </button>
             );
           })}
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
