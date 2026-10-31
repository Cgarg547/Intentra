import {
  Activity,
  Bot,
  ChartNoAxesCombined,
  ClipboardCheck,
  CreditCard,
  FileCheck2,
  LayoutDashboard,
  ScrollText,
  Settings2,
  ShieldCheck,
  Store,
} from "lucide-react";

export const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Intent Contracts", href: "/contracts", icon: FileCheck2 },
  { label: "AI Agents", href: "/agents", icon: Bot },
  { label: "Payments", href: "/payments", icon: CreditCard },
  { label: "Approvals", href: "/approvals", icon: ClipboardCheck },
  { label: "Analytics", href: "/analytics", icon: ChartNoAxesCombined },
  { label: "Security Center", href: "/security", icon: ShieldCheck },
  { label: "Audit Explorer", href: "/audit", icon: ScrollText },
  { label: "Merchants", href: "/merchants", icon: Store },
  { label: "System Status", href: "/status", icon: Activity },
  { label: "Settings", href: "/settings", icon: Settings2 },
] as const;
