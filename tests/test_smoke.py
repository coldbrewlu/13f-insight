# tests/test_smoke.py
import os
import pytest

# 从包里导入类（注意是class，不是function）
from insight13f.sec_13f_analyzer import SEC13FAnalyzer

@pytest.mark.smoke
def test_analyzer_runs_smoke():
    """
    冒烟测试：跑一遍伯克希尔的 13F 分析流程，验证不报错且返回三张表。
    这是“联机”测试（需要访问 SEC），首次运行会比较慢。
    """
    # SEC 要求 User-Agent 必须包含一个可联系的邮箱
    user_agent = os.getenv("USER_AGENT", "Investment Research you@example.com")
    cik = "0001067983"  # 伯克希尔

    analyzer = SEC13FAnalyzer(user_agent=user_agent)

    # 不导出 CSV，减少副作用
    result = analyzer.analyze_institution(cik, export_csv=False)

    # 基本结构性断言：返回字典，包含三张表
    assert isinstance(result, dict)
    for key in ("top_holdings", "top_buys", "top_sells"):
        assert key in result
        assert isinstance(result[key], list)

    # 每张表至少应该有条目（极端情况下可能 <20，但应 >=1）
    assert len(result["top_holdings"]) >= 1
