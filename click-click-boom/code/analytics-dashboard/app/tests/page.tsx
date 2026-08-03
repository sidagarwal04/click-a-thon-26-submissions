import { Activity } from 'lucide-react';

export default function TestsPage() {
  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Test Runs</h1>
          <p className="mt-1 text-sm text-zinc-400">Track test execution results for schema proposals</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-12 text-center">
          <Activity className="h-10 w-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400">Test run history will appear here</p>
          <p className="text-sm text-zinc-500 mt-1">Connect to ClickHouse to view test results</p>
        </div>
      </div>
    </div>
  );
}
