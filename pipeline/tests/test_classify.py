from dartpipe.classify import classify


def test_major_reports():
    assert classify("주요사항보고서(유상증자결정)").subtype == "rights_offering"
    assert classify("주요사항보고서(전환사채권발행결정)").category == "financing"
    assert classify("주요사항보고서(자기주식취득결정)").subtype == "buyback"
    assert classify("주요사항보고서(자기주식처분결정)").subtype == "treasury_disposal"
    assert classify("주요사항보고서 (감자결정)").subtype == "capital_reduction"


def test_ownership_and_earnings():
    assert classify("주식등의대량보유상황보고서(일반)").subtype == "major_holder"
    assert classify("임원ㆍ주요주주특정증권등소유상황보고서").subtype == "insider"
    assert classify("분기보고서 (2026.03)").category == "earnings"
    assert classify("연결재무제표기준영업(잠정)실적(공정공시)").subtype == "preliminary_earnings"


def test_correction_prefix_and_other():
    c = classify("[기재정정]주요사항보고서(유상증자결정)")
    assert c.is_correction and c.subtype == "rights_offering"
    assert classify("[첨부추가]사업보고서 (2025.12)").is_correction is False
    assert classify("단일판매ㆍ공급계약체결").category == "other"
