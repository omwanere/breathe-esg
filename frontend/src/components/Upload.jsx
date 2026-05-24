import React, { useState, useEffect } from 'react';
import api from '../api';
import { 
  UploadCloud, FileText, CheckCircle2, XCircle, 
  AlertTriangle, RefreshCw, Info, HelpCircle 
} from 'lucide-react';

export default function Upload() {
  const [activeUploads, setActiveUploads] = useState({}); // job_id -> job details
  const [files, setFiles] = useState({ sap: null, utility: null, travel: null });
  const [errorMsgs, setErrorMsgs] = useState({ sap: null, utility: null, travel: null });
  const [loading, setLoading] = useState({ sap: false, utility: false, travel: false });

  // Handle file selection
  const handleFileChange = (source, file) => {
    setFiles(prev => ({ ...prev, [source]: file }));
    setErrorMsgs(prev => ({ ...prev, [source]: null }));
  };

  // Submit file upload
  const handleUploadSubmit = async (source, endpoint) => {
    const file = files[source];
    if (!file) {
      setErrorMsgs(prev => ({ ...prev, [source]: 'Please select a file first.' }));
      return;
    }

    setLoading(prev => ({ ...prev, [source]: true }));
    setErrorMsgs(prev => ({ ...prev, [source]: null }));

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const jobData = response.data;
      
      // Save job in activeUploads to begin polling
      setActiveUploads(prev => ({
        ...prev,
        [jobData.id]: {
          id: jobData.id,
          source,
          status: jobData.status,
          row_count: 0,
          error_count: 0,
          error_log: [],
          filename: file.name
        }
      }));

      // Reset file input
      setFiles(prev => ({ ...prev, [source]: null }));
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail || err.response?.data?.error || 'Upload failed. Please try again.';
      setErrorMsgs(prev => ({ ...prev, [source]: detail }));
    } finally {
      setLoading(prev => ({ ...prev, [source]: false }));
    }
  };

  // Poll active uploads every 2 seconds
  useEffect(() => {
    const activeJobIds = Object.keys(activeUploads).filter(
      id => activeUploads[id].status === 'PENDING' || activeUploads[id].status === 'PROCESSING'
    );

    if (activeJobIds.length === 0) return;

    const interval = setInterval(() => {
      activeJobIds.forEach(async (jobId) => {
        try {
          const res = await api.get(`/api/ingestion/jobs/${jobId}/`);
          const job = res.data;
          
          setActiveUploads(prev => ({
            ...prev,
            [jobId]: {
              ...prev[jobId],
              status: job.status,
              row_count: job.row_count,
              error_count: job.error_count,
              error_log: job.error_log
            }
          }));
        } catch (err) {
          console.error('Error polling job status:', err);
        }
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [activeUploads]);

  // Render format panel utility
  const renderUploadCard = (source, label, hint, endpoint, accept = ".csv") => {
    const file = files[source];
    const isUploading = loading[source];
    const errorMsg = errorMsgs[source];

    return (
      <div className="glass-card p-6 rounded-2xl flex flex-col justify-between border border-slate-800">
        <div>
          <h3 className="text-md font-bold text-white mb-1.5">{label}</h3>
          <p className="text-slate-400 text-xs mb-4 flex items-center gap-1">
            <Info className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
            <span>Format: {hint}</span>
          </p>

          {/* Drag & Drop simulated area */}
          <div className="border border-dashed border-slate-700 hover:border-emerald-500/50 bg-slate-950/40 rounded-xl p-6 text-center transition-colors cursor-pointer relative group">
            <input
              type="file"
              accept={accept}
              onChange={(e) => handleFileChange(source, e.target.files[0])}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center gap-2">
              <UploadCloud className="w-8 h-8 text-slate-500 group-hover:text-emerald-400 transition-colors" />
              <span className="text-xs font-semibold text-slate-300">
                {file ? file.name : 'Choose file or drag & drop'}
              </span>
              <span className="text-[10px] text-slate-500">
                Maximum size 10MB ({accept})
              </span>
            </div>
          </div>

          {errorMsg && (
            <p className="mt-3 text-xs text-red-400 bg-red-500/10 border border-red-500/15 py-2 px-3 rounded-lg flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {errorMsg}
            </p>
          )}
        </div>

        <button
          onClick={() => handleUploadSubmit(source, endpoint)}
          disabled={!file || isUploading}
          className="mt-6 w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-800 disabled:text-slate-500 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition-all text-xs active:scale-[0.98]"
        >
          {isUploading ? 'Uploading...' : 'Ingest File'}
        </button>
      </div>
    );
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          Ingest Activity Data
        </h1>
        <p className="text-slate-400 text-sm mt-0.5">Upload carbon emissions transaction records to normalized staging tables</p>
      </div>

      {/* Upload panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {renderUploadCard(
          'sap', 
          'SAP Goods Issues (MB51)', 
          'MB51 movement export (CSV/XLSX), German format', 
          '/api/ingestion/upload/sap/',
          '.csv,.xlsx'
        )}
        {renderUploadCard(
          'utility', 
          'Utility Bills (EDF/PG&E)', 
          'Electric meter bill portal export (CSV)', 
          '/api/ingestion/upload/utility/',
          '.csv'
        )}
        {renderUploadCard(
          'travel', 
          'Corporate Travel (Concur)', 
          'Detail travel expense report export (CSV)', 
          '/api/ingestion/upload/travel/',
          '.csv'
        )}
      </div>

      {/* Ingestion status monitor */}
      {Object.keys(activeUploads).length > 0 && (
        <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-md font-bold text-white">Ingestion Job Status Monitor</h2>
          <div className="space-y-3.5">
            {Object.values(activeUploads).map((job) => {
              const isFinished = job.status === 'COMPLETED' || job.status === 'FAILED';
              let borderStyle = 'border-slate-800 bg-slate-950/30';
              if (job.status === 'COMPLETED') borderStyle = 'border-emerald-500/20 bg-emerald-500/5';
              if (job.status === 'FAILED') borderStyle = 'border-red-500/20 bg-red-500/5';

              return (
                <div 
                  key={job.id} 
                  className={`border rounded-xl p-4 transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 ${borderStyle}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {job.status === 'PENDING' || job.status === 'PROCESSING' ? (
                        <RefreshCw className="w-5 h-5 text-amber-400 animate-spin" />
                      ) : job.status === 'COMPLETED' ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-slate-500">Job #{job.id}</span>
                        <span className="text-xs font-bold text-slate-200 capitalize">{job.source} Pipeline</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5 font-medium">{job.filename}</p>
                      
                      {isFinished && job.status === 'COMPLETED' && (
                        <div className="mt-2 text-[11px] text-slate-400 flex items-center gap-3">
                          <span className="flex items-center gap-1 font-semibold text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Ingested {job.row_count} rows
                          </span>
                          {job.error_count > 0 && (
                            <span className="flex items-center gap-1 font-semibold text-red-400">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              Auto-flagged {job.error_count} warnings
                            </span>
                          )}
                        </div>
                      )}
                      
                      {isFinished && job.status === 'FAILED' && (
                        <p className="mt-2 text-[11px] text-red-400 font-medium">
                          Failed: {job.error_log[0]?.error || 'Unknown parsing error occurred'}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                    <span className={`text-[10px] font-bold py-1 px-2.5 rounded-full uppercase border ${
                      job.status === 'COMPLETED' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' :
                      job.status === 'FAILED' ? 'border-red-500/30 text-red-400 bg-red-500/10' :
                      'border-amber-500/30 text-amber-400 bg-amber-500/10 animate-pulse'
                    }`}>
                      {job.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
