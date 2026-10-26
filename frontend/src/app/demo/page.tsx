"use client";
import Link from "next/link";
import { mockPlan } from "@/lib/mock";
import { Dashboard } from "@/components/family/Dashboard";

export default function DemoFamily() {
  return (
    <>
      <div className="demo-bar">
        <div className="wrap">
          <span><strong>Demo</strong> · a fictional patient with synthetic documents. Nothing here is saved.</span>
          <Link href="/signup">Create your own</Link>
        </div>
      </div>
      <Dashboard plan={mockPlan} basePath="/demo" />
    </>
  );
}
