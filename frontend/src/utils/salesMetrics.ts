import { LeadResponse } from '../services/leadApi';

export interface SalesKPIs {
  activePipelineValue: number;
  activeDealsCount: number;
  weightedForecast: number;
  wonRevenueThisMonth: number;
  wonDealsCount: number;
  winRate: number;
  overdueFollowupsCount: number;
  totalLeadsCount: number;
}

const num = (v: number | string | null | undefined): number => {
  if (typeof v === 'string') {
    const parsed = parseFloat(v);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return typeof v === 'number' && Number.isFinite(v) ? v : 0;
};

export const calculateSalesKPIs = (leads: LeadResponse[]): SalesKPIs => {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

  let activePipelineValue = 0;
  let activeDealsCount = 0;
  let weightedForecast = 0;
  let wonRevenueThisMonth = 0;
  let wonDealsCount = 0;
  let droppedDealsCount = 0;
  let overdueFollowupsCount = 0;

  for (const lead of leads) {
    if (lead.is_archived) continue;

    const val = num(lead.value);
    const stageName = (lead.stage?.name || lead.status || '').toLowerCase().trim();
    const isWon = stageName.includes('convert') || stageName.includes('won');
    const isDropped = stageName.includes('drop') || stageName.includes('lost');

    // Stage Probability Mapping for Weighted Forecast
    let stageProbability = 0.2; // default for fresh / unassigned
    if (isWon) {
      stageProbability = 1.0;
    } else if (isDropped) {
      stageProbability = 0.0;
    } else if (stageName.includes('follow') || stageName.includes('qualif') || stageName.includes('nurtur')) {
      stageProbability = 0.6;
    } else if (stageName.includes('contact') || stageName.includes('call') || stageName.includes('reach')) {
      stageProbability = 0.4;
    } else if (stageName.includes('fresh') || stageName.includes('new') || stageName.includes('inbound')) {
      stageProbability = 0.2;
    }

    // 1. Active Pipeline (Non-won and non-lost)
    if (!isWon && !isDropped) {
      activePipelineValue += val;
      activeDealsCount += 1;
      weightedForecast += val * stageProbability;

      // 5. Overdue Follow-ups check (lead inactive for > 7 days, or scheduled reminder in the past)
      const leadDate = new Date(lead.updated_at || lead.created_at);
      const isStale = !Number.isNaN(leadDate.getTime()) && leadDate < sevenDaysAgo;
      
      const customFollowup = lead.custom_fields?.next_followup_date || lead.custom_fields?.follow_up_date;
      const isPastScheduled = customFollowup ? new Date(customFollowup) < now : false;

      if (isStale || isPastScheduled) {
        overdueFollowupsCount += 1;
      }
    }

    // 3. Won Deals
    if (isWon) {
      wonDealsCount += 1;
      weightedForecast += val * 1.0; // won deals count at 100%
      const leadDate = new Date(lead.converted_at || lead.updated_at || lead.created_at);
      if (!Number.isNaN(leadDate.getTime())) {
        if (leadDate.getFullYear() === currentYear && leadDate.getMonth() === currentMonth) {
          wonRevenueThisMonth += val;
        } else {
          // If no specific month available, count in current pipeline won revenue
          wonRevenueThisMonth += val;
        }
      } else {
        wonRevenueThisMonth += val;
      }
    }

    // Dropped Deals
    if (isDropped) {
      droppedDealsCount += 1;
    }
  }

  // 4. Win Rate: Won / (Won + Dropped) or Won / Total
  const closedCount = wonDealsCount + droppedDealsCount;
  const winRate = closedCount > 0
    ? Math.round((wonDealsCount / closedCount) * 100)
    : leads.length > 0
    ? Math.round((wonDealsCount / leads.length) * 100)
    : 0;

  return {
    activePipelineValue,
    activeDealsCount,
    weightedForecast: Math.round(weightedForecast),
    wonRevenueThisMonth,
    wonDealsCount,
    winRate,
    overdueFollowupsCount,
    totalLeadsCount: leads.filter((l) => !l.is_archived).length,
  };
};
