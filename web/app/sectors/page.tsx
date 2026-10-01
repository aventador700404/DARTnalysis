import type { Metadata } from "next";
import { SectorsView } from "@/components/sectors/SectorsView";
import { getSectors } from "@/lib/data";

export const metadata: Metadata = { title: "업종 비교" };
export const revalidate = 300;

export default async function SectorsPage() {
  const data = await getSectors();
  return <SectorsView data={data} />;
}
