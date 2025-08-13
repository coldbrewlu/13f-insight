#!/usr/bin/env python3
"""
使用SEC官方API探索filing结构，找到13F信息表XML文件
"""

import requests
import json
import time

def get_filing_documents_via_api(cik, accession_number):
    """
    使用SEC官方submissions API获取filing的所有文档
    """
    print(f"🔍 使用SEC API探索filing文档: {accession_number}")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    # 格式化CIK为10位数字
    cik_padded = f"{int(cik):010d}"
    api_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    
    try:
        print(f"📡 调用SEC submissions API...")
        response = session.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # 在submissions中查找指定的accession number
        recent_filings = data.get("filings", {}).get("recent", {})
        accession_numbers = recent_filings.get("accessionNumber", [])
        
        if accession_number not in accession_numbers:
            print(f"❌ 在API响应中未找到 {accession_number}")
            return None
        
        # 找到对应的索引
        filing_index = accession_numbers.index(accession_number)
        
        # 获取该filing的信息
        filing_info = {
            "accessionNumber": recent_filings["accessionNumber"][filing_index],
            "filingDate": recent_filings["filingDate"][filing_index],
            "form": recent_filings["form"][filing_index],
            "primaryDocument": recent_filings.get("primaryDocument", [None] * len(accession_numbers))[filing_index],
            "primaryDocDescription": recent_filings.get("primaryDocDescription", [None] * len(accession_numbers))[filing_index]
        }
        
        print(f"✅ 找到filing信息:")
        print(f"   表单类型: {filing_info['form']}")
        print(f"   提交日期: {filing_info['filingDate']}")
        print(f"   主要文档: {filing_info['primaryDocument']}")
        print(f"   文档描述: {filing_info['primaryDocDescription']}")
        
        return filing_info
        
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        return None

def explore_filing_directory_structure(cik, accession_number):
    """
    探索filing目录的index文件，获取所有可用文档
    """
    print(f"\n🗂️  探索filing目录结构...")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    accession_clean = accession_number.replace('-', '')
    
    # 尝试访问JSON格式的index文件
    index_urls = [
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession_number}-index.json",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/index.json",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession_number}-index.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/index.xml"
    ]
    
    for url in index_urls:
        try:
            print(f"📄 尝试: {url}")
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ 成功获取index文件!")
                
                if url.endswith('.json'):
                    try:
                        index_data = response.json()
                        print(f"📋 JSON格式index文件内容:")
                        print(json.dumps(index_data, indent=2))
                        return index_data
                    except:
                        print(f"📄 JSON解析失败，显示原始内容:")
                        print(response.text[:1000])
                else:
                    print(f"📄 XML/HTML格式index文件内容:")
                    print(response.text[:1000])
                    print("...")
                
                return response.text
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(0.1)
    
    return None

def try_alternative_xml_patterns(cik, accession_number):
    """
    基于常见模式尝试可能的XML文件位置
    """
    print(f"\n🎯 尝试替代XML文件模式...")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    accession_clean = accession_number.replace('-', '')
    
    # 基于研究的常见模式
    xml_patterns = [
        # 标准模式
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/form13fInfoTable.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.xml",
        
        # 可能的HTML格式（有些13F以HTML形式存储）
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/form13fInfoTable.htm",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.htm",
        
        # 基于accession number的模式
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession_number.replace('-', '')}.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession_number}.xml",
        
        # 数字文件名模式
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/1.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/2.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/doc1.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/doc2.xml",
        
        # 子目录模式
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/xslForm13F_X01/form13fInfoTable.xml",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/Tables/InfoTable.xml",
        
        # TXT格式（可能是纯文本格式）
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.txt",
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/form13fInfoTable.txt",
    ]
    
    found_files = []
    
    for url in xml_patterns:
        try:
            print(f"🔍 测试: {url}")
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                content = response.text
                
                # 检查内容是否像13F信息表
                indicators = ['nameofissuer', 'cusip', 'shrsornramt', 'infotable', 'value']
                found_indicators = [ind for ind in indicators if ind in content.lower()]
                
                print(f"✅ 找到文件! 大小: {len(content):,} 字符")
                print(f"🎯 13F指标: {found_indicators}")
                
                if len(found_indicators) >= 2:
                    print(f"🎉 可能是13F信息表!")
                    found_files.append({
                        'url': url,
                        'size': len(content),
                        'indicators': found_indicators,
                        'content_preview': content[:500]
                    })
                
                # 显示内容预览
                print(f"📄 内容预览:")
                print(content[:300])
                print("...")
                
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(0.1)  # 避免过快请求
    
    return found_files

def comprehensive_filing_analysis(cik="1067983"):
    """
    对伯克希尔的历史filing进行全面分析
    """
    print("🎯 SEC 13F历史文件全面分析")
    print("="*60)
    
    # 要分析的历史filing
    target_filings = [
        "0000950123-25-002701",  # 2025-02-14 (最近的问题filing)
        "0000950123-24-011775",  # 2024-11-14
        "0000950123-24-008740",  # 2024-08-14
    ]
    
    all_results = {}
    
    for accession in target_filings:
        print(f"\n{'='*80}")
        print(f"分析 filing: {accession}")
        print(f"{'='*80}")
        
        # 方法1: 使用SEC官方API
        filing_info = get_filing_documents_via_api(cik, accession)
        
        # 方法2: 探索目录结构
        index_info = explore_filing_directory_structure(cik, accession)
        
        # 方法3: 尝试常见XML模式
        found_xml_files = try_alternative_xml_patterns(cik, accession)
        
        # 汇总结果
        all_results[accession] = {
            'filing_info': filing_info,
            'index_info': index_info,
            'xml_files': found_xml_files
        }
        
        # 如果找到XML文件，记录成功模式
        if found_xml_files:
            print(f"\n🎉 在 {accession} 中找到 {len(found_xml_files)} 个可能的13F文件!")
            for file_info in found_xml_files:
                print(f"   📁 {file_info['url']}")
                print(f"      大小: {file_info['size']:,} 字符")
                print(f"      指标: {file_info['indicators']}")
        
        print(f"\n⏳ 等待1秒避免过快请求...")
        time.sleep(1)
    
    # 分析结果，寻找模式
    print(f"\n{'='*80}")
    print(f"分析总结")
    print(f"{'='*80}")
    
    successful_patterns = []
    for accession, results in all_results.items():
        if results['xml_files']:
            for xml_file in results['xml_files']:
                # 提取URL模式
                url = xml_file['url']
                pattern = url.split(f"/{accession.replace('-', '')}/")[-1]
                successful_patterns.append({
                    'pattern': pattern,
                    'accession': accession,
                    'url': url,
                    'indicators': xml_file['indicators']
                })
    
    if successful_patterns:
        print(f"✅ 发现 {len(successful_patterns)} 个成功模式:")
        for i, pattern_info in enumerate(successful_patterns, 1):
            print(f"  {i}. 模式: {pattern_info['pattern']}")
            print(f"     在filing: {pattern_info['accession']}")
            print(f"     完整URL: {pattern_info['url']}")
            print(f"     指标匹配: {pattern_info['indicators']}")
            print()
        
        # 返回最有希望的模式
        return successful_patterns[0]['pattern']
    else:
        print(f"❌ 未找到任何成功的13F XML文件模式")
        return None

if __name__ == "__main__":
    successful_pattern = comprehensive_filing_analysis()
    
    if successful_pattern:
        print(f"🎯 建议更新分析器使用此模式: {successful_pattern}")
    else:
        print(f"🔍 可能需要尝试其他方法或分析不同的机构")