#!/usr/bin/env python3
"""
快速13F文件查找器 - 测试最可能的文件格式和位置
"""

import requests
import time

def quick_test_13f_formats(cik="1067983", accession="0000950123-25-002701"):
    """
    快速测试13F可能的文件格式
    重点测试: HTML, XML, TXT 三种格式
    """
    print(f"测试13F文件格式")
    print(f"CIK: {cik}, Accession: {accession}")
    print("="*50)
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Investment Research analysis@example.com'})
    
    accession_clean = accession.replace('-', '')
    
    # 最有可能的文件模式（基于SEC惯例）
    test_patterns = [
        # HTML格式（很多13F用这种格式）
        ("HTML表格", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/form13fInfoTable.htm"),
        ("HTML表格2", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.htm"),
        ("HTML主文档", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession}.htm"),
        
        # XML格式
        ("XML表格", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/form13fInfoTable.xml"),
        ("XML表格2", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.xml"),
        
        # TXT格式（旧系统）
        ("TXT主文档", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession}.txt"),
        ("TXT表格", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/InfoTable.txt"),
        
        # 数字命名
        ("文档1 HTML", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/1.htm"),
        ("文档2 HTML", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/2.htm"),
        ("文档1 XML", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/1.xml"),
        ("文档2 XML", f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/2.xml"),
    ]
    
    found_files = []
    
    for name, url in test_patterns:
        try:
            print(f"🔍 {name:<15}: ", end="")
            response = session.get(url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # 检查13F特征
                indicators = {
                    'nameofissuer': 'nameofissuer' in content.lower(),
                    'cusip': 'cusip' in content.lower(), 
                    'shares': any(word in content.lower() for word in ['shares', 'shrsornramt']),
                    'value': 'value' in content.lower(),
                    'infotable': 'infotable' in content.lower()
                }
                
                score = sum(indicators.values())
                
                if score >= 3:
                    print(f"✅ 可能是13F! (评分: {score}/5)")
                    print(f"    大小: {len(content):,} 字符")
                    print(f"    指标: {[k for k, v in indicators.items() if v]}")
                    
                    found_files.append({
                        'name': name,
                        'url': url,
                        'size': len(content),
                        'score': score,
                        'indicators': indicators,
                        'preview': content[:200].replace('\n', ' ')[:100]
                    })
                elif score >= 1:
                    print(f"⚠️  部分匹配 (评分: {score}/5)")
                else:
                    print(f"❌ 不匹配")
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ 错误: {str(e)[:30]}")
        
        time.sleep(0.1)
    
    # 显示结果
    if found_files:
        print(f"\n 找到 {len(found_files)} 个可能的13F文件:")
        for i, file_info in enumerate(sorted(found_files, key=lambda x: x['score'], reverse=True), 1):
            print(f"\n{i}. {file_info['name']} (评分: {file_info['score']}/5)")
            print(f"   URL: {file_info['url']}")
            print(f"   大小: {file_info['size']:,} 字符")
            print(f"   预览: {file_info['preview']}...")
        
        # 返回最佳匹配
        best_match = max(found_files, key=lambda x: x['score'])
        return best_match
    else:
        print(f"\n❌ 未找到任何13F文件")
        return None

def test_multiple_filings():
    """
    测试多个filing查找通用模式
    """
    print(f"\n 测试多个filing寻找通用模式...")
    
    test_filings = [
        ("2025-02-14", "0000950123-25-002701"),
        ("2024-11-14", "0000950123-24-011775"), 
        ("2024-08-14", "0000950123-24-008740"),
    ]
    
    results = {}
    
    for date, accession in test_filings:
        print(f"\n{'='*50}")
        print(f"测试 {date} ({accession})")
        print(f"{'='*50}")
        
        result = quick_test_13f_formats("1067983", accession)
        if result:
            results[accession] = result
            print(f"✅ {date}: 找到文件")
        else:
            print(f"❌ {date}: 未找到文件")
        
        time.sleep(1)
    
    # 分析模式
    if results:
        print(f"\n 模式分析:")
        patterns = {}
        for accession, result in results.items():
            # 提取文件名模式
            filename = result['url'].split('/')[-1]
            if filename in patterns:
                patterns[filename] += 1
            else:
                patterns[filename] = 1
        
        print(f"发现的文件名模式:")
        for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pattern}: 出现 {count} 次")
        
        return list(patterns.keys())[0] if patterns else None
    else:
        return None

if __name__ == "__main__":
    print(" 13F文件快速查找器")
    print("="*40)
    
    # 测试单个filing
    result = quick_test_13f_formats()
    
    if result:
        print(f"\n✅ 建议使用这个文件:")
        print(f"   类型: {result['name']}")
        print(f"   URL: {result['url']}")
        
        # 提取可用的URL模式
        url_parts = result['url'].split('/')
        filename = url_parts[-1]
        print(f"   文件名模式: {filename}")
        print(f"\n 可以尝试将分析器更新为使用此模式")
    else:
        # 如果单个测试失败，尝试多个
        print(f"\n 单个测试失败，尝试多个filing...")
        common_pattern = test_multiple_filings()
        
        if common_pattern:
            print(f"\n✅ 发现通用模式: {common_pattern}")
        else:
            print(f"\n❌ 所有测试都失败了")
            print(f" 建议:")
            print(f"   1. 检查网络连接")
            print(f"   2. 尝试不同的CIK (其他机构)")
            print(f"   3. 考虑使用第三方数据源")