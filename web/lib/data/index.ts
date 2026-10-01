// 데이터 소스 선택: DATA_SOURCE=mock(기본, 가상 기업 샘플) | supabase(실제 데이터)
import type { Company, FeedItem, HomeData, SectorData, StockBundle } from "@/lib/types";
import * as mock from "./mock";

const useSupabase = process.env.DATA_SOURCE === "supabase";

async function sb() {
  return import("./supabase");
}

export async function listCompanies(): Promise<Company[]> {
  return useSupabase ? (await sb()).listCompanies() : mock.listCompanies();
}

export async function getHome(): Promise<HomeData> {
  return useSupabase ? (await sb()).getHome() : mock.getHome();
}

export async function getStock(code: string): Promise<StockBundle | null> {
  return useSupabase ? (await sb()).getStock(code) : mock.getStock(code);
}

export async function getSectors(): Promise<SectorData> {
  return useSupabase ? (await sb()).getSectors() : mock.getSectors();
}

export async function getDemoLivePool(): Promise<FeedItem[]> {
  return useSupabase ? [] : mock.demoLivePool();
}

export const dataSource = useSupabase ? "supabase" : "mock";
