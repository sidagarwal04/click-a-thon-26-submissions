import React from 'react';
import { HumanReviewStatus } from '../../types';
import { CheckCircle2, AlertTriangle, Flame, ThumbsUp, XCircle } from 'lucide-react';
import { useState } from 'react';

interface HumanLoopControlsProps {
  status: HumanReviewStatus;
  reviewedAt?: string;
  reviewedBy?: string;
  hallucinationReason?: string;
  feedbackNote?: string;
  onApprove: () => void;
  onFlagHallucination: (reason: string, feedback: string) => void;
}

const HALLUCINATION_REASONS = [
  'LLM exaggerated percentage change / numbers',
  'Hallucinated non-existent segment or device model',
  'Incorrect factor attribution (Requests vs Fill Rate)',
  'Misquoted baseline metrics — verbatim constraint violation',
  'Other model hallucination',
];

export const HumanLoopControls: React.FC<HumanLoopControlsProps> = ({
  status,
  reviewedAt,
  reviewedBy,
  hallucinationReason,
  feedbackNote,
  onApprove,
  onFlagHallucination,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [selectedReason, setSelectedReason] = useState(HALLUCINATION_REASONS[0]);
  const [customNote, setCustomNote] = useState('');

  const handleConfirm = () => {
    onFlagHallucination(selectedReason, customNote);
    setShowModal(false);
    setCustomNote('');
  };

  return (
    <>
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-semibold text-slate-800">Human-in-the-Loop Verification</span>
          </div>
          {/* Current status badge */}
          {status === 'APPROVED' && (
            <span className="badge badge-green">
              <CheckCircle2 className="w-3 h-3" /> Approved
            </span>
          )}
          {status === 'HALLUCINATION' && (
            <span className="badge badge-red">
              <Flame className="w-3 h-3" /> Flagged Hallucination
            </span>
          )}
          {status === 'PENDING' && (
            <span className="badge badge-amber">
              <AlertTriangle className="w-3 h-3" /> Awaiting Review
            </span>
          )}
        </div>

        {/* Status detail row */}
        <div className="px-4 py-3">
          {status === 'APPROVED' && (
            <p className="text-[12px] text-slate-500">
              Verified by <span className="text-slate-700 font-medium">{reviewedBy || 'Operator'}</span>
              {reviewedAt && <> on {reviewedAt}</>}.
              {feedbackNote && <> <span className="italic text-slate-400">"{feedbackNote}"</span></>}
            </p>
          )}
          {status === 'HALLUCINATION' && (
            <p className="text-[12px] text-slate-500">
              Reason: <span className="text-red-600">{hallucinationReason}</span>
              {feedbackNote && <> — <span className="italic text-slate-400">"{feedbackNote}"</span></>}
            </p>
          )}
          {status === 'PENDING' && (
            <p className="text-[12px] text-slate-500">
              Review the AI diagnosis above, then approve if accurate or flag any hallucination.
            </p>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 px-4 pb-3">
          <button
            onClick={onApprove}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold transition-all ${
              status === 'APPROVED'
                ? 'bg-emerald-600 text-white border border-emerald-500 shadow-sm'
                : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200'
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            Approve Finding
          </button>
          <button
            onClick={() => setShowModal(true)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold transition-all ${
              status === 'HALLUCINATION'
                ? 'bg-red-600 text-white border border-red-500 shadow-sm'
                : 'bg-red-50 hover:bg-red-100 text-red-700 border border-red-200'
            }`}
          >
            <Flame className="w-3.5 h-3.5" />
            Flag Hallucination
          </button>
        </div>
      </div>

      {/* Flag Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg bg-white border border-slate-200 rounded-xl p-5 shadow-2xl space-y-4 animate-slide-up">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-[14px] font-bold text-slate-900 flex items-center gap-2">
                <Flame className="w-4 h-4 text-red-500" /> Flag AI Hallucination
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[12px] text-slate-500 leading-relaxed">
              Select the primary reason this RCA output is inaccurate. Feedback is sent to Langfuse to tune the DeepSeek narrator.
            </p>

            <div className="space-y-1.5">
              <label className="section-label block">Hallucination Category</label>
              <select
                value={selectedReason}
                onChange={(e) => setSelectedReason(e.target.value)}
                className="w-full bg-white text-[12px] text-slate-900 border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-300"
              >
                {HALLUCINATION_REASONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="section-label block">Operator Note (optional)</label>
              <textarea
                value={customNote}
                onChange={(e) => setCustomNote(e.target.value)}
                rows={3}
                placeholder="Describe the discrepancy observed…"
                className="w-full bg-white text-[12px] text-slate-900 border border-slate-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={() => setShowModal(false)}
                className="btn-ghost text-[12px] py-1.5"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-[12px] shadow-sm transition-all"
              >
                Confirm &amp; Record
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
