"""가상 데이터 생성기가 실제 분석 함수들을 끝까지 통과하는지 확인 (통합 테스트)."""

from dartpipe.mock.generate import Generator, to_web_json


def test_mock_end_to_end():
    gen = Generator(seed=1)
    u, news = gen.run()
    data = to_web_json(u, news)
    assert data["meta"]["demo"] is True
    assert len(data["companies"]) == 18
    codes = {c["code"] for c in data["companies"]}
    assert all(code.startswith("X") for code in codes)  # 실제 종목코드와 겹치지 않음
    assert set(data["prices"]) == codes
    assert len(data["index"]["kospi"]) == len(data["calendar"]) == len(data["index"]["ew"])
    assert any(d.get("impact") for d in data["disclosures"])
    shown = [s for s in data["stats"] if not s["hidden"]]
    assert shown and all(s["n"] >= 5 for s in shown)
    # 재무: 분기 누적 → 분기 값 변환이 실제 값과 일치해야 함
    truth = gen.truth(next(s for s in __import__("dartpipe.mock.generate", fromlist=["SPECS"]).SPECS if s.code == "X00010"))
    t = {(r["year"], r["quarter"]): r["revenue"] for r in truth}
    for q in data["financials"]["X00010"]:
        assert abs(q["revenue"] - round(t[(q["year"], q["quarter"])])) <= 2
