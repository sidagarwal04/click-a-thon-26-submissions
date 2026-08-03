import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return 'just now';
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;
  return formatDate(dateString);
}

export function getConfidenceColor(score: number): string {
  if (score >= 0.8) return 'text-green-500';
  if (score >= 0.6) return 'text-yellow-500';
  return 'text-red-500';
}

export function getConfidenceBgColor(score: number): string {
  if (score >= 0.8) return 'bg-green-500/10 border-green-500/20';
  if (score >= 0.6) return 'bg-yellow-500/10 border-yellow-500/20';
  return 'bg-red-500/10 border-red-500/20';
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-red-600 bg-red-500/10';
    case 'high': return 'text-orange-600 bg-orange-500/10';
    case 'medium': return 'text-yellow-600 bg-yellow-500/10';
    case 'low': return 'text-blue-600 bg-blue-500/10';
    default: return 'text-gray-600 bg-gray-500/10';
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'executed':
    case 'approved':
    case 'passed':
      return 'text-green-600 bg-green-500/10';
    case 'pending_review':
    case 'drafted':
      return 'text-blue-600 bg-blue-500/10';
    case 'needs_rework':
    case 'failed':
      return 'text-orange-600 bg-orange-500/10';
    case 'skipped':
      return 'text-gray-600 bg-gray-500/10';
    default:
      return 'text-gray-600 bg-gray-500/10';
  }
}
