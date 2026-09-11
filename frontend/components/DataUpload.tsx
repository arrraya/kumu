'use client'
import React, { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, LogIn, LogOut, Upload, XCircle } from 'lucide-react'
import { apiService, session } from '@/lib/api'

/**
 * Loading a club's own data.
 *
 * The order here is deliberate: a payload can be VALIDATED without an account,
 * because deciding whether your data is usable should not require signing up
 * first. Only writing needs a login. The capability report is shown before the
 * upload button appears, so nobody discovers a section is empty after the fact
 * — the same declared-provenance habit the reports follow, moved to the moment
 * the data changes hands.
 */

const EJEMPLO = {
  source: 'mi-proveedor',
  club: {
    external_id: 'mi-club',
    name: 'Nombre del club',
    league: 'Liga',
    budget: 8000000,
    possession: 0.53,
    pressing_intensity: 0.6,
    squad: ['jugador-1'],
  },
  players: [
    {
      external_id: 'jugador-1',
      name: 'Nombre del jugador',
      position: 'ST',
      metrics: { shooting: { goals_per_90: 0.5, shots_per_90: 2.4 } },
      performance_history: [
        { match_id: 1, goals: 1, shots: 3, pass_completion: 0.78 },
        { match_id: 2, goals: 0, shots: 2, pass_completion: 0.81 },
        { match_id: 3, goals: 1, shots: 4, pass_completion: 0.75 },
      ],
    },
  ],
}

