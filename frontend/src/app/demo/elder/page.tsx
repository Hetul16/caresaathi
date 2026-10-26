"use client";
import { mockPlan } from "@/lib/mock";
import { ElderView } from "@/components/ElderView";

export default function DemoElder() {
  return <ElderView plan={mockPlan} emergencyHref="/e/demo-token" />;
}
