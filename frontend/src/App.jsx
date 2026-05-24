import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import Upload from './components/Upload';
import Review from './components/Review';
import Export from './components/Export';
import { 
  BarChart3, UploadCloud, Layers, Download, LogOut, 
  User as UserIcon, Shield, Menu, X 
} from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1
    }
  }
});

function MainApp() {
  const [user, setUser] = useState(null);
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Load user from localStorage on startup
  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    const token = localStorage.getItem('token');
    if (savedUser && token) {
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const handleLoginSuccess = (loggedInUser) => {
    setUser(loggedInUser);
    setCurrentTab('dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    setUser(null);
  };

  if (!user) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'upload':
        return <Upload />;
      case 'review':
        return <Review />;
      case 'export':
        return <Export />;
      default:
        return <Dashboard />;
    }
  };

  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'upload', label: 'Ingest Data', icon: UploadCloud },
    { id: 'review', label: 'Review Rows', icon: Layers },
    { id: 'export', label: 'Audit Export', icon: Download },
  ];

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col relative text-slate-100 font-sans">
      {/* Background glow animations */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/5 rounded-full blur-[160px] pointer-events-none animate-pulse-slow"></div>
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-teal-500/5 rounded-full blur-[160px] pointer-events-none animate-pulse-slow"></div>

      {/* Top Navbar */}
      <header className="h-16 border-b border-slate-900 glass-panel sticky top-0 z-30">
        <div className="max-w-[90rem] mx-auto w-full h-full flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white md:hidden transition-colors"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg">
                <Shield className="w-5 h-5" />
              </div>
              <span className="font-bold tracking-tight text-white">Breathe ESG</span>
            </div>
          </div>

          {/* User profile details */}
          <div className="flex items-center gap-4 text-xs">
            <div className="hidden sm:flex flex-col items-end">
              <span className="font-semibold text-slate-200">{user.username}</span>
              <span className="text-[10px] text-emerald-400 font-bold tracking-wide uppercase mt-0.5">{user.tenant?.name || 'Demo Tenant'}</span>
            </div>
            
            <button 
              onClick={handleLogout}
              className="p-2 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 text-slate-400 hover:text-red-400 rounded-xl transition-all cursor-pointer"
              title="Sign Out"
            >
              <LogOut className="w-4.5 h-4.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Layout wrapper */}
      <div className="max-w-[90rem] mx-auto w-full flex flex-1 relative">
        {/* Mobile Sidebar Backdrop */}
        {sidebarOpen && (
          <div 
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          ></div>
        )}

        {/* Sidebar Navigation */}
        <aside className={`w-64 border-r border-slate-900 bg-slate-950/80 backdrop-blur-md p-4 space-y-2 flex flex-col justify-between absolute md:static top-0 bottom-0 left-0 z-40 transition-transform duration-300 md:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <div className="space-y-1.5">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setCurrentTab(item.id);
                    setSidebarOpen(false);
                  }}
                  className={`w-full flex items-center gap-3 px-4.5 py-3 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                    isActive 
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                  }`}
                >
                  <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="p-3 bg-slate-900/40 border border-slate-900 rounded-xl flex items-center gap-3 text-xs text-slate-400 md:hidden">
            <UserIcon className="w-5 h-5 text-emerald-400" />
            <div className="overflow-hidden">
              <p className="font-semibold text-slate-200 truncate">{user.username}</p>
              <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider truncate">{user.tenant?.name}</p>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto w-full">
          {renderContent()}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MainApp />
    </QueryClientProvider>
  );
}
