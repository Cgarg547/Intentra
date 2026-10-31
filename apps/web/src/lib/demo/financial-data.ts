export const spendingTrends = [
  { day: "Mon", authorized: 1250, blocked: 320 },
  { day: "Tue", authorized: 1820, blocked: 480 },
  { day: "Wed", authorized: 1450, blocked: 650 },
  { day: "Thu", authorized: 2300, blocked: 390 },
  { day: "Fri", authorized: 1980, blocked: 720 },
  { day: "Sat", authorized: 850, blocked: 180 },
  { day: "Sun", authorized: 1420, blocked: 510 },
];

export const demoTransactions = [
  {
    id: "TXN-1042",
    agent: "Procurement Agent",
    merchant: "Cloud Infrastructure",
    amount: 1240,
    decision: "Allowed",
    reason: "Within approved contract limits",
  },
  {
    id: "TXN-1041",
    agent: "Travel Booking Agent",
    merchant: "Travel Services",
    amount: 780,
    decision: "Blocked",
    reason: "Merchant category not permitted",
  },
  {
    id: "TXN-1040",
    agent: "Operations Agent",
    merchant: "Office Supplies",
    amount: 420,
    decision: "Review",
    reason: "Human approval required",
  },
  {
    id: "TXN-1039",
    agent: "Procurement Agent",
    merchant: "Developer Tools",
    amount: 310,
    decision: "Allowed",
    reason: "Policy checks satisfied",
  },
  {
    id: "TXN-1038",
    agent: "Travel Booking Agent",
    merchant: "Hospitality Services",
    amount: 1650,
    decision: "Blocked",
    reason: "Spending limit exceeded",
  },
] as const;
