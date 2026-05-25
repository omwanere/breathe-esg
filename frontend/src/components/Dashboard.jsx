import React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { 
  FileSpreadsheet, AlertOctagon, CheckCircle2, RefreshCw, 
  Layers, Zap, Shield, ArrowUpRight, BarChart3
} from 'lucide-react';

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { data: summary, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['reviewSummary'],
    queryFn: async () => {
      const res = await api.get('/api/review/summary/');
      return res.data;
    },
    // No auto-refresh — use the Refresh button to update manually
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['recentJobs'],
    queryFn: async () => {
      const res = await api.get('/api/ingestion/jobs/');
      return res.data.slice(0, 5); // display only last 5 jobs
    },
    // No auto-refresh — triggered by same Refresh button via queryClient.invalidateQueries
  });

  if (isLoading || jobsLoading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
          <p className="text-slate-400 text-sm">Loading ESG metrics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-red-400 font-semibold mb-2">Error loading dashboard data</p>
        <p className="text-slate-400 text-sm mb-4">{error.message}</p>
        <button 
          onClick={() => refetch()} 
          className="px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 hover:bg-slate-700 transition-all text-xs"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Calculate scope percentages for visual bars
  const s1 = summary?.scopes?.SCOPE_1 || 0;
  const s2 = summary?.scopes?.SCOPE_2 || 0;
  const s3 = summary?.scopes?.SCOPE_3 || 0;
  const totalScopes = s1 + s2 + s3 || 1;
  const s1Percent = (s1 / totalScopes) * 100;
  const s2Percent = (s2 / totalScopes) * 100;
  const s3Percent = (s3 / totalScopes) * 100;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Dashboard
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">Analyst oversight & ingestion platform metrics</p>
        </div>
        <button 
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['reviewSummary'] });
            queryClient.invalidateQueries({ queryKey: ['recentJobs'] });
          }}
          disabled={isFetching}
          className="inline-flex items-center gap-2 py-1.5 px-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800 active:scale-[0.98] transition-all text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-emerald-400' : ''}`} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Ingested */}
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/10 transition-all"></div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-slate-400 text-xs font-semibold tracking-wider uppercase">Ingested This Month</span>
            <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white">{summary?.total_this_month}</div>
          <div className="text-slate-500 text-xs mt-2 flex items-center gap-1">
            <span>Total rows loaded in current cycle</span>
          </div>
        </div>

        {/* Pending Review */}
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl group-hover:bg-amber-500/10 transition-all"></div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-slate-400 text-xs font-semibold tracking-wider uppercase">Pending Review</span>
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white flex items-center gap-2">
            <span>{summary?.pending_review}</span>
            {summary?.pending_review > 0 && (
              <span className="text-xs font-bold py-0.5 px-2 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400">
                Action Required
              </span>
            )}
          </div>
          <div className="text-slate-500 text-xs mt-2">Awaiting analyst action</div>
        </div>

        {/* Flagged */}
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/5 rounded-full blur-2xl group-hover:bg-red-500/10 transition-all"></div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-slate-400 text-xs font-semibold tracking-wider uppercase">Flagged Rows</span>
            <div className="p-2 bg-red-500/10 text-red-400 rounded-lg">
              <AlertOctagon className="w-5 h-5" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white flex items-center gap-2">
            <span>{summary?.flagged}</span>
            {summary?.flagged > 0 && (
              <span className="text-xs font-bold py-0.5 px-2 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 animate-pulse">
                Needs Attention
              </span>
            )}
          </div>
          <div className="text-slate-500 text-xs mt-2">Auto-flagged validation warnings</div>
        </div>

        {/* Approved */}
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-teal-500/5 rounded-full blur-2xl group-hover:bg-teal-500/10 transition-all"></div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-slate-400 text-xs font-semibold tracking-wider uppercase">Approved Rows</span>
            <div className="p-2 bg-teal-500/10 text-teal-400 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white">{summary?.approved}</div>
          <div className="text-slate-500 text-xs mt-2">Locked for audit on export</div>
        </div>
      </div>

      {/* Main Grid: Scope Breakdown & Recent Ingestion Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scope Breakdown */}
        <div className="glass-card p-6 rounded-2xl lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-6">
              <BarChart3 className="w-5 h-5 text-emerald-400" />
              <h2 className="text-md font-bold text-white">Greenhouse Gas Scopes</h2>
            </div>

            <div className="space-y-5">
              {/* Scope 1 */}
              <div>
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="font-medium text-slate-300">Scope 1 (Direct Fuel)</span>
                  <span className="font-bold text-white">{s1} rows ({Math.round(s1Percent)}%)</span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${s1Percent}%` }}></div>
                </div>
              </div>

              {/* Scope 2 */}
              <div>
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="font-medium text-slate-300">Scope 2 (Electricity)</span>
                  <span className="font-bold text-white">{s2} rows ({Math.round(s2Percent)}%)</span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div className="h-full bg-teal-400 rounded-full transition-all duration-500" style={{ width: `${s2Percent}%` }}></div>
                </div>
              </div>

              {/* Scope 3 */}
              <div>
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="font-medium text-slate-300">Scope 3 (Procurement & Travel)</span>
                  <span className="font-bold text-white">{s3} rows ({Math.round(s3Percent)}%)</span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div className="h-full bg-purple-400 rounded-full transition-all duration-500" style={{ width: `${s3Percent}%` }}></div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-slate-800 text-slate-400 text-xs flex justify-between">
            <span>Emission Protocol</span>
            <span className="font-medium text-slate-300">DEFRA / EPA Standard</span>
          </div>
        </div>

        {/* Recent Ingestion Jobs */}
        <div className="glass-card p-6 rounded-2xl lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" />
              <h2 className="text-md font-bold text-white">Recent Ingestion Jobs</h2>
            </div>
            <span className="text-slate-400 text-xs">Last 5 jobs</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-semibold">
                  <th className="py-2.5">Job ID</th>
                  <th className="py-2.5">Source Type</th>
                  <th className="py-2.5">Status</th>
                  <th className="py-2.5">Rows Ingested</th>
                  <th className="py-2.5">Flagged Errors</th>
                  <th className="py-2.5">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/50">
                {jobs && jobs.length > 0 ? (
                  jobs.map((job) => {
                    let statusColor = 'bg-slate-500/10 text-slate-400 border-slate-500/20';
                    if (job.status === 'COMPLETED') statusColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
                    if (job.status === 'PROCESSING') statusColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse';
                    if (job.status === 'FAILED') statusColor = 'bg-red-500/10 text-red-400 border-red-500/20';

                    return (
                      <tr key={job.id} className="text-slate-300 hover:bg-slate-900/20 transition-colors">
                        <td className="py-3.5 font-mono text-slate-400">#{job.id}</td>
                        <td className="py-3.5 font-medium">{job.data_source_display}</td>
                        <td className="py-3.5">
                          <span className={`inline-flex py-0.5 px-2 rounded-full text-[10px] font-bold border ${statusColor}`}>
                            {job.status}
                          </span>
                        </td>
                        <td className="py-3.5 font-semibold text-slate-200">{job.row_count} rows</td>
                        <td className="py-3.5 text-slate-200">
                          {job.error_count > 0 ? (
                            <span className="text-red-400 font-bold">{job.error_count} flags</span>
                          ) : (
                            <span className="text-slate-500">0</span>
                          )}
                        </td>
                        <td className="py-3.5 text-slate-500">
                          {new Date(job.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">
                      No ingestion jobs executed yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
