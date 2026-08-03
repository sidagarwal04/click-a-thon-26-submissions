import React from 'react';
import { FilterState } from '../../types';
import { Filter, RefreshCw } from 'lucide-react';

interface FilterBarProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  onReset: () => void;
}

const selectCls = "bg-white text-xs text-slate-700 border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 shadow-sm";

export const FilterBar: React.FC<FilterBarProps> = ({ filters, setFilters, onReset }) => {
  return (
    <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
        <Filter className="w-4 h-4 text-brand-500" />
        <span>Dimension Filters</span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Time Window */}
        <select
          value={filters.timeRange}
          onChange={(e) => setFilters((prev) => ({ ...prev, timeRange: e.target.value }))}
          className={selectCls}
        >
          <option value="last_24h">Last 24 Hours</option>
          <option value="last_7d">Last 7 Days</option>
          <option value="last_30d">Last 30 Days (Jun-Jul 2026)</option>
        </select>

        {/* App Category */}
        <select
          value={filters.appCategory}
          onChange={(e) => setFilters((prev) => ({ ...prev, appCategory: e.target.value }))}
          className={selectCls}
        >
          <option value="all">All Categories</option>
          <option value="gaming">Gaming &amp; Casual</option>
          <option value="social">Social &amp; Media</option>
          <option value="utilities">Utilities &amp; Tools</option>
        </select>

        {/* Region */}
        <select
          value={filters.region}
          onChange={(e) => setFilters((prev) => ({ ...prev, region: e.target.value }))}
          className={selectCls}
        >
          <option value="all">All Regions</option>
          <option value="us_east">US-East (Virginia)</option>
          <option value="us_west">US-West (California)</option>
          <option value="apac">APAC (India &amp; SEA)</option>
          <option value="eu">EU (Frankfurt)</option>
        </select>

        {/* Ad Format */}
        <select
          value={filters.adFormat}
          onChange={(e) => setFilters((prev) => ({ ...prev, adFormat: e.target.value }))}
          className={selectCls}
        >
          <option value="all">All Ad Formats</option>
          <option value="rewarded_video">Rewarded Video</option>
          <option value="interstitial">Interstitial</option>
          <option value="banner">Banner</option>
          <option value="native">Native</option>
        </select>

        {/* Device OS */}
        <select
          value={filters.deviceModel}
          onChange={(e) => setFilters((prev) => ({ ...prev, deviceModel: e.target.value }))}
          className={selectCls}
        >
          <option value="all">All OS / Devices</option>
          <option value="ios_17">iOS (17.5)</option>
          <option value="android_14">Android (14)</option>
        </select>

        <button
          onClick={onReset}
          className="p-2 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-400 hover:text-slate-700 transition-colors shadow-sm"
          title="Reset Filters"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
