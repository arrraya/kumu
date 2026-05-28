'use client'

import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, BarChart, Bar, RadarChart, PolarGrid, 
  PolarAngleAxis, PolarRadiusAxis, Radar, XAxis, YAxis, 
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell 
} from 'recharts';
import { 
  User, TrendingUp, DollarSign, Target, FileText, 
  ChevronRight, Activity, Shield, Zap, Users, Eye 
} from 'lucide-react';
import { api } from '@/lib/api';
import { Player, Team, Match } from '@/types';
import PlayerCard from './PlayerCard';
import MatchCard from './MatchCard';
import PerformanceChart from './PerformanceChart';

interface PlayerMatchingProps {
  selectedPlayer: Player | null;
  setSelectedPlayer: (player: Player | null) => void;
  selectedMatch: Match | null;
  setSelectedMatch: (match: Match | null) => void;
  setActiveView: (view: string) => void;
}

const PlayerMatching: React.FC<PlayerMatchingProps> = ({
  selectedPlayer,
  setSelectedPlayer,
  selectedMatch,
  setSelectedMatch,
  setActiveView
}) => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [filters, setFilters] = useState({
    position: '',
    minAge: '',
    maxAge: '',
    search: ''
  });

  useEffect(() => {
    fetchPlayers();
  }, [filters]);

  // Add this useEffect to fetch matches when a player is selected
  useEffect(() => {
    if (selectedPlayer && selectedPlayer.id) {
      fetchMatches(selectedPlayer.id.toString());
    } else {
      setMatches([]);
    }
  }, [selectedPlayer]);

  const fetchPlayers = async () => {
    try {
      setLoading(true);
      const data = await api.players.getAll({
        position: filters.position || undefined,
        min_age: filters.minAge || undefined,
        max_age: filters.maxAge || undefined,
        search: filters.search || undefined
      });
      setPlayers(data);
    } catch (error) {
      console.error('Error fetching players:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMatches = async (playerId: string) => {
    try {
      setMatchesLoading(true);
      setSelectedMatch(null);
      
      // For now, pass empty team_ids array - backend will handle it
      const matchData = await api.matches.calculate(playerId, []);
      setMatches(matchData);
    } catch (error) {
      console.error('Error fetching matches:', error);
      setMatches([]);
    } finally {
      setMatchesLoading(false);
    }
  };

  const handlePlayerSelect = (player: Player) => {
    setSelectedPlayer(player);
    setSelectedMatch(null);
    // Matches will be fetched by the useEffect
  };

  const handleViewReport = async () => {
    if (!selectedPlayer || !selectedMatch) return;
    try {
      const report = await api.reports.generate(selectedMatch?.id ?? 0);
      localStorage.setItem("currentReport", JSON.stringify(report));
      setActiveView("report");
    } catch (error) {
      console.error("Error generating report:", error);
    }
  };

  const formatCurrency = (value: number) => `€${(value / 1000000).toFixed(1)}M`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-md p-4 mb-4">
            <h3 className="text-lg font-semibold mb-4">Filters</h3>
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Search players..."
                className="w-full p-2 border rounded-lg"
                value={filters.search}
                onChange={(e) => setFilters({...filters, search: e.target.value})}
              />
              <select
                className="w-full p-2 border rounded-lg"
                value={filters.position}
                onChange={(e) => setFilters({...filters, position: e.target.value})}
              >
                <option value="">All Positions</option>
                <option value="GK">GK</option>
                <option value="CB">CB</option>
                <option value="RB">RB</option>
                <option value="LB">LB</option>
                <option value="CDM">CDM</option>
                <option value="CM">CM</option>
                <option value="CAM">CAM</option>
                <option value="RW">RW</option>
                <option value="LW">LW</option>
                <option value="ST">ST</option>
              </select>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Min Age"
                  className="p-2 border rounded-lg"
                  value={filters.minAge}
                  onChange={(e) => setFilters({...filters, minAge: e.target.value})}
                />
                <input
                  type="number"
                  placeholder="Max Age"
                  className="p-2 border rounded-lg"
                  value={filters.maxAge}
                  onChange={(e) => setFilters({...filters, maxAge: e.target.value})}
                />
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow-md p-4">
            <h3 className="text-lg font-semibold mb-4">Available Players</h3>
            {loading ? (
              <div>Loading players...</div>
            ) : (
              <div className="space-y-4">
                {players.map((player) => (
                  <PlayerCard
                    key={player.id}
                    player={player}
                    onClick={() => handlePlayerSelect(player)}
                    isSelected={selectedPlayer?.id === player.id}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          {selectedPlayer ? (
            <>
              <div className="bg-white p-6 rounded-lg shadow-md mb-6">
                <div className="flex items-center gap-6">
                  <div className="w-24 h-24 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="w-12 h-12 text-gray-500" />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold text-gray-900">{selectedPlayer.name}</h2>
                    <div className="text-gray-600 mt-1">
                      {selectedPlayer.position} • {selectedPlayer.age} years • {selectedPlayer.nationality}
                    </div>
                    <div className="text-gray-600">
                      €{(selectedPlayer.marketValue / 1000000).toFixed(1)}M • {selectedPlayer.currentTeam}
                    </div>
                  </div>
                </div>
                
                {selectedPlayer.performanceIndex && (
                  <PerformanceChart player={selectedPlayer} />
                )}
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">Compatible Teams</h3>
                {matchesLoading ? (
                  <div>Loading matches...</div>
                ) : matches.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {matches.map((match, index) => (
                      <MatchCard
                        key={index}
                        match={match}
                        onClick={() => setSelectedMatch(match)}
                        isSelected={selectedMatch === match}
                        onViewReport={handleViewReport}
                      />
                    ))}
                  </div>
                ) : (
                  <div>No compatible teams found</div>
                )}
              </div>

              {selectedMatch && (
                <div className="mt-6 bg-white p-6 rounded-lg shadow-md">
                  <h4 className="text-lg font-semibold mb-4">Match Details</h4>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">Team:</span> {selectedMatch.team.name}
                    </div>
                    <div>
                      <span className="font-medium">League:</span> {selectedMatch.team.league}
                    </div>
                    <div>
                      <span className="font-medium">Overall Score:</span> {selectedMatch.score.overall.toFixed(1)}%
                    </div>
                    <div>
                      <span className="font-medium">Offer Range:</span> {formatCurrency(selectedMatch.offer.minimum)} - {formatCurrency(selectedMatch.offer.maximum)}
                    </div>
                    <div>
                      <span className="font-medium">Recommendation:</span> {selectedMatch.recommendation}
                    </div>
                    <button
                      onClick={handleViewReport}
                      className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                    >
                      Generate Scouting Report
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-gray-50 rounded-lg p-12 text-center">
              <User className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Select a player to see matching teams</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlayerMatching;
