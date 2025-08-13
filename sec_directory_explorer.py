#!/usr/bin/env python3
"""
SEC Directory Explorer - 分析SEC filing目录结构找到XML文件
"""

import requests
import re
from bs4 import BeautifulSoup
import time

def explore_sec_filing_directory(accession_number, cik="1067983"):
    """
    探索SEC filing目录，找到所有可用文件
    """
    print(f"🔍 探索SEC filing目录: {accession_number}")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    # SEC filing目录的index页面
    accession_clean = accession_number.replace('-', '')
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession_number}-index.htm"
    
    try:
        print(f"📄 访问index页面: {index_url}")
        response = session.get(index_url, timeout=30)
        
        if response.status_code == 200:
            # 解析HTML找到所有文件链接
            soup = BeautifulSoup(response.content, 'html.parser')
            
            print(f"✅ 成功获取index页面")
            print(f"📄 页面内容预览:")
            print(response.text[:1000])
            print("...")
            
            # 查找所有文件链接
            links = soup.find_all('a', href=True)
            xml_files = []
            all_files = []
            
            for link in links:
                href = link.get('href')
                if href and not href.startswith('http'):
                    filename = href.split('/')[-1]
                    all_files.append(filename)
                    
                    if filename.endswith('.xml'):
                        xml_files.append(filename)
            
            print(f"\n📁 发现的所有文件 ({len(all_files)}个):")
            for i, filename in enumerate(all_files, 1):
                file_type = "📄 XML" if filename.endswith('.xml') else "📄 其他"
                print(f"  {i:2d}. {file_type} {filename}")
            
            print(f"\n🎯 XML文件 ({len(xml_files)}个):")
            for i, filename in enumerate(xml_files, 1):
                print(f"  {i}. {filename}")
            
            return xml_files, all_files
            
        else:
            print(f"❌ HTTP {response.status_code}")
            
            # 尝试alternative URLs
            alt_urls = [
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/",
                f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{cik}/{accession_clean}/{accession_number}.htm"
            ]
            
            for alt_url in alt_urls:
                print(f"🔄 尝试备用URL: {alt_url}")
                alt_response = session.get(alt_url, timeout=30)
                if alt_response.status_code == 200:
                    print(f"✅ 备用URL成功!")
                    print(alt_response.text[:500])
                    break
            
            return [], []
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return [], []

def test_xml_files(accession_number, xml_files, cik="1067983"):
    """
    测试发现的XML文件，看哪个是13F信息表
    """
    if not xml_files:
        print("⚠️ 没有发现XML文件")
        return None
    
    print(f"\n🧪 测试XML文件内容...")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    accession_clean = accession_number.replace('-', '')
    found_info_table = None
    
    for filename in xml_files:
        print(f"\n📄 测试文件: {filename}")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{filename}"
        
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                content = response.text
                
                # 检查是否为13F信息表
                indicators = [
                    'nameofissuer', 'cusip', 'shrsornramt', 'infotable',
                    'informationtable', 'thirteenf', '13f'
                ]
                
                found_indicators = []
                for indicator in indicators:
                    if indicator in content.lower():
                        found_indicators.append(indicator)
                
                print(f"  📊 文件大小: {len(content):,} 字符")
                print(f"  🎯 13F指标: {found_indicators}")
                
                if len(found_indicators) >= 3:  # 如果包含多个13F指标
                    print(f"  ✅ 可能是13F信息表!")
                    found_info_table = filename
                    
                    # 显示内容预览
                    print(f"  📄 内容预览:")
                    print(f"    {content[:300]}...")
                    
                else:
                    print(f"  ❌ 不像13F信息表")
                    
            else:
                print(f"  ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        
        time.sleep(0.1)  # 避免过快请求
    
    return found_info_table

def main():
    """
    主函数：探索伯克希尔的历史13F filing
    """
    print("🎯 SEC 13F历史文件探索器")
    print("="*50)
    
    # 要探索的历史filing
    historical_filings = [
        "0000950123-25-002701",  # 2025-02-14
        "0000950123-24-011775",  # 2024-11-14  
        "0000950123-24-008740",  # 2024-08-14
        "0000950123-24-005664",  # 2024-05-15 (amended)
    ]
    
    cik = "1067983"  # 伯克希尔
    
    for accession in historical_filings:
        print(f"\n{'='*60}")
        print(f"探索filing: {accession}")
        print(f"{'='*60}")
        
        # 步骤1：探索目录结构
        xml_files, all_files = explore_sec_filing_directory(accession, cik)
        
        # 步骤2：测试XML文件
        if xml_files:
            info_table_file = test_xml_files(accession, xml_files, cik)
            
            if info_table_file:
                print(f"\n🎉 找到13F信息表: {info_table_file}")
                print(f"完整URL:")
                accession_clean = accession.replace('-', '')
                full_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{info_table_file}"
                print(f"  {full_url}")
                
                # 这个URL模式可以用于更新分析器
                return accession, info_table_file
        
        print(f"\n⏳ 等待1秒避免过快请求...")
        time.sleep(1)
    
    print(f"\n❌ 未在任何历史filing中找到13F信息表")
    return None, None

if __name__ == "__main__":
    found_accession, found_filename = main()
    
    if found_filename:
        print(f"\n✅ 成功！可以用这个模式更新分析器:")
        print(f"   文件模式: {found_filename}")
        print(f"   应用到其他filing")