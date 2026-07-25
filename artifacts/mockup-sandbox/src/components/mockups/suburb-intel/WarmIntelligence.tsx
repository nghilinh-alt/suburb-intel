import React, { useState } from 'react';
import { Search, BarChart2, TrendingUp, TrendingDown, Minus, MapPin, Building2, Map } from 'lucide-react';

const Suburbs = [
  { rank: 1, name: "South Yarra", state: "VIC", code: "206041122", distance: "3.2km", trend: "Accelerating", type: "Hot", score: 87.4 },
  { rank: 2, name: "Fortitude Valley", state: "QLD", code: "305031104", distance: "1.8km", trend: "Accelerating", type: "Growth play", score: 84.1 },
  { rank: 3, name: "Newstead", state: "QLD", code: "305021108", distance: "2.4km", trend: "Steady", type: "Hot", score: 81.9 },
  { rank: 4, name: "Fitzroy", state: "VIC", code: "206031108", distance: "2.9km", trend: "Accelerating", type: "Growth play", score: 79.3 },
  { rank: 5, name: "West End", state: "QLD", code: "305011101", distance: "1.6km", trend: "Steady", type: "Cash-flow play", score: 76.8 },
  { rank: 6, name: "Surry Hills", state: "NSW", code: "117021338", distance: "2.1km", trend: "Cooling", type: "Growth play", score: 74.5 },
  { rank: 7, name: "Collingwood", state: "VIC", code: "206031112", distance: "3.4km", trend: "Accelerating", type: "Hot", score: 72.1 },
  { rank: 8, name: "Paddington", state: "NSW", code: "117021333", distance: "3.7km", trend: "Steady", type: "Cash-flow play", score: 68.9 },
];

export function WarmIntelligence() {
  const [activeTab, setActiveTab] = useState("Momentum");
  const tabs = ["Momentum", "Supply Scarcity", "Investment", "Economic", "Demographic", "Liveability"];

  return (
    <div className="min-h-screen font-sans" style={{ backgroundColor: '#faf7f4', color: '#1e293b' }}>
      {/* Navigation */}
      <nav style={{ backgroundColor: '#fffdf9', borderColor: '#e8e0d8' }} className="border-b sticky top-0 z-10 shadow-sm shadow-[#e8e0d8]/30">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded flex items-center justify-center text-white" style={{ backgroundColor: '#059669' }}>
              <Building2 size={18} strokeWidth={2.5} />
            </div>
            <span className="font-['Playfair_Display',serif] text-xl font-bold tracking-wide" style={{ color: '#059669' }}>
              Suburb Intel
            </span>
          </div>
          <div className="flex items-center gap-8">
            <button className="text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium flex items-center gap-2">
              <Search size={16} /> Search
            </button>
            <button className="text-sm font-semibold flex items-center gap-2" style={{ color: '#059669' }}>
              <BarChart2 size={16} /> Rankings
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-10">
          <h1 className="font-['Playfair_Display',serif] text-4xl text-slate-800 mb-4 font-bold tracking-tight">Top Suburbs by Momentum</h1>
          <p className="text-slate-500 text-lg max-w-2xl font-light">
            Identifying locations with accelerating market conditions, constrained supply, and strong economic fundamentals.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-3 overflow-x-auto pb-4 mb-8 scrollbar-hide">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`whitespace-nowrap px-5 py-2.5 rounded-full text-sm font-medium transition-all ${
                activeTab === tab
                  ? 'text-white border-transparent shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 bg-transparent'
              }`}
              style={{
                backgroundColor: activeTab === tab ? '#059669' : 'transparent',
                borderColor: activeTab === tab ? 'transparent' : '#e8e0d8',
                borderWidth: activeTab === tab ? 0 : 1
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Rankings List */}
        <div className="space-y-4">
          {Suburbs.map((suburb) => (
            <div 
              key={suburb.rank}
              style={{ backgroundColor: '#fffdf9', borderColor: '#e8e0d8' }}
              className="border rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow flex items-center justify-between group cursor-pointer"
            >
              <div className="flex items-center gap-6">
                {/* Rank */}
                <div 
                  className={`font-['Playfair_Display',serif] text-3xl font-semibold w-12 text-center ${suburb.rank === 1 ? 'text-[#d97706]' : 'text-slate-400'}`}
                >
                  #{suburb.rank}
                </div>
                
                {/* Info */}
                <div>
                  <div className="flex items-baseline gap-3 mb-1.5">
                    <h3 className="text-xl font-bold text-slate-800 tracking-tight">{suburb.name}</h3>
                    <span className="text-sm font-semibold text-slate-500">{suburb.state}</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-slate-500 mb-3.5">
                    <span className="flex items-center gap-1.5"><Map size={14} className="text-slate-400" /> {suburb.code}</span>
                    <span className="text-slate-300">&bull;</span>
                    <span className="flex items-center gap-1.5"><MapPin size={14} className="text-slate-400" /> {suburb.distance} to CBD</span>
                  </div>
                  
                  {/* Badges */}
                  <div className="flex items-center gap-2">
                    {/* Trend Badge */}
                    <span 
                      className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold border"
                      style={{
                        backgroundColor: suburb.trend === 'Accelerating' ? '#ecfdf5' : suburb.trend === 'Cooling' ? '#f8fafc' : '#f8fafc',
                        color: suburb.trend === 'Accelerating' ? '#059669' : suburb.trend === 'Cooling' ? '#64748b' : '#475569',
                        borderColor: suburb.trend === 'Accelerating' ? '#a7f3d0' : suburb.trend === 'Cooling' ? '#e2e8f0' : '#e2e8f0'
                      }}
                    >
                      {suburb.trend === 'Accelerating' && <TrendingUp size={14} />}
                      {suburb.trend === 'Steady' && <Minus size={14} />}
                      {suburb.trend === 'Cooling' && <TrendingDown size={14} />}
                      {suburb.trend}
                    </span>
                    
                    {/* Type Badge */}
                    <span 
                      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border"
                      style={{
                        backgroundColor: suburb.type === 'Hot' ? '#fffbeb' : suburb.type === 'Growth play' ? '#f0fdf4' : '#f8fafc',
                        color: suburb.type === 'Hot' ? '#d97706' : suburb.type === 'Growth play' ? '#15803d' : '#475569',
                        borderColor: suburb.type === 'Hot' ? '#fde68a' : suburb.type === 'Growth play' ? '#bbf7d0' : '#e2e8f0'
                      }}
                    >
                      {suburb.type}
                    </span>
                  </div>
                </div>
              </div>
              
              {/* Score */}
              <div className="text-right flex flex-col items-end justify-center pr-2">
                <div className="text-4xl font-bold tracking-tight mb-1" style={{ color: '#059669' }}>
                  {suburb.score}
                </div>
                <div className="text-[11px] uppercase tracking-widest font-bold text-slate-400">
                  Momentum
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
