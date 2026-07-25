import React from 'react';
import { Terminal, Search, Database } from 'lucide-react';

export function DarkTerminal() {
  const data = [
    { 
      rank: 1, name: "South Yarra", state: "VIC", sa2: "206041122", distance: "3.2km", 
      momentum: "Accelerating", type: "Hot", score: 87.4, trend: "▲", 
      momentumColor: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10 shadow-[0_0_10px_rgba(6,182,212,0.2)]", 
      typeColor: "text-rose-400 border-rose-400/30 bg-rose-400/10" 
    },
    { 
      rank: 2, name: "Fortitude Valley", state: "QLD", sa2: "305031104", distance: "1.8km", 
      momentum: "Accelerating", type: "Growth play", score: 84.1, trend: "▲", 
      momentumColor: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10 shadow-[0_0_10px_rgba(6,182,212,0.2)]", 
      typeColor: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10" 
    },
    { 
      rank: 3, name: "Newstead", state: "QLD", sa2: "305021108", distance: "2.4km", 
      momentum: "Steady", type: "Hot", score: 81.9, trend: "→", 
      momentumColor: "text-slate-300 border-slate-600 bg-slate-800/80", 
      typeColor: "text-rose-400 border-rose-400/30 bg-rose-400/10" 
    },
    { 
      rank: 4, name: "Fitzroy", state: "VIC", sa2: "206031108", distance: "2.9km", 
      momentum: "Accelerating", type: "Growth play", score: 79.3, trend: "▲", 
      momentumColor: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10 shadow-[0_0_10px_rgba(6,182,212,0.2)]", 
      typeColor: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10" 
    },
    { 
      rank: 5, name: "West End", state: "QLD", sa2: "305011101", distance: "1.6km", 
      momentum: "Steady", type: "Cash-flow play", score: 76.8, trend: "→", 
      momentumColor: "text-slate-300 border-slate-600 bg-slate-800/80", 
      typeColor: "text-indigo-400 border-indigo-400/30 bg-indigo-400/10" 
    },
    { 
      rank: 6, name: "Surry Hills", state: "NSW", sa2: "117021338", distance: "2.1km", 
      momentum: "Cooling", type: "Growth play", score: 74.5, trend: "▼", 
      momentumColor: "text-orange-400 border-orange-400/30 bg-orange-400/10", 
      typeColor: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10" 
    },
    { 
      rank: 7, name: "Collingwood", state: "VIC", sa2: "206031112", distance: "3.4km", 
      momentum: "Accelerating", type: "Hot", score: 72.1, trend: "▲", 
      momentumColor: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10 shadow-[0_0_10px_rgba(6,182,212,0.2)]", 
      typeColor: "text-rose-400 border-rose-400/30 bg-rose-400/10" 
    },
    { 
      rank: 8, name: "Paddington", state: "NSW", sa2: "117021333", distance: "3.7km", 
      momentum: "Steady", type: "Cash-flow play", score: 68.9, trend: "→", 
      momentumColor: "text-slate-300 border-slate-600 bg-slate-800/80", 
      typeColor: "text-indigo-400 border-indigo-400/30 bg-indigo-400/10" 
    },
  ];

  const tabs = [
    { name: "MOMENTUM", active: true },
    { name: "SUPPLY SCARCITY", active: false },
    { name: "INVESTMENT", active: false },
    { name: "ECONOMIC", active: false },
    { name: "DEMOGRAPHIC", active: false },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300 font-sans selection:bg-cyan-500/30 pb-16 overflow-x-hidden">
      {/* Background Grid Pattern for terminal feel */}
      <div className="fixed inset-0 pointer-events-none z-0" 
           style={{ 
             backgroundImage: `linear-gradient(rgba(30, 41, 59, 0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(30, 41, 59, 0.3) 1px, transparent 1px)`, 
             backgroundSize: '40px 40px',
             maskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.2) 100%)',
             WebkitMaskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.2) 100%)'
           }} 
      />

      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2 text-cyan-400">
              <Terminal size={18} className="animate-pulse duration-2000" />
              <span className="font-mono font-bold tracking-tight text-sm">SUBURB_INTEL</span>
            </div>
            
            <nav className="flex items-center gap-2 mt-0.5">
              <button className="px-3 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors">
                <div className="flex items-center gap-2">
                  <Search size={14} />
                  <span>Search</span>
                </div>
              </button>
              <button className="px-3 h-14 border-b-[3px] border-cyan-400 text-sm font-medium text-cyan-400 bg-gradient-to-t from-cyan-400/10 to-transparent">
                <div className="flex items-center gap-2">
                  <Database size={14} />
                  <span>Rankings</span>
                </div>
              </button>
            </nav>
          </div>
          
          <div className="flex items-center gap-4 font-mono text-[10px] text-slate-500">
            <span className="flex items-center gap-1.5">SYS_STAT: <span className="text-emerald-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_5px_#34d399]"></span>ONLINE</span></span>
            <span>UPDATED: 08:42:15 UTC</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-10 relative z-10">
        <div className="flex items-end justify-between mb-8">
          <div>
            <h1 className="text-3xl font-light text-slate-100 tracking-tight mb-2">National Rankings</h1>
            <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
              <span className="px-2 py-0.5 rounded border border-slate-800 bg-slate-900/50">ALL_STATES</span>
              <span className="px-2 py-0.5 rounded border border-slate-800 bg-slate-900/50">TOP_100</span>
              <span className="text-cyan-500/70">LIVE_DATA_FEED_ACTIVE</span>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="px-3 py-1.5 text-xs font-mono border border-slate-700 rounded text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors">
              [ EXPORT_CSV ]
            </button>
            <button className="px-3 py-1.5 text-xs font-mono border border-cyan-500/50 bg-cyan-500/10 rounded text-cyan-400 hover:bg-cyan-500/20 hover:shadow-[0_0_15px_rgba(6,182,212,0.2)] transition-all">
              [ FILTER_OPTS ]
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide">
          {tabs.map((tab) => (
            <button
              key={tab.name}
              className={`px-4 py-2 text-xs font-mono tracking-wider rounded border transition-colors whitespace-nowrap ${
                tab.active
                  ? "border-cyan-400 bg-cyan-400/10 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.15)]"
                  : "border-slate-800 bg-slate-900/50 text-slate-500 hover:border-slate-700 hover:text-slate-300"
              }`}
            >
              {tab.name}
            </button>
          ))}
        </div>

        {/* Data List */}
        <div className="flex flex-col gap-1.5">
          {/* Header row */}
          <div className="flex items-center px-4 py-2 text-[10px] font-mono text-slate-500 border-b border-slate-800/80 mb-2 tracking-widest uppercase">
            <div className="w-12 text-right pr-4">RNK</div>
            <div className="flex-1 pl-4">Suburb_Identifier</div>
            <div className="w-[300px]">Market_Signals</div>
            <div className="w-32 text-right">Score_Idx</div>
          </div>

          {/* Rows */}
          {data.map((row) => (
            <div 
              key={row.rank}
              className="flex items-center p-3.5 border border-slate-800/60 bg-slate-900/40 rounded hover:bg-slate-800/60 hover:border-slate-700 transition-colors group relative overflow-hidden"
            >
              {/* Left active glow accent */}
              <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity shadow-[0_0_8px_#06b6d4]"></div>

              {/* Rank */}
              <div className="w-12 text-2xl font-mono text-slate-600 text-right pr-4 border-r border-slate-800/80 group-hover:text-slate-400 transition-colors">
                {String(row.rank).padStart(2, '0')}
              </div>

              {/* Suburb Info */}
              <div className="flex-1 pl-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-lg font-semibold text-slate-200 group-hover:text-white transition-colors">{row.name}</span>
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/50">
                    {row.state}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500">
                  <span className="text-slate-600">ID:</span>
                  <span className="text-slate-400">{row.sa2}</span>
                  <span className="text-slate-700">·</span>
                  <span className="text-slate-400">{row.distance} <span className="text-slate-600">to CBD</span></span>
                </div>
              </div>

              {/* Signals */}
              <div className="w-[300px] flex gap-2 justify-start items-center">
                <span className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider border rounded-md flex items-center gap-1.5 ${row.momentumColor}`}>
                  <span>{row.trend}</span>
                  {row.momentum}
                </span>
                <span className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider border rounded-md ${row.typeColor}`}>
                  {row.type}
                </span>
              </div>

              {/* Score */}
              <div className="w-32 text-right flex flex-col items-end justify-center group-hover:transform group-hover:-translate-x-1 transition-transform">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-mono font-medium text-cyan-400 tracking-tight drop-shadow-[0_0_8px_rgba(6,182,212,0.3)]">
                    {row.score.toFixed(1)}
                  </span>
                </div>
                <span className="text-[9px] font-mono text-slate-600 tracking-widest mt-0.5 group-hover:text-cyan-500/50 transition-colors">
                  IDX_MOMENTUM
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
