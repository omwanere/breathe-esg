import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { 
  FileSpreadsheet, ShieldAlert, Download, Lock, CheckCircle, 
  HelpCircle, RefreshCw, AlertTriangle
} from 'lucide-react';

export default function Export() {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  // Fetch approved counts and locked counts
  const { data: counts, isLoading, error, refetch } = useQuery({
    queryKey: ['exportCounts'],
    queryFn: async () => {
      const res = await api.get('/api/review/summary/');
      // We will also get the total locked count. Since the summary API doesn't separate locked, 
      // let's fetch raw activity rows list with a quick parameter, or assume summary gives counts.
      // Wait, we can fetch paginated list with is_locked check or just query review summary.
      return res.data;
    }
  });

  const { data: lockedData } = useQuery({
    queryKey: ['lockedRowsCount'],
    queryFn: async () => {
      const res = await api.get('/api/review/rows/', { params: { page_size: 1 } });
      // Total count from paginated results is returned in res.data.count
      return res.data;
    }
  });

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);

    try {
      const response = await api.get('/api/export/audit-ready/', {
        responseType: 'blob',
      });

      // Create a local blob URL and trigger browser download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;

      const timestamp = new Date().toISOString().replace(/[-:T]/g, '_').substring(0, 15);
      link.setAttribute('download', `breathe_esg_audit_export_${timestamp}.csv`);
      document.body.appendChild(link);
      link.click();

      // Clean up link
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);

      // Refresh counts
      refetch();
    } catch (err) {
      console.error(err);
      setExportError('Export failed. Ensure there are APPROVED and unlocked rows available in the system.');
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
          <p className="text-slate-400 text-sm">Loading audit export counts...</p>
        </div>
      </div>
    );
  }

  const approvedCount = counts?.approved || 0;

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          Audit Export Staging
        </h1>
        <p className="text-slate-400 text-sm mt-0.5">Export approved transactions to static immutable files for external validation</p>
      </div>

      {exportError && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Export Warning</p>
            <p className="text-xs opacity-90">{exportError}</p>
          </div>
        </div>
      )}

      {/* Main card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-card p-6 rounded-2xl border border-slate-800 lg:col-span-2 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
              <h2 className="text-md font-bold text-white font-sans">Prepare Export Bundle</h2>
            </div>
            
            <p className="text-slate-300 text-xs leading-relaxed">
              Exporting for audit extracts all <strong>APPROVED</strong> rows, converts their values to a unified audit CSV template, and marks the rows as locked.
            </p>

            <div className="p-4 bg-slate-950/50 border border-slate-800 rounded-xl flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5 animate-pulse" />
              <div>
                <p className="text-xs font-bold text-amber-400">Locking Policy Enforcement</p>
                <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
                  Upon clicking export, matching records are permanently locked (<code>is_locked = True</code>). Any subsequent changes will require administrative overrides and will generate explicit warnings in the compliance history.
                </p>
              </div>
            </div>

            <div className="p-3 bg-amber-500/5 border border-amber-500/15 rounded-xl text-[11px] text-amber-300 leading-relaxed">
              ⚠️ <strong>Important:</strong> When you click "Export for Audit &amp; Lock", all approved rows will be downloaded as a CSV file <strong>and permanently locked</strong>. Locked rows cannot be edited, re-approved, or changed. Only export when you are certain the data is ready for your auditor.
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-900">
            <div className="text-left">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Approved Staging Rows</span>
              <span className="text-2xl font-bold text-white">{approvedCount} ready for export</span>
            </div>

            <button
              onClick={handleExport}
              disabled={approvedCount === 0 || exporting}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 py-3 px-6 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-800 disabled:text-slate-500 disabled:opacity-40 text-slate-950 font-bold rounded-xl shadow-lg hover:shadow-emerald-500/10 active:scale-[0.98] transition-all text-xs shrink-0"
            >
              {exporting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Generating Audit File...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Export for Audit & Lock
                </>
              )}
            </button>
          </div>
        </div>

        {/* Audit Stats Panel */}
        <div className="glass-card p-6 rounded-2xl border border-slate-800 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Lock className="w-5 h-5 text-emerald-400" />
              <h2 className="text-md font-bold text-white">Audit Trail Statistics</h2>
            </div>

            <div className="space-y-4 pt-2">
              <div className="p-3.5 bg-slate-950/20 border border-slate-900 rounded-xl flex items-center justify-between">
                <span className="text-xs text-slate-400">Total Database Rows</span>
                <span className="text-sm font-bold text-white font-mono">{lockedData?.count || 0}</span>
              </div>

              <div className="p-3.5 bg-slate-950/20 border border-slate-900 rounded-xl flex items-center justify-between">
                <span className="text-xs text-slate-400">Status Ready (Staging)</span>
                <span className="text-sm font-bold text-emerald-400 font-mono">{approvedCount}</span>
              </div>
            </div>
          </div>

          <div className="text-[10px] text-slate-500 flex items-center gap-1.5 justify-center py-1">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
            <span>Platform conforms to ISO 14064 criteria</span>
          </div>
        </div>
      </div>
    </div>
  );
}
