import React from 'react';
import { Search, ChevronDown, User, Bell, TrendingUp, ArrowRight, TrendingDown, MapPin } from 'lucide-react';

const SUBURBS = [
  { rank: 1, name: "South Yarra", state: "VIC", code: "206041122", distance: "3.2km", momentum: "Accelerating", momentumTrend: "up", type: "Hot", score: 87.4 },
  { rank: 2, name: "Fortitude Valley", state: "QLD", code: "305031104", distance: "1.8km", momentum: "Accelerating", momentumTrend: "up", type: "Growth play", score: 84.1 },
  { rank: 3, name: "Newstead", state: "QLD", code: "305021108", distance: "2.4km", momentum: "Steady", momentumTrend: "flat", type: "Hot", score: 81.9 },
  { rank: 4, name: "Fitzroy", state: "VIC", code: "206031108", distance: "2.9km", momentum: "Accelerating", momentumTrend: "up", type: "Growth play", score: 79.3 },
  { rank: 5, name: "West End", state: "QLD", code: "305011101", distance: "1.6km", momentum: "Steady", momentumTrend: "flat", type: "Cash-flow play", score: 76.8 },
  { rank: 6, name: "Surry Hills", state: "NSW", code: "117021338", distance: "2.1km", momentum: "Cooling", momentumTrend: "down", type: "Growth play", score: 74.5 },
  { rank: 7, name: "Collingwood", state: "VIC", code: "206031112", distance: "3.4km", momentum: "Accelerating", momentumTrend: "up", type: "Hot", score: 72.1 },
  { rank: 8, name: "Paddington", state: "NSW", code: "117021333", distance: "3.7km", momentum: "Steady", momentumTrend: "flat", type: "Cash-flow play", score: 68.9 },
];

export function CleanPlatform() {
  return (
    <div className="min-h-screen bg-[#f8fafc] font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      {/* Top Nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6 md:gap-8">
            <div className="flex items-center gap-2 cursor-pointer">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-sm">
                <MapPin className="w-4 h-4 text-white" />
              </div>
              <span className="font-semibold text-lg tracking-tight text-slate-900">SuburbIntel</span>
            </div>
            
            <nav className="hidden md:flex items-center gap-1">
              <a href="#" className="px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-md hover:bg-slate-50 transition-colors">Search</a>
              <a href="#" className="px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-md">Rankings</a>
              <a href="#" className="px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-md hover:bg-slate-50 transition-colors">Portfolios</a>
            </nav>
          </div>

          <div className="flex items-center gap-3 md:gap-4">
            <button className="text-slate-400 hover:text-slate-600 p-2 rounded-full hover:bg-slate-50 transition-colors">
              <Search className="w-5 h-5" />
            </button>
            <button className="text-slate-400 hover:text-slate-600 p-2 rounded-full hover:bg-slate-50 transition-colors relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full border-2 border-white"></span>
            </button>
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center ml-1 border border-indigo-200 cursor-pointer hover:border-indigo-300 transition-colors">
              <span className="text-xs font-medium text-indigo-700">JD</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 md:px-6 py-6 md:py-8">
        
        {/* Header & Tabs */}
        <div className="mb-6 md:mb-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">Top Suburbs by Momentum</h1>
              <p className="text-sm text-slate-500">Ranking 1,429 Australian suburbs by short-term growth indicators.</p>
            </div>
            
            <button className="flex items-center gap-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg px-3 py-2 shadow-sm hover:bg-slate-50 transition-colors">
              Filter Results
              <ChevronDown className="w-4 h-4 text-slate-400" />
            </button>
          </div>
          
          <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4 md:mx-0 md:px-0">
            {["Momentum", "Supply Scarcity", "Investment", "Economic", "Demographic", "Liveability"].map((tab, i) => (
              <button 
                key={tab}
                className={`whitespace-nowrap px-4 py-2 text-sm font-medium rounded-full transition-colors ${
                  i === 0 
                    ? "bg-indigo-600 text-white shadow-sm ring-1 ring-indigo-600" 
                    : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200 shadow-sm"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="space-y-3">
          {SUBURBS.map((suburb) => (
            <div 
              key={suburb.rank}
              className="bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200 flex flex-col md:flex-row md:items-center gap-4 md:gap-6 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
            >
              <div className="flex items-start md:items-center gap-4 md:gap-5 flex-1">
                <div className="w-6 text-sm font-semibold text-slate-400 pt-0.5 md:pt-0">
                  #{suburb.rank}
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-base md:text-lg font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors leading-tight">
                      {suburb.name}
                    </h2>
                    <span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded uppercase tracking-wider">{suburb.state}</span>
                  </div>
                  <div className="text-sm text-slate-500 flex items-center gap-1.5">
                    <span className="font-mono text-xs text-slate-400">{suburb.code}</span>
                    <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                    <span>{suburb.distance} to CBD</span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap md:flex-nowrap items-center gap-2 md:gap-3 pl-10 md:pl-0">
                {/* Badges */}
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                  suburb.momentumTrend === 'up' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' :
                  suburb.momentumTrend === 'down' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  'bg-slate-50 text-slate-600 border-slate-200'
                }`}>
                  {suburb.momentumTrend === 'up' && <TrendingUp className="w-3.5 h-3.5" />}
                  {suburb.momentumTrend === 'down' && <TrendingDown className="w-3.5 h-3.5" />}
                  {suburb.momentumTrend === 'flat' && <ArrowRight className="w-3.5 h-3.5" />}
                  {suburb.momentum}
                </div>

                <div className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                  suburb.type === 'Hot' ? 'bg-rose-50 text-rose-700 border-rose-100' :
                  suburb.type === 'Growth play' ? 'bg-blue-50 text-blue-700 border-blue-100' :
                  'bg-violet-50 text-violet-700 border-violet-100'
                }`}>
                  {suburb.type}
                </div>
              </div>

              <div className="hidden md:block w-px h-12 bg-slate-100 mx-2"></div>

              <div className="flex flex-row md:flex-col items-center md:items-end justify-between md:justify-center pl-10 md:pl-0 min-w-[90px] border-t border-slate-100 md:border-t-0 pt-3 md:pt-0 mt-1 md:mt-0">
                <div className="text-[10px] uppercase font-bold tracking-widest text-slate-400 md:hidden">
                  Score
                </div>
                <div className="flex flex-col items-end">
                  <div className="text-2xl md:text-[26px] font-bold text-indigo-600 tracking-tight leading-none mb-1">
                    {suburb.score.toFixed(1)}
                  </div>
                  <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 hidden md:block">
                    Momentum
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-8 flex justify-center pb-12">
          <button className="px-5 py-2.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50 hover:text-slate-900 transition-colors">
            Load More Suburbs
          </button>
        </div>

      </main>
    </div>
  );
}
