import os
import pytest
from insight13f.sec_13f_analyzer import SEC13FAnalyzer

@pytest.mark.smoke
def test_analyzer_runs_end_to_end():
    """
    冒烟测试：跑一遍伯克希尔 13F 分析流程并打印三张表前 20 行
    """
    user_agent = os.getenv("USER_AGENT", "Investment Research you@example.com")
    cik = "0001067983"  # Berkshire Hathaway

    analyzer = SEC13FAnalyzer(user_agent=user_agent)
    result = analyzer.analyze_institution(cik, export_csv=False)

    assert "top_holdings" in result
    assert "top_buys" in result
    assert "top_sells" in result

    def _print_table(title, rows, limit):
        print(f"\n{title}")
        print("=" * len(title))
        print(f"{'Rank':<4} {'Company (Ticker)':<40} {'%Port':>8} {'Δpp':>8} {'%ΔShares':>10}")
        print("-" * 80)
        for i, r in enumerate(rows[:limit], 1):
            name = f"{(r.get('company_name') or 'N/A')[:30]} ({r.get('ticker', 'N/A')})"
            pct_sh = "N/A" if r.get("share_change_pct") is None else f"{r['share_change_pct']:.2f}%"
            print(f"{i:<4} {name:<40} {r['weight_current']:>8.2f} {r['weight_change']:>8.2f} {pct_sh:>10}")

    _print_table("TOP 20 HOLDINGS", result["top_holdings"], 20)
    _print_table("TOP 10 BUYS",     result["top_buys"],     10)
    _print_table("TOP 20 SELLS",    result["top_sells"],    20)