const DataUpload: React.FC = () => {
  const [raw, setRaw] = useState('')
  const [report, setReport] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [signedIn, setSignedIn] = useState(() => Boolean(session.get()))
  const [org, setOrg] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const parsed = useMemo(() => {
    if (!raw.trim()) return null
    try {
      return JSON.parse(raw)
    } catch {
      return undefined // distinct from null: present but unparseable
    }
  }, [raw])

  const login = useCallback(async () => {
    setError(null)
    setBusy(true)
    try {
      const data = await apiService.auth.login(email, password)
      setOrg(data.organization)
      setSignedIn(true)
      setPassword('')
    } catch {
      setError('No pudimos iniciar sesión con esos datos.')
    } finally {
      setBusy(false)
    }
  }, [email, password])

  const logout = useCallback(() => {
    apiService.auth.logout()
    setSignedIn(false)
    setOrg(null)
    setResult(null)
  }, [])

  const validate = useCallback(async () => {
    setError(null)
    setResult(null)
    setBusy(true)
    try {
      setReport(await apiService.ingest.validate(parsed))
    } catch (e: any) {
      setReport(null)
      const detail = e?.response?.data?.detail
      setError(
        Array.isArray(detail)
          ? detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(' · ')
          : 'El archivo no cumple el contrato de datos.'
      )
    } finally {
      setBusy(false)
    }
  }, [parsed])

  const upload = useCallback(async () => {
    setError(null)
    setBusy(true)
    try {
      setResult(await apiService.ingest.upload(parsed))
    } catch (e: any) {
      setError(e?.response?.status === 401
        ? 'La sesión expiró. Volvé a entrar.'
        : 'No pudimos cargar los datos.')
      if (e?.response?.status === 401) setSignedIn(false)
    } finally {
      setBusy(false)
    }
  }, [parsed])

  const readFile = useCallback((file: File) => {
    const reader = new FileReader()
    reader.onload = () => setRaw(String(reader.result || ''))
    reader.readAsText(file)
  }, [])

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Cargar tus datos</h2>
            <p className="text-sm text-gray-600 mt-1 max-w-2xl">
              Kumü mide a tus jugadores contra la población de referencia, así que
              un plantel chico obtiene índices comparables con los de cualquier otro club.
            </p>
          </div>
          {signedIn ? (
            <button onClick={logout}
              className="shrink-0 px-3 py-2 text-sm text-gray-700 border rounded-lg hover:bg-gray-50 flex items-center gap-2">
              <LogOut className="w-4 h-4" /> Salir{org ? ` · ${org}` : ''}
            </button>
          ) : null}
        </div>
      </div>

      {!signedIn && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-1">Entrar</h3>
          <p className="text-sm text-gray-600 mb-4">
            Podés validar un archivo sin cuenta. Para guardarlo hace falta entrar.
          </p>
          <div className="flex flex-wrap gap-3">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="correo" autoComplete="username"
              className="flex-1 min-w-[200px] px-3 py-2 border rounded-lg text-sm" />
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="contraseña" autoComplete="current-password"
              className="flex-1 min-w-[200px] px-3 py-2 border rounded-lg text-sm" />
            <button onClick={login} disabled={busy || !email || !password}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 flex items-center gap-2">
              <LogIn className="w-4 h-4" /> Entrar
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-gray-900">Tu archivo</h3>
          <div className="flex items-center gap-3">
            <button onClick={() => setRaw(JSON.stringify(EJEMPLO, null, 2))}
              className="text-sm text-green-700 hover:underline">
              Ver un ejemplo
            </button>
            <label className="text-sm text-green-700 hover:underline cursor-pointer">
              Subir archivo
              <input type="file" accept=".json,application/json" className="hidden"
                onChange={(e) => e.target.files?.[0] && readFile(e.target.files[0])} />
            </label>
          </div>
        </div>
        <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={12}
          spellCheck={false} placeholder="Pegá acá el JSON con tus jugadores y tu club"
          className="w-full px-3 py-2 border rounded-lg font-mono text-xs" />
        {parsed === undefined && raw.trim() && (
          <p className="text-sm text-amber-700 mt-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> El texto no es JSON válido.
          </p>
        )}
        <div className="flex gap-3 mt-4">
          <button onClick={validate} disabled={busy || !parsed}
            className="px-4 py-2 border border-green-600 text-green-700 rounded-lg text-sm hover:bg-green-50 disabled:opacity-50">
            Revisar
          </button>
          <button onClick={upload} disabled={busy || !parsed || !report || !signedIn}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 flex items-center gap-2">
            <Upload className="w-4 h-4" /> Guardar en Kumü
          </button>
        </div>
        {error && (
          <p className="text-sm text-red-700 mt-3 flex items-start gap-2">
            <XCircle className="w-4 h-4 mt-0.5 shrink-0" /> {error}
          </p>
        )}
      </div>

      {report && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-1">Qué habilita este archivo</h3>
          <p className="text-sm text-gray-600 mb-4">
            {report.players_received} jugadores{report.club ? ` · ${report.club}` : ''}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(report.capabilities || {}).map(([key, cap]: any) => (
              <div key={key} className="flex items-start gap-2 p-3 rounded-lg bg-gray-50">
                {cap.enabled
                  ? <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
                  : <XCircle className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800">{key.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-gray-600">{cap.requires}</div>
                </div>
              </div>
            ))}
          </div>
          {(report.warnings || []).length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200">
              {report.warnings.map((w: string, i: number) => (
                <p key={i} className="text-sm text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {w}
                </p>
              ))}
            </div>
          )}
          {!signedIn && (
            <p className="text-sm text-gray-600 mt-4">
              Para guardarlo, entrá con tu cuenta arriba.
            </p>
          )}
        </div>
      )}

      {result && (
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-600">
          <h3 className="font-medium text-gray-900 mb-2">Cargado</h3>
          <p className="text-sm text-gray-700">
            {result.result.players_written} jugadores guardados
            {result.result.club
              ? ` · ${result.result.club.name} con ${result.result.club.squad_size} en plantel`
              : ''}
          </p>
          {result.result.positions_without_reference?.length > 0 && (
            <p className="text-sm text-amber-700 mt-2">
              Sin referencia suficiente para escalar estas posiciones:{' '}
              {result.result.positions_without_reference.join(', ')}. Sus índices quedan
              en escala cruda y así se declaran.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default DataUpload
