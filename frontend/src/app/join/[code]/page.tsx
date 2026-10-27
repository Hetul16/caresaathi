import type { Metadata } from "next";
import { JoinClient } from "@/components/JoinClient";

export const instant = false; // dynamic: the invitation code is runtime data

export const metadata: Metadata = { title: "Join a family", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function Join(props: PageProps<"/join/[code]">) {
  const { code } = await props.params;
  return <JoinClient code={code} />;
}
