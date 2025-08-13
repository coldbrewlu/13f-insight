#!/usr/bin/env python3
import os
import re
import time
import json
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class SEC13FAnalyzer:
    """
    SEC 13F 分析器：
    - 自动定位最近两个 13F filing
    - 兼容多种文件形态（目录里的数字命名 XML，例如 39042.xml；或主 TXT/SGML；以及常见 form13fInfoTable.xml）
    - 解析持仓市值与股数，计算组合权重变化（pp）与持股数变化（%）
    - 产出 Top 20 持仓 / 买入 / 卖出
    """

    def __init__(self, user_agent: str = "Investment Research analysis@example.com"):
        if "@" not in user_agent:
            raise ValueError("SEC 要求 User-Agent 必须包含可联系的 email。")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        # 常用公司名到 ticker 的映射（节选，可继续补充）
        self.ticker_mapping = {
            "APPLE INC": "AAPL", "AMERICAN EXPRESS CO": "AXP", "BANK AMER CORP": "BAC",
            "BANK OF AMERICA CORP": "BAC", "COCA COLA CO": "KO", "COCA-COLA CO": "KO",
            "CHEVRON CORP NEW": "CVX", "OCCIDENTAL PETE CORP": "OXY", "KRAFT HEINZ CO": "KHC",
            "MOODYS CORP": "MCO", "VERISIGN INC": "VRSN", "DAVITA INC": "DVA", "HP INC": "HPQ",
            "CAPITAL ONE FINL CORP": "COF", "KROGER CO": "KR", "CHUBB LIMITED": "CB",
            "VISA INC": "V", "MASTERCARD INC": "MA", "CONSTELLATION BRANDS INC": "STZ",
            "AMAZON COM INC": "AMZN", "AON PLC": "AON", "SIRIUS XM HOLDINGS INC": "SIRI",
            "DOMINOS PIZZA INC": "DPZ"
        }

    # ---------------------------
    # 一、发现最近两个 13F filing
    # ---------------------------
    def get_recent_13f_filings(self, cik: str) -> Tuple[str, str]:
        """返回 (current_accession, previous_accession)。会验证“前一份”确实含有持仓数据。"""
        cik_padded = f"{int(cik):010d}"
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        forms = data["filings"]["recent"]["form"]
        accs = data["filings"]["recent"]["accessionNumber"]
        dates = data["filings"]["recent"]["filingDate"]

        cand = [(f, a, d) for f, a, d in zip(forms, accs, dates) if f in {"13F-HR", "13F-HR/A"}]
        cand.sort(key=lambda x: x[2], reverse=True)
        if len(cand) < 2:
            raise RuntimeError("可用 13F 数量不足 2。")

        current = cand[0][1]
        # 逐个回溯，找到确有信息表的前一份
        previous = None
        for _, acc, _ in cand[1:5]:
            content = self.fetch_13f_data(cik, acc)
            if content and self._looks_like_info_table(content):
                previous = acc
                break
        if not previous:
            previous = cand[1][1]  # 兜底

        return current, previous

    # --------------------------------
    # 二、抓取 filing 中的“信息表”原始内容
    # --------------------------------
    def fetch_13f_data(self, cik: str, accession_number: str) -> Optional[str]:
        """
        统一抓取入口：
        1) 先读目录 JSON: /index.json，找 *.xml 并逐个验证是否像信息表（informationTable/infoTable）
        2) 如果目录没有合适 XML，则尝试“主 TXT” {accession}.txt（许多历史 filing 可用）
        3) 最后再尝试常见的 form13fInfoTable.xml 命名
        返回原始文本（XML/TXT/HTML 其一）
        """
        content = self._fetch_from_directory_index(cik, accession_number)
        if content:
            return content

        content = self._fetch_primary_txt(cik, accession_number)
        if content:
            return content

        content = self._fetch_by_common_xml_patterns(cik, accession_number)
        return content

    def _dir_index_url(self, cik: str, accession_number: str) -> str:
        acc_clean = accession_number.replace("-", "")
        cik_int = int(cik)
        return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/index.json"

    def _fetch_from_directory_index(self, cik: str, accession_number: str) -> Optional[str]:
        """读取目录 index.json，优先尝试数字命名 XML（例如 39042.xml）。"""
        idx_url = self._dir_index_url(cik, accession_number)
        r = self.session.get(idx_url, timeout=30)
        if r.status_code != 200:
            return None

        j = r.json()
        base = j["directory"]["name"]  # 例如 /Archives/edgar/data/1067983/0000...
        items = j["directory"]["item"]
        xml_names = [it["name"] for it in items if it["name"].lower().endswith(".xml")]

        for name in xml_names:
            url = f"https://www.sec.gov{base}/{name}"
            try:
                t = self.session.get(url, timeout=30).text
                if self._looks_like_info_table(t):
                    return t
            except requests.RequestException:
                continue
        return None

    def _fetch_primary_txt(self, cik: str, accession_number: str) -> Optional[str]:
        """尝试 {accession}.txt 主文档（SGML/TXT 内含信息表）。"""
        acc_clean = accession_number.replace("-", "")
        cik_int = int(cik)
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{accession_number}.txt"
        r = self.session.get(url, timeout=30)
        if r.status_code == 200 and self._looks_like_info_table(r.text):
            return r.text
        return None

    def _fetch_by_common_xml_patterns(self, cik: str, accession_number: str) -> Optional[str]:
        """最后尝试常见命名的 XML。"""
        acc_clean = accession_number.replace("-", "")
        cik_int = int(cik)
        patterns = [
            "form13fInfoTable.xml", "InfoTable.xml",
            "xslForm13F_X01/form13fInfoTable.xml", "xslForm13F_X01/InfoTable.xml",
            f"d{acc_clean[:12]}inftable.xml", "informationTable.xml", "table.xml", "holdings.xml",
            "primary_doc.xml"
        ]
        for pat in patterns:
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{pat}"
            r = self.session.get(url, timeout=30)
            if r.status_code == 200 and self._looks_like_info_table(r.text):
                return r.text
        return None

    # ---------------------------
    # 三、解析：支持 XML / TXT / HTML
    # ---------------------------
    def parse_13f_data(self, content: str, aggregate_by_cusip8: bool = True) -> Dict:
        """自动识别格式并解析为 {cusip: {company_name, market_value, shares}}"""
        s = content.lstrip()
        if s.startswith("<"):
            # XML/HTML
            if "informationtable" in s.lower() or "infotable" in s.lower():
                return self._parse_xml_format(s, aggregate_by_cusip8)
            return self._parse_html_format(s, aggregate_by_cusip8)
        # TXT/SGML
        return self._parse_txt_sgml_format(content, aggregate_by_cusip8)

    def _parse_xml_format(self, xml_content: str, aggregate_by_cusip8: bool) -> Dict:
        xml_clean = re.sub(r' xmlns="[^"]+"', "", xml_content, count=1)
        try:
            root = ET.fromstring(xml_clean)
        except ET.ParseError:
            return {}

        holdings = defaultdict(lambda: {"company_name": "", "market_value": 0.0, "shares": 0})
        for table in root.findall(".//infoTable"):
            try:
                name = (table.find(".//nameOfIssuer").text or "").strip().upper()
                cusip = (table.find(".//cusip").text or "").strip()
                val_th = float((table.find(".//value").text or "0").strip())
                mv = val_th * 1000
                sh = 0
                sh_node = table.find(".//shrsOrPrnAmt/sshPrnamt")
                if sh_node is not None and sh_node.text:
                    sh = int(float(sh_node.text.strip()))
                key = cusip[:8] if aggregate_by_cusip8 else cusip
                holdings[key]["market_value"] += mv
                holdings[key]["shares"] += sh
                if not holdings[key]["company_name"]:
                    holdings[key]["company_name"] = name
            except Exception:
                continue
        return dict(holdings)

    def _parse_txt_sgml_format(self, txt: str, aggregate_by_cusip8: bool) -> Dict:
        holdings = defaultdict(lambda: {"company_name": "", "market_value": 0.0, "shares": 0})
        lines = txt.splitlines()
        in_table = False
        for ln in lines:
            low = ln.lower()
            if not in_table and any(k in low for k in ["information table", "<informationtable", "<infotable", "info table"]):
                in_table = True
                continue
            if in_table and any(k in low for k in ["</informationtable", "</infotable", "<signature", "<signatures"]):
                in_table = False
            if not in_table:
                continue

            m_cusip = re.search(r"\b([A-Z0-9]{9})\b", ln)
            if not m_cusip:
                continue
            cusip_full = m_cusip.group(1)
            # 取 CUSIP 前的文本当作公司名（粗略但有效）
            parts = ln.split()
            name = ""
            for j, p in enumerate(parts):
                if cusip_full in p:
                    name = " ".join(parts[:j]).strip().upper()
                    name = re.sub(r"[<>]", "", name)
                    break
            # 行内数字：大概率包含 shares 和 value(thousands)
            nums = [int(n.replace(",", "")) for n in re.findall(r"\b(\d{1,3}(?:,\d{3})*|\d+)\b", ln)]
            if not nums:
                continue
            nums.sort(reverse=True)
            shares = nums[0]
            value_th = nums[-1] if len(nums) > 1 else max(shares // 1000, 0)
            mv = value_th * 1000
            key = cusip_full[:8] if aggregate_by_cusip8 else cusip_full
            holdings[key]["market_value"] += mv
            holdings[key]["shares"] += shares
            if not holdings[key]["company_name"] and name:
                holdings[key]["company_name"] = name
        # 若抽取过少，使用备用 SGML 抽取
        if len(holdings) < 5:
            return self._parse_sgml_alternative(txt, aggregate_by_cusip8)
        return dict(holdings)

    def _parse_sgml_alternative(self, txt: str, aggregate_by_cusip8: bool) -> Dict:
        holdings = defaultdict(lambda: {"company_name": "", "market_value": 0.0, "shares": 0})
        cusips = list(re.finditer(r"(?:CUSIP|cusip)\s*[: ]\s*([A-Z0-9]{9})", txt))
        for m in cusips:
            cusip = m.group(1)
            start = max(0, m.start() - 500)
            end = min(len(txt), m.end() + 500)
            chunk = txt[start:end]
            name = ""
            m_name = re.search(r"(?:NAMEOFISSUER|NAME OF ISSUER|nameofissuer)\s*[: ]\s*([^\n<]+)", chunk, re.I)
            if m_name:
                name = re.sub(r"[<>/]", "", m_name.group(1)).strip().upper()
            mv = 0
            m_val = re.search(r"(?:VALUE|value)\s*[: ]\s*(\d{1,3}(?:,\d{3})*|\d+)", chunk)
            if m_val:
                mv = int(m_val.group(1).replace(",", "")) * 1000
            sh = 0
            m_sh = re.search(r"(?:SSHPRNAMT|sshprnamt|SHARES)\s*[: ]\s*(\d{1,3}(?:,\d{3})*|\d+)", chunk)
            if m_sh:
                sh = int(m_sh.group(1).replace(",", ""))
            if mv > 0 or sh > 0:
                key = cusip[:8] if aggregate_by_cusip8 else cusip
                holdings[key]["market_value"] += mv
                holdings[key]["shares"] += sh
                if not holdings[key]["company_name"] and name:
                    holdings[key]["company_name"] = name
        return dict(holdings)

    def _parse_html_format(self, html: str, aggregate_by_cusip8: bool) -> Dict:
        holdings = defaultdict(lambda: {"company_name": "", "market_value": 0.0, "shares": 0})
        for m in re.finditer(r"([A-Z0-9]{9})", html):
            cusip = m.group(1)
            start = max(0, m.start() - 800)
            end = min(len(html), m.end() + 800)
            chunk = html[start:end]
            name = ""
            m_name = re.search(r"(?:NAMEOFISSUER|nameofissuer)[^>]*>([^<]+)", chunk, re.I)
            if m_name:
                name = re.sub(r"&[^;]+;", "", m_name.group(1)).strip().upper()
            nums = [int(n.replace(",", "")) for n in re.findall(r">(\d{1,3}(?:,\d{3})*)<", chunk)]
            if nums:
                nums.sort(reverse=True)
                shares = nums[0]
                value_th = nums[-1] if len(nums) > 1 else max(shares // 1000, 0)
                mv = value_th * 1000
                key = cusip[:8] if aggregate_by_cusip8 else cusip
                holdings[key]["market_value"] += mv
                holdings[key]["shares"] += shares
                if not holdings[key]["company_name"] and name:
                    holdings[key]["company_name"] = name
        return dict(holdings)

    # ---------------------------
    # 四、指标计算与表格生成
    # ---------------------------
    def get_ticker_symbol(self, company_name: str) -> str:
        nm = (company_name or "").strip().upper()
        if nm in self.ticker_mapping:
            return self.ticker_mapping[nm]
        for pat, tk in self.ticker_mapping.items():
            if pat in nm or nm in pat:
                return tk
        return "N/A"

    def calculate_portfolio_changes(self, cur: Dict, prev: Dict) -> List[Dict]:
        """计算权重变化（pp）与股数变化（%）"""
        tot_c = sum(x["market_value"] for x in cur.values()) or 1.0
        tot_p = sum(x["market_value"] for x in prev.values()) or 1.0
        all_keys = set(cur) | set(prev)
        out = []
        for k in all_keys:
            c = cur.get(k, {"company_name": "", "market_value": 0.0, "shares": 0})
            p = prev.get(k, {"company_name": "", "market_value": 0.0, "shares": 0})
            name = c["company_name"] or p["company_name"]
            ticker = self.get_ticker_symbol(name)
            w_c = (c["market_value"] / tot_c) * 100
            w_p = (p["market_value"] / tot_p) * 100
            w_delta = w_c - w_p
            sh_c, sh_p = c["shares"], p["shares"]
            sh_pct = ((sh_c - sh_p) / sh_p * 100) if sh_p > 0 else None
            status = "NEW" if p["market_value"] == 0 else ("EXIT" if c["market_value"] == 0 else "CHANGE")
            out.append({
                "cusip": k, "company_name": name, "ticker": ticker,
                "current_value": c["market_value"], "previous_value": p["market_value"],
                "current_shares": sh_c, "previous_shares": sh_p,
                "weight_current": w_c, "weight_previous": w_p, "weight_change": w_delta,
                "share_change_abs": sh_c - sh_p, "share_change_pct": sh_pct,
                "status": status
            })
        return out

    def generate_tables(self, rows: List[Dict], sort_by_share_change: bool) -> Tuple[List[Dict], List[Dict], List[Dict]]:

        """
        生成三张表：
        - Top Holdings：仍按当前权重排序（不变）
        - Top Buys：只保留“股数增加且占比上升”的标的，按 Δpp 降序取前 10
        - Top Sells：只保留“股数减少且占比下降”的标的，按 Δpp 升序取前 20
        """
        # 1) Top holdings：当前仍持有的头部权重
        current_positions = [r for r in rows if r["current_value"] > 0]
        top_holdings = sorted(current_positions, key=lambda x: x["weight_current"], reverse=True)[:20]

        # 2) 只统计“真买入/真卖出”（股数发生变化）
        buys_candidates = [
            r for r in rows
            if r["share_change_abs"] > 0 and r["weight_change"] > 0
        ]
        sells_candidates = [
            r for r in rows
            if r["share_change_abs"] < 0 and r["weight_change"] < 0
        ]

        # 3) 排序与截断
        #   与网站一致：按组合占比变动（pp）排序，而不是按股数变化百分比
        top_buys = sorted(buys_candidates, key=lambda x: x["weight_change"], reverse=True)[:10]
        top_sells = sorted(sells_candidates, key=lambda x: x["weight_change"])[:20]

        return top_holdings, top_buys, top_sells


    # ---------------------------
    # 五、主流程
    # ---------------------------
    def analyze_institution(self, cik: str, export_csv: bool = False, sort_by_share_change: bool = False) -> Dict:
        cur_acc, prev_acc = self.get_recent_13f_filings(cik)
        time.sleep(0.2)
        cur_raw = self.fetch_13f_data(cik, cur_acc)
        if not cur_raw:
            raise RuntimeError(f"未找到信息表: {cur_acc}")
        time.sleep(0.2)
        prev_raw = self.fetch_13f_data(cik, prev_acc)  # 可能为 None（极少数）
        cur_hold = self.parse_13f_data(cur_raw)
        prev_hold = self.parse_13f_data(prev_raw) if prev_raw else {}
        rows = self.calculate_portfolio_changes(cur_hold, prev_hold)
        top_hold, top_buy, top_sell = self.generate_tables(rows, sort_by_share_change)

        if export_csv:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            pd.DataFrame(top_hold).to_csv(f"cik_{cik}_holdings_{ts}.csv", index=False)
            pd.DataFrame(top_buy).to_csv(f"cik_{cik}_buys_{ts}.csv", index=False)
            pd.DataFrame(top_sell).to_csv(f"cik_{cik}_sells_{ts}.csv", index=False)

        return {
            "cik": cik,
            "current_accession": cur_acc,
            "previous_accession": prev_acc,
            "top_holdings": top_hold,
            "top_buys": top_buy,
            "top_sells": top_sell,
            "analysis_data": rows,
            "has_previous_data": bool(prev_hold),
            "sort_by_share_change": sort_by_share_change,
        }

    # ---------------------------
    # 六、辅助
    # ---------------------------
    def _looks_like_info_table(self, text: str) -> bool:
        s = (text or "").lower()
        if not s:
            return False
        hits = sum(k in s for k in ["informationtable", "infotable", "nameofissuer", "cusip"])
        # 过滤只有 cover/summary 的主 XML
        if "edgarsubmission" in s and "infotable" not in s and "informationtable" not in s:
            return False
        return hits >= 2


def main():
    analyzer = SEC13FAnalyzer(os.getenv("USER_AGENT", "Investment Research analysis@example.com"))
    cik = "0001067983"  # Berkshire Hathaway
    res = analyzer.analyze_institution(cik, export_csv=False, sort_by_share_change=False)

    def _print(title, data, kind):
        print("\n" + title)
        print("=" * len(title))
        if kind == "hold":
            print(f"{'Rank':<4} {'Company (Ticker)':<40} {'% Port':>8} {'Δ pp':>8} {'% Change(shares)':>17} {'Status':>8}")
            for i, r in enumerate(data, 1):
                pct = f"{r['share_change_pct']:.2f}%" if r['share_change_pct'] is not None else "N/A"
                nm = f"{r['company_name'][:30]} ({r['ticker']})"
                print(f"{i:<4} {nm:<40} {r['weight_current']:>8.2f} {r['weight_change']:>8.2f} {pct:>17} {r['status']:>8}")
        else:
            hdr = "Wt Increase" if kind == "buy" else "Wt Decrease"
            print(f"{'Rank':<4} {'Company (Ticker)':<40} {'% Port':>8} {hdr:>12} {'% Change(shares)':>17}")
            for i, r in enumerate(data, 1):
                pct = f"{r['share_change_pct']:.2f}%" if r['share_change_pct'] is not None else "N/A"
                nm = f"{r['company_name'][:30]} ({r['ticker']})"
                print(f"{i:<4} {nm:<40} {r['weight_current']:>8.2f} {r['weight_change']:>12.2f} {pct:>17}")

    _print("TOP 20 HOLDINGS", res["top_holdings"], "hold")
    _print("TOP 20 BUYS", res["top_buys"], "buy")
    _print("TOP 20 SELLS", res["top_sells"], "sell")


if __name__ == "__main__":
    main()
