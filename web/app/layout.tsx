import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { TopBar } from "@/components/TopBar";
import { listCompanies, dataSource } from "@/lib/data";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/site";

const pretendard = localFont({
  src: "./fonts/PretendardVariable.woff2",
  variable: "--font-pretendard",
  weight: "45 920",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: `${SITE_NAME} — ${SITE_TAGLINE}`, template: `%s · ${SITE_NAME}` },
  description:
    "공시가 뜰 때마다 주가가 어떻게 움직였고 회사 숫자는 어떻게 바뀌었는지를, 종목의 재무 체력과 함께 차트 위에서 보여주는 DART 기반 주가 분석 대시보드",
};

// 첫 화면이 그려지기 전에 저장된 테마를 적용 (깜빡임 방지)
const themeScript = `try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}`;

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const companies = await listCompanies();
  const demo = dataSource === "mock";
  return (
    <html lang="ko" className={`${pretendard.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <TopBar companies={companies.map((c) => ({ code: c.code, name: c.name }))} demo={demo} />
        <main className="flex-1 w-full max-w-[1280px] mx-auto px-4 sm:px-6 py-5 sm:py-6">{children}</main>
        <footer className="border-t border-line mt-8">
          <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-6 text-xs text-ink-3 leading-relaxed space-y-1">
            <p>
              과거 통계이며 투자 권유가 아닙니다. 공시 후 수익률은 같은 기간 시장 대비 초과수익률이고, 표본이 5건 미만인 통계는 표시하지 않습니다.
            </p>
            <p>
              데이터: 금융감독원 OpenDART · 금융위원회 주식시세정보(공공데이터포털, 하루 지연) · 네이버 뉴스 검색 · 차트: TradingView Lightweight
              Charts
              {demo && " · 지금 보이는 숫자는 가상 기업으로 만든 샘플 데이터입니다."}
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
