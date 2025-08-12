import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import time
import os
from datetime import datetime

class SEC13FAnalyzer:
    """
    Analyzes SEC 13F filings to extract portfolio holdings and changes
    """
    
    def __init__(self, user_agent: str = "Investment Research analysis@example.com"):
        """
        Initialize the analyzer with SEC-compliant headers
        
        Args:
            user_agent: User agent string for SEC requests (must include email)
        """
        self.headers = {'User-Agent': user_agent}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Enhanced ticker mapping for better readability
        self.ticker_mapping = {
            "APPLE INC": "AAPL",
            "BANK OF AMERICA CORP": "BAC", 
            "BANK AMER CORP": "BAC",
            "AMERICAN EXPRESS CO": "AXP",
            "COCA COLA CO": "KO", 
            "COCA-COLA CO": "KO",
            "CHEVRON CORP NEW": "CVX",
            "CHEVRON CORP": "CVX",
            "OCCIDENTAL PETE CORP": "OXY",
            "OCCIDENTAL PETROLEUM CORP": "OXY",
            "KRAFT HEINZ CO": "KHC",
            "MOODYS CORP": "MCO",
            "VERISIGN INC": "VRSN",
            "DAVITA INC": "DVA",
            "HP INC": "HPQ",
            "CITIGROUP INC": "C",
            "CAPITAL ONE FINL CORP": "COF",
            "KROGER CO": "KR",
            "DIAMONDBACK ENERGY INC": "FANG",
            "MARSH & MCLENNAN COS INC": "MMC",
            "MARCH & MCLENNAN COS INC": "MMC",
            "NU HOLDINGS LTD": "NU",
            "LIBERTY MEDIA CORP DELAWARE": "FWONA",
            "LIBERTY MEDIA CORP DE A": "FWONA",
            "LIBERTY MEDIA CORP DE C": "FWONK",
            "AT&T INC": "T",
            "PARAMOUNT GLOBAL": "PARA",
            "VIACOMCBS INC": "PARA",
            "DEUTSCHE TELEKOM AG": "DTEGY",
            "FORMULA ONE GROUP": "FWONK",
            "CHUBB LIMITED": "CB",
            "VISA INC": "V",
            "MASTERCARD INC": "MA",
            "CONSTELLATION BRANDS INC": "STZ",
            "ALLY FINL INC": "ALLY",
            "AMAZON COM INC": "AMZN",
            "CHARTER COMMUNICATIONS INC": "CHTR",
            "DOMINOS PIZZA INC": "DPZ",
            "HEICO CORP": "HEI",
            "JEFFERIES FINL GROUP INC": "JEF",
            "LENNAR CORP": "LEN",
            "LOUISIANA PAC CORP": "LPX",
            "NVR INC": "NVR",
            "POOL CORP": "POOL",
            "SIRIUS XM HOLDINGS INC": "SIRI",
            "T-MOBILE US INC": "TMUS",
            "AON PLC": "AON",
            "LIBERTY LATIN AMERICA LTD": "LILA",
            "DIAGEO P L C": "DEO",
            "ATLANTA BRAVES HLDGS INC": "BATRA",
            "MICROSOFT CORP": "MSFT",
            "JOHNSON & JOHNSON": "JNJ",
            "BERKSHIRE HATHAWAY INC": "BRK.B",
            "JPMORGAN CHASE & CO": "JPM",
            "PROCTER & GAMBLE CO": "PG",
            "UNITEDHEALTH GROUP INC": "UNH",
            "TESLA INC": "TSLA",
            "NVIDIA CORP": "NVDA",
            "META PLATFORMS INC": "META",
            "ALPHABET INC": "GOOGL",
            "WELLS FARGO & CO": "WFC",
            "HOME DEPOT INC": "HD",
            "PFIZER INC": "PFE"
        }
    
    def get_recent_13f_filings(self, cik: str) -> Tuple[str, str]:
        """
        Automatically discover the two most recent 13F filings for a given CIK
        
        This method:
        1. Fetches the company's submission history from SEC
        2. Filters for 13F-HR and 13F-HR/A forms
        3. Sorts by filing date (newest first)
        4. Returns current and previous quarter accession numbers
        
        Args:
            cik: Company's Central Index Key (e.g., "0001067983" for Berkshire Hathaway)
            
        Returns:
            Tuple of (current_accession, previous_accession)
            
        Raises:
            Exception: If unable to find sufficient 13F filings
        """
        print(f"🔍 Searching for recent 13F filings for CIK: {cik}")
        
        # Format CIK to 10 digits with leading zeros
        cik_padded = f"{int(cik):010d}"
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise Exception(f"Failed to fetch submission data: {e}")
        
        # Extract 13F filings
        recent = data["filings"]["recent"]
        filings = []
        
        for form, accession, filing_date in zip(recent["form"], 
                                              recent["accessionNumber"], 
                                              recent["filingDate"]):
            if form in {"13F-HR", "13F-HR/A"}:
                filings.append((form, accession, filing_date))
        
        if len(filings) < 2:
            raise Exception(f"Found only {len(filings)} 13F filings, need at least 2")
        
        # Sort by filing date (newest first)
        filings.sort(key=lambda x: x[2], reverse=True)
        
        # Handle amendments: prefer 13F-HR/A over 13F-HR for same period
        # For simplicity, we'll take the two most recent by date
        current_filing = filings[0]
        previous_filing = filings[1]
        
        print(f"✅ Found current filing: {current_filing[1]} ({current_filing[2]})")
        print(f"✅ Found previous filing: {previous_filing[1]} ({previous_filing[2]})")
        
        return current_filing[1], previous_filing[1]
    
    def fetch_13f_xml(self, cik: str, accession_number: str) -> Optional[str]:
        """
        Fetch the 13F XML data for a specific filing
        
        This method tries multiple possible XML file locations:
        1. form13fInfoTable.xml (most common)
        2. InfoTable.xml (alternative naming)
        3. primary_doc.xml (sometimes used)
        4. Constructed filename with accession number
        
        Args:
            cik: Company's CIK
            accession_number: SEC accession number (with dashes)
            
        Returns:
            XML content as string, or None if not found
        """
        print(f"📥 Fetching XML for accession: {accession_number}")
        
        # Remove dashes from accession number for URL construction
        accession_clean = accession_number.replace('-', '')
        cik_int = int(cik)
        
        # Try multiple possible XML file locations
        possible_urls = [
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/form13fInfoTable.xml",
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/InfoTable.xml",
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/primary_doc.xml",
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/d{accession_clean[:12]}inftable.xml"
        ]
        
        for url in possible_urls:
            try:
                print(f"  Trying: {url}")
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    print(f"  ✅ Success!")
                    return response.text
                else:
                    print(f"  ❌ HTTP {response.status_code}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
        
        print(f"⚠️  Could not fetch XML for {accession_number}")
        return None
    
    def parse_13f_xml(self, xml_content: str, aggregate_by_cusip8: bool = True) -> Dict:
        """
        Parse 13F XML content and extract holdings information
        
        This method:
        1. Removes XML namespaces for easier parsing
        2. Finds all infoTable entries
        3. Extracts issuer name, CUSIP, and market value
        4. Optionally aggregates by CUSIP-8 (first 8 digits) to combine share classes
        5. Handles errors gracefully and continues processing
        
        Args:
            xml_content: Raw XML content from SEC
            aggregate_by_cusip8: If True, aggregate holdings by first 8 digits of CUSIP
            
        Returns:
            Dictionary mapping CUSIP (or CUSIP-8) to holding information
        """
        print(f"🔄 Parsing XML content...")
        
        # Remove namespace declarations for easier parsing
        xml_clean = re.sub(r' xmlns="[^"]+"', '', xml_content, count=1)
        
        try:
            root = ET.fromstring(xml_clean)
        except ET.ParseError as e:
            print(f"❌ XML parsing error: {e}")
            return {}
        
        # Dictionary to store aggregated holdings
        holdings = defaultdict(lambda: {"company_name": "", "market_value": 0.0})
        
        # Find all information tables
        info_tables = root.findall('.//infoTable')
        print(f"  Found {len(info_tables)} holdings entries")
        
        processed = 0
        errors = 0
        
        for table in info_tables:
            try:
                # Extract required fields
                issuer_elem = table.find('.//nameOfIssuer')
                cusip_elem = table.find('.//cusip')
                value_elem = table.find('.//value')
                
                if issuer_elem is None or cusip_elem is None or value_elem is None:
                    errors += 1
                    continue
                
                issuer_name = issuer_elem.text.strip().upper()
                cusip_full = cusip_elem.text.strip()
                
                # Market value is in thousands of USD in the XML
                market_value_thousands = float(value_elem.text.strip())
                market_value_usd = market_value_thousands * 1000
                
                # Decide on aggregation key
                if aggregate_by_cusip8:
                    cusip_key = cusip_full[:8]  # First 8 digits for share class aggregation
                else:
                    cusip_key = cusip_full
                
                # Aggregate market values
                holdings[cusip_key]["market_value"] += market_value_usd
                
                # Keep the first non-empty company name we encounter
                if not holdings[cusip_key]["company_name"] and issuer_name:
                    holdings[cusip_key]["company_name"] = issuer_name
                
                processed += 1
                
            except (AttributeError, ValueError, TypeError) as e:
                errors += 1
                continue
        
        print(f"  ✅ Processed {processed} holdings, {errors} errors")
        return dict(holdings)
    
    def get_ticker_symbol(self, company_name: str) -> str:
        """
        Map company name to ticker symbol for better readability
        
        Args:
            company_name: Company name from 13F filing
            
        Returns:
            Ticker symbol if found, otherwise 'N/A'
        """
        # Clean and normalize company name
        clean_name = company_name.strip().upper()
        
        # Direct lookup
        if clean_name in self.ticker_mapping:
            return self.ticker_mapping[clean_name]
        
        # Try some common variations
        for pattern, ticker in self.ticker_mapping.items():
            if pattern in clean_name or clean_name in pattern:
                return ticker
        
        return 'N/A'
    
    def calculate_portfolio_changes(self, current_holdings: Dict, 
                                  previous_holdings: Dict) -> List[Dict]:
        """
        Calculate portfolio weight changes between two periods
        
        This method:
        1. Calculates total portfolio values for both periods
        2. Computes portfolio weights (% of total) for each holding
        3. Calculates the change in portfolio weight
        4. Handles new positions (previous weight = 0) and exits (current weight = 0)
        
        Args:
            current_holdings: Holdings from current quarter
            previous_holdings: Holdings from previous quarter
            
        Returns:
            List of dictionaries with holding analysis data
        """
        print("📊 Calculating portfolio changes...")
        
        # Calculate total portfolio values
        total_current = sum(h["market_value"] for h in current_holdings.values()) or 1.0
        total_previous = sum(h["market_value"] for h in previous_holdings.values()) or 1.0
        
        print(f"  Current portfolio value: ${total_current:,.0f}")
        print(f"  Previous portfolio value: ${total_previous:,.0f}")
        
        # Get all unique CUSIPs from both periods
        all_cusips = set(current_holdings.keys()) | set(previous_holdings.keys())
        
        results = []
        
        for cusip in all_cusips:
            # Get holding data for both periods
            current_data = current_holdings.get(cusip, {"company_name": "", "market_value": 0.0})
            previous_data = previous_holdings.get(cusip, {"company_name": "", "market_value": 0.0})
            
            # Use the most recent company name
            company_name = current_data["company_name"] or previous_data["company_name"]
            ticker = self.get_ticker_symbol(company_name)
            
            # Calculate portfolio weights
            weight_current = (current_data["market_value"] / total_current) * 100
            weight_previous = (previous_data["market_value"] / total_previous) * 100
            weight_change = weight_current - weight_previous
            
            # Determine position status
            if previous_data["market_value"] == 0:
                status = "NEW"  # New position
            elif current_data["market_value"] == 0:
                status = "EXIT"  # Exited position
            else:
                status = "CHANGE"  # Changed position
            
            results.append({
                "cusip": cusip,
                "company_name": company_name,
                "ticker": ticker,
                "current_value": current_data["market_value"],
                "previous_value": previous_data["market_value"],
                "weight_current": weight_current,
                "weight_previous": weight_previous,
                "weight_change": weight_change,
                "status": status
            })
        
        print(f"  ✅ Analyzed {len(results)} unique positions")
        return results
    
    def generate_tables(self, analysis_data: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Generate the three required tables from analysis data
        
        Args:
            analysis_data: List of position analysis dictionaries
            
        Returns:
            Tuple of (top_holdings, top_buys, top_sells)
        """
        print("📋 Generating analysis tables...")
        
        # Table 1: Top 20 Holdings by current portfolio weight
        top_holdings = sorted(
            analysis_data, 
            key=lambda x: x["weight_current"], 
            reverse=True
        )[:20]
        
        # Table 2: Top 20 Buys (largest positive weight changes)
        buys = [item for item in analysis_data if item["weight_change"] > 0]
        top_buys = sorted(buys, key=lambda x: x["weight_change"], reverse=True)[:20]
        
        # Table 3: Top 20 Sells (largest negative weight changes)
        sells = [item for item in analysis_data if item["weight_change"] < 0]
        top_sells = sorted(sells, key=lambda x: x["weight_change"])[:20]  # Most negative first
        
        print(f"  📈 Top Holdings: {len(top_holdings)} entries")
        print(f"  📈 Top Buys: {len(top_buys)} entries") 
        print(f"  📉 Top Sells: {len(top_sells)} entries")
        
        return top_holdings, top_buys, top_sells
    
    def print_table(self, title: str, data: List[Dict], table_type: str = "holdings"):
        """
        Print a formatted table to console
        
        Args:
            title: Table title
            data: List of data dictionaries
            table_type: Type of table ("holdings", "buys", or "sells")
        """
        print(f"\n{title}")
        print("=" * len(title))
        
        if table_type == "holdings":
            print(f"{'Rank':<4} {'Company (Ticker)':<40} {'% Portfolio':>12} {'Change':>10} {'Status':>8}")
            print("-" * 84)
            for i, row in enumerate(data, 1):
                company_display = f"{row['company_name'][:30]} ({row['ticker']})"
                print(f"{i:<4} {company_display:<40} {row['weight_current']:>11.2f}% {row['weight_change']:>9.2f}% {row['status']:>8}")
        
        elif table_type == "buys":
            print(f"{'Rank':<4} {'Company (Ticker)':<40} {'% Portfolio':>12} {'Increase':>10} {'Status':>8}")
            print("-" * 84)
            for i, row in enumerate(data, 1):
                company_display = f"{row['company_name'][:30]} ({row['ticker']})"
                print(f"{i:<4} {company_display:<40} {row['weight_current']:>11.2f}% {row['weight_change']:>9.2f}% {row['status']:>8}")
        
        elif table_type == "sells":
            print(f"{'Rank':<4} {'Company (Ticker)':<40} {'% Portfolio':>12} {'Decrease':>10} {'Status':>8}")
            print("-" * 84)
            for i, row in enumerate(data, 1):
                company_display = f"{row['company_name'][:30]} ({row['ticker']})"
                print(f"{i:<4} {company_display:<40} {row['weight_current']:>11.2f}% {row['weight_change']:>9.2f}% {row['status']:>8}")
    
    def export_to_csv(self, top_holdings: List[Dict], top_buys: List[Dict], 
                     top_sells: List[Dict], filename_prefix: str = "13f_analysis"):
        """
        Export analysis results to CSV files
        
        Args:
            top_holdings: Top holdings data
            top_buys: Top buys data  
            top_sells: Top sells data
            filename_prefix: Prefix for output filenames
        """
        print(f"\n💾 Exporting results to CSV...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export top holdings
        if top_holdings:
            df_holdings = pd.DataFrame(top_holdings)
            holdings_file = f"{filename_prefix}_holdings_{timestamp}.csv"
            df_holdings.to_csv(holdings_file, index=False)
            print(f"  ✅ Saved: {holdings_file}")
        
        # Export top buys
        if top_buys:
            df_buys = pd.DataFrame(top_buys)
            buys_file = f"{filename_prefix}_buys_{timestamp}.csv"
            df_buys.to_csv(buys_file, index=False)
            print(f"  ✅ Saved: {buys_file}")
        
        # Export top sells
        if top_sells:
            df_sells = pd.DataFrame(top_sells)
            sells_file = f"{filename_prefix}_sells_{timestamp}.csv"
            df_sells.to_csv(sells_file, index=False)
            print(f"  ✅ Saved: {sells_file}")
    
    def analyze_institution(self, cik: str, export_csv: bool = True) -> Dict:
        """
        Complete analysis workflow for an institution
        
        This is the main method that orchestrates the entire analysis:
        1. Discovers recent 13F filings
        2. Downloads and parses XML data
        3. Calculates portfolio changes
        4. Generates analysis tables
        5. Displays results and optionally exports to CSV
        
        Args:
            cik: Institution's Central Index Key
            export_csv: Whether to export results to CSV files
            
        Returns:
            Dictionary containing all analysis results
        """
        print(f"\n🎯 Starting 13F Analysis for CIK: {cik}")
        print("="*60)
        
        try:
            # Step 1: Find recent filings
            current_accession, previous_accession = self.get_recent_13f_filings(cik)
            
            # Add delay to be respectful to SEC servers
            time.sleep(0.1)
            
            # Step 2: Download XML data
            current_xml = self.fetch_13f_xml(cik, current_accession)
            if not current_xml:
                raise Exception("Could not fetch current quarter XML")
            
            time.sleep(0.1)
            
            previous_xml = self.fetch_13f_xml(cik, previous_accession)
            if not previous_xml:
                raise Exception("Could not fetch previous quarter XML")
            
            # Step 3: Parse XML data
            current_holdings = self.parse_13f_xml(current_xml)
            previous_holdings = self.parse_13f_xml(previous_xml)
            
            if not current_holdings:
                raise Exception("No current holdings data found")
            
            # Step 4: Calculate changes
            analysis_data = self.calculate_portfolio_changes(current_holdings, previous_holdings)
            
            # Step 5: Generate tables
            top_holdings, top_buys, top_sells = self.generate_tables(analysis_data)
            
            # Step 6: Display results
            self.print_table("📊 TOP 20 HOLDINGS", top_holdings, "holdings")
            self.print_table("📈 TOP 20 BUYS", top_buys, "buys")
            self.print_table("📉 TOP 20 SELLS", top_sells, "sells")
            
            # Step 7: Export if requested
            if export_csv:
                self.export_to_csv(top_holdings, top_buys, top_sells, f"cik_{cik}")
            
            # Return results
            results = {
                "cik": cik,
                "current_accession": current_accession,
                "previous_accession": previous_accession,
                "top_holdings": top_holdings,
                "top_buys": top_buys,
                "top_sells": top_sells,
                "analysis_data": analysis_data
            }
            
            print(f"\n✅ Analysis completed successfully!")
            return results
            
        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            raise


def main():
    """
    Main execution function with example usage
    """
    # Initialize analyzer with SEC-compliant user agent
    # NOTE: Replace with your actual email address for SEC compliance
    analyzer = SEC13FAnalyzer("Investment Research analysis@example.com")
    
    # Berkshire Hathaway CIK
    berkshire_cik = "0001067983"
    
    try:
        # Run complete analysis
        results = analyzer.analyze_institution(berkshire_cik, export_csv=True)
        
        print(f"\n📋 Analysis Summary:")
        print(f"Current filing: {results['current_accession']}")
        print(f"Previous filing: {results['previous_accession']}")
        print(f"Total positions analyzed: {len(results['analysis_data'])}")
        
        # You can also analyze other institutions by changing the CIK
        # For example:
        # - Warren Buffett's Berkshire Hathaway: "0001067983"
        # - Bill & Melinda Gates Foundation Trust: "0001166559"  
        # - Vanguard Group: "0000102909"
        
    except Exception as e:
        print(f"Error in analysis: {e}")


if __name__ == "__main__":
    main()
