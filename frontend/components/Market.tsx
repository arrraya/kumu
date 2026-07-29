'use client'
import React, { useEffect, useMemo, useState } from 'react'
import {
  TrendingUp, TrendingDown, Star, Search, Wallet, X, ArrowUpRight, ArrowDownRight,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '@/lib/api'

const WATCHLIST_KEY = 'kumu_watchlist'
const PORTFOLIO_KEY = 'kumu_portfolio'
const STARTING_CASH = 500_000_000   // €500M virtual budget

type Row = {
  player_id: number
  name: string
  position: string
  team: string
  nationality: string
  current_price: number
  opening_price: number
  total_change_pct: number
  last_change_pct: number
  high: number
  low: number
  volatility: number
  matches: number
  performance_index: number | null
}

type Holding = { player_id: number; name: string; shares: number; buy_price: number }

const money = (v: number) => `€${(v / 1_000_000).toFixed(1)}M`
const pct = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`

const load = <T,>(key: string, fallback: T): T => {
  try {
    const raw = typeof window !== 'undefined' ? window.localStorage.getItem(key) : null
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}
const save = (key: string, value: unknown) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable */
  }
}

const Market: React.FC = () => {
  const [rows, setRows] = useState<Row[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [position, setPosition] = useState('')
  const [sort, setSort] = useState('change')
  const [order, setOrder] = useState('desc')
  const [tab, setTab] = useState<'market' | 'watchlist' | 'portfolio'>('market')

  const [watchlist, setWatchlist] = useState<number[]>([])
  const [portfolio, setPortfolio] = useState<Holding[]>([])
  const [cash, setCash] = useState<number>(STARTING_CASH)

  const [selected, setSelected] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    setWatchlist(load<number[]>(WATCHLIST_KEY, []))
    const saved = load<{ holdings: Holding[]; cash: number }>(PORTFOLIO_KEY, {
      holdings: [], cash: STARTING_CASH,
    })
    setPortfolio(saved.holdings || [])
    setCash(typeof saved.cash === 'number' ? saved.cash : STARTING_CASH)
  }, [])

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true)
        const [list, sum] = await Promise.all([
          api.market.list({ sort, order, position: position || undefined, search: search || undefined, limit: 300 }),
          api.market.summary(),
        ])
        setRows(list || [])
        setSummary(sum)
      } catch (e) {
        console.error('Market load failed:', e)
      } finally {
        setLoading(false)
      }
    }
    const t = setTimeout(run, search ? 300 : 0)
    return () => clearTimeout(t)
  }, [sort, order, position, search])

  const toggleWatch = (id: number) => {
    const next = watchlist.includes(id) ? watchlist.filter((w) => w !== id) : [...watchlist, id]
    setWatchlist(next)
    save(WATCHLIST_KEY, next)
  }

  const persistPortfolio = (holdings: Holding[], newCash: number) => {
    setPortfolio(holdings)
    setCash(newCash)
    save(PORTFOLIO_KEY, { holdings, cash: newCash })
  }

  const buy = (row: Row) => {
    if (cash < row.current_price) return
    const existing = portfolio.find((h) => h.player_id === row.player_id)
    const holdings = existing
      ? portfolio.map((h) =>
          h.player_id === row.player_id
            ? {
                ...h,
                shares: h.shares + 1,
                buy_price: (h.buy_price * h.shares + row.current_price) / (h.shares + 1),
              }
            : h,
        )
      : [...portfolio, { player_id: row.player_id, name: row.name, shares: 1, buy_price: row.current_price }]
    persistPortfolio(holdings, cash - row.current_price)
  }

  const sell = (row: Row) => {
    const existing = portfolio.find((h) => h.player_id === row.player_id)
    if (!existing) return
    const holdings =
      existing.shares > 1
        ? portfolio.map((h) => (h.player_id === row.player_id ? { ...h, shares: h.shares - 1 } : h))
        : portfolio.filter((h) => h.player_id !== row.player_id)
    persistPortfolio(holdings, cash + row.current_price)
  }

  const openDetail = async (id: number) => {
    try {
      setDetailLoading(true)
      setSelected(await api.market.detail(id))
    } catch (e) {
      console.error('Detail failed:', e)
    } finally {
      setDetailLoading(false)
    }
  }

  const priceById = useMemo(() => {
    const m: Record<number, Row> = {}
    rows.forEach((r) => (m[r.player_id] = r))
    return m
  }, [rows])

  const holdingsValue = portfolio.reduce(
    (s, h) => s + (priceById[h.player_id]?.current_price ?? h.buy_price) * h.shares, 0,
  )
  const invested = portfolio.reduce((s, h) => s + h.buy_price * h.shares, 0)
  const pnl = holdingsValue - invested

  const visible = useMemo(() => {
    if (tab === 'watchlist') return rows.filter((r) => watchlist.includes(r.player_id))
    if (tab === 'portfolio') return rows.filter((r) => portfolio.some((h) => h.player_id === r.player_id))
    return rows
  }, [rows, tab, watchlist, portfolio])

  const Delta: React.FC<{ value: number }> = ({ value }) => (
    <span className={`inline-flex items-center gap-1 font-medium ${
      value > 0 ? 'text-green-600' : value < 0 ? 'text-red-600' : 'text-gray-500'
    }`}>
      {value > 0 ? <ArrowUpRight className="w-3 h-3" /> : value < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
      {pct(value)}
    </span>
  )

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Player Market</h1>
        <p className="text-gray-600 mt-1">
          Prices derived from match-by-match performance against positional peers.
          <span className="text-gray-400"> Analytical construct, not observed transfer data.</span>
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold">{summary.listed_players}</div>
            <div className="text-sm text-gray-600">Listed players</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold">€{(summary.total_market_cap / 1e9).toFixed(2)}B</div>
            <div className="text-sm text-gray-600">Market cap</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">{summary.risers}</div>
            <div className="text-sm text-gray-600">Risers</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-red-600">{summary.fallers}</div>
            <div className="text-sm text-gray-600">Fallers</div>
          </div>
        </div>
      )}

      {portfolio.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2 text-gray-700 font-medium">
            <Wallet className="w-4 h-4" /> Portfolio
          </div>
          <div><span className="text-sm text-gray-600">Cash </span><span className="font-semibold">{money(cash)}</span></div>
          <div><span className="text-sm text-gray-600">Holdings </span><span className="font-semibold">{money(holdingsValue)}</span></div>
          <div>
            <span className="text-sm text-gray-600">P&amp;L </span>
            <span className={`font-semibold ${pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {pnl >= 0 ? '+' : '-'}{money(Math.abs(pnl))}
            </span>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow mb-6">
        <div className="flex flex-wrap items-center gap-3 p-4 border-b">
          {(['market', 'watchlist', 'portfolio'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${
                tab === t ? 'bg-green-50 text-green-700' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {t}
              {t === 'watchlist' && watchlist.length > 0 && ` (${watchlist.length})`}
              {t === 'portfolio' && portfolio.length > 0 && ` (${portfolio.length})`}
            </button>
          ))}

          <div className="flex-1" />

          <div className="relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-2 top-2.5" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search player"
              className="pl-8 pr-3 py-2 border rounded-md text-sm w-44"
            />
          </div>
          <select value={position} onChange={(e) => setPosition(e.target.value)}
            className="border rounded-md text-sm px-2 py-2">
            <option value="">All positions</option>
            {['GK','CB','RB','LB','CDM','CM','CAM','RW','LW','ST'].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <select value={`${sort}:${order}`} onChange={(e) => {
              const [s, o] = e.target.value.split(':'); setSort(s); setOrder(o)
            }}
            className="border rounded-md text-sm px-2 py-2">
            <option value="change:desc">Top gainers</option>
            <option value="change:asc">Top fallers</option>
            <option value="price:desc">Highest price</option>
            <option value="price:asc">Lowest price</option>
            <option value="volatility:desc">Most volatile</option>
            <option value="name:asc">Name A–Z</option>
          </select>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading market…</div>
        ) : visible.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {tab === 'watchlist' ? 'Your watchlist is empty — star players to follow them.'
              : tab === 'portfolio' ? 'No holdings yet — buy a player to start your portfolio.'
              : 'No players match these filters.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-3 py-2 text-left w-8"></th>
                  <th className="px-3 py-2 text-left">Player</th>
                  <th className="px-3 py-2 text-left">Pos</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">Last</th>
                  <th className="px-3 py-2 text-right">Vol</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const held = portfolio.find((h) => h.player_id === r.player_id)
                  return (
                    <tr key={r.player_id} className="border-t hover:bg-gray-50">
                      <td className="px-3 py-2">
                        <button onClick={() => toggleWatch(r.player_id)} title="Watch">
                          <Star className={`w-4 h-4 ${
                            watchlist.includes(r.player_id) ? 'text-yellow-500 fill-yellow-400' : 'text-gray-300'
                          }`} />
                        </button>
                      </td>
                      <td className="px-3 py-2">
                        <button onClick={() => openDetail(r.player_id)} className="text-left">
                          <div className="font-medium text-gray-900 hover:text-green-700">{r.name}</div>
                          <div className="text-xs text-gray-500">
                            {r.team}{held ? ` • ${held.shares} held` : ''}
                          </div>
                        </button>
                      </td>
                      <td className="px-3 py-2 text-gray-600">{r.position}</td>
                      <td className="px-3 py-2 text-right font-semibold">{money(r.current_price)}</td>
                      <td className="px-3 py-2 text-right"><Delta value={r.total_change_pct} /></td>
                      <td className="px-3 py-2 text-right"><Delta value={r.last_change_pct} /></td>
                      <td className="px-3 py-2 text-right text-gray-500">{r.volatility.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button onClick={() => buy(r)} disabled={cash < r.current_price}
                          className="px-2 py-1 text-xs rounded bg-green-600 text-white disabled:opacity-40 mr-1">
                          Buy
                        </button>
                        <button onClick={() => sell(r)} disabled={!held}
                          className="px-2 py-1 text-xs rounded bg-gray-200 text-gray-700 disabled:opacity-40">
                          Sell
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {(selected || detailLoading) && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
          onClick={() => setSelected(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6" onClick={(e) => e.stopPropagation()}>
            {detailLoading || !selected ? (
              <p className="text-gray-500">Loading…</p>
            ) : (
              <>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{selected.name}</h3>
                    <p className="text-sm text-gray-600">
                      {selected.position} • {selected.team} • {selected.matches} matches
                    </p>
                  </div>
                  <button onClick={() => setSelected(null)}><X className="w-5 h-5 text-gray-400" /></button>
                </div>

                <div className="flex flex-wrap gap-6 mb-4">
                  <div>
                    <div className="text-2xl font-bold">{money(selected.current_price)}</div>
                    <div className="text-sm text-gray-600">Current</div>
                  </div>
                  <div>
                    <div className={`text-2xl font-bold ${
                      selected.total_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {pct(selected.total_change_pct)}
                    </div>
                    <div className="text-sm text-gray-600">Since first match</div>
                  </div>
                  <div>
                    <div className="text-lg font-semibold">{money(selected.high)} / {money(selected.low)}</div>
                    <div className="text-sm text-gray-600">High / Low</div>
                  </div>
                </div>

                <ResponsiveContainer width="100%" height={220}>
                  <LineChart
                    data={(selected.series || []).map((s: any) => ({
                      label: `M${s.match}`,
                      price: s.price / 1_000_000,
                      change: s.change_pct,
                      goals: s.goals,
                      assists: s.assists,
                    }))}
                    margin={{ top: 10, right: 10, bottom: 5, left: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={['dataMin - 3', 'dataMax + 3']}
                      tickFormatter={(v) => `€${v.toFixed(0)}M`} />
                    <Tooltip content={({ active, payload, label }: any) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0].payload
                      return (
                        <div className="bg-white border rounded-md px-3 py-2 shadow-sm text-xs">
                          <p className="font-medium">Match {String(label).replace('M', '')}</p>
                          <p className="text-green-700">€{d.price.toFixed(1)}M ({pct(d.change)})</p>
                          {(d.goals > 0 || d.assists > 0) && (
                            <p className="text-gray-600">{d.goals}g • {d.assists}a</p>
                          )}
                        </div>
                      )
                    }} />
                    <Line type="monotone" dataKey="price" stroke="#16a34a" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Market
