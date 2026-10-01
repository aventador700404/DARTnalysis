import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="text-sm text-ink-3">404</p>
      <h1 className="text-xl font-bold mt-1">찾는 종목이나 페이지가 없어요</h1>
      <p className="text-sm text-ink-3 mt-2">상단 검색창에서 종목명이나 코드로 다시 찾아보세요.</p>
      <Link href="/" className="inline-block mt-5 text-sm font-medium text-brand-ink hover:underline">
        홈으로
      </Link>
    </div>
  );
}
