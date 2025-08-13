# tests/test_smoke.py
import os
import pytest
from insight13f.sec_13f_analyzer import SEC13FAnalyzer

@pytest.mark.smoke
def test_analyzer_runs_end_to_end():
    """
    冒烟测试：
    1) 端到端执行伯克希尔 13F 分析（不导出 CSV）
    2) 断言返回结构完整
    3) 若存在“上一季度”数据，则断言 Top Holdings 与 Top Buys 不相同
    """
    user_agent = os.getenv("USER_AGENT", "Investment Research smoke@example.com")
    cik = "0001067983"  # Berkshire Hathaway

    analyzer = SEC13FAnalyzer(user_agent=user_agent)
    result = analyzer.analyze_institution(cik, export_csv=False, sort_by_share_change=False)

    # 结构断言
    assert isinstance(result, dict)
    for k in ("top_holdings", "top_buys", "top_sells", "analysis_data", "has_previous_data"):
        assert k in result
    assert isinstance(result["top_holdings"], list)
    assert isinstance(result["analysis_data"], list)

    # 有数据
    assert len(result["analysis_data"]) > 0
    assert len(result["top_holdings"]) > 0

    # 字段断言
    sample = result["analysis_data"][0]
    fields = {
        "cusip", "company_name", "ticker",
        "current_value", "previous_value",
        "current_shares", "previous_shares",
        "weight_current", "weight_previous", "weight_change",
        "share_change_abs", "share_change_pct", "status"
    }
    for f in fields:
        assert f in sample

    # 如果存在上季度数据：TopBuys 不应与 TopHoldings 完全相同
    if result["has_previous_data"] and result["top_buys"]:
        h = [x["cusip"] for x in result["top_holdings"][:5]]
        b = [x["cusip"] for x in result["top_buys"][:5]]
        assert h != b, "Top Holdings 与 Top Buys 不应相同"

    # 控制台打印简要结果，便于人工快速确认
    print("\ncurrent:", result["current_accession"])
    print("previous:", result["previous_accession"])
    print("counts:", len(result["top_holdings"]), len(result["top_buys"]), len(result["top_sells"]))
