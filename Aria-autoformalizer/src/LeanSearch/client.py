import json
import requests
import yaml
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional


def load_config(config_path: str = "configs/leansearch.yaml") -> Dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

async def std_search_remote(queries: List[str], num_results: Optional[int] = None, config_path: str = "configs/leansearch.yaml") -> List[List[Dict[str, Any]]]:
    config = load_config(config_path)
    std_search_config = config['std_search_remote']
    request_data = {
        "query": queries,
        "num_results": num_results if num_results is not None else std_search_config['num_results']
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 使用 async with session.post 发送异步请求
            async with session.post(
                std_search_config['base_url'],
                headers={'Content-Type': 'application/json'},
                json=request_data,
                timeout=30
            ) as response:
                # 检查 HTTP 响应状态码，如果失败则会引发异常
                response.raise_for_status()
                
                # response.json() 是一个协程，需要 await
                results = await response.json()
                return results
        
        # 捕获 aiohttp 的客户端错误
        except aiohttp.ClientError as e:
            print(f"Network request failed: {e}")
            raise
        # 也可以捕获其他可能的异常，例如 asyncio.TimeoutError
        except asyncio.TimeoutError:
            print(f"Request timed out after 30 seconds.")
            raise

if __name__ == "__main__":
    def format_search_results(queries: List[str], results: List[List[Dict[str, Any]]]) -> str:
        output_lines = []
        
        for i, (query, query_results) in enumerate(zip(queries, results)):
            output_lines.append(f"\n=== Query {i+1}: {query} ===")
                
            for j, result in enumerate(query_results):
                result_data = result.get('result', {})
                distance = result.get('distance', 0.0)
                
                name = result_data.get('name', 'Unknown')
                kind = result_data.get('kind', 'Unknown type')
                type = result_data.get('type', 'Unknown type')
                informal_name = result_data.get('informal_name', '')
                informal_description = result_data.get('informal_description', '')
                signature = result_data.get('signature', '')
                
                output_lines.append(f"\nResult {j+1} (distance: {distance:.4f}):")
                output_lines.append(f"  Name: {name}")
                output_lines.append(f"  Kind: {kind}")
                output_lines.append(f"  Type: {type}")
                if informal_name:
                    output_lines.append(f"  Informal name: {informal_name}")
                if informal_description:
                    output_lines.append(f"  Description: {informal_description}")
                if signature:
                    output_lines.append(f"  Signature: {signature}")
        
        return '\n'.join(output_lines)

    test_queries = [
        "rank-nullity theorem",
        "finite integral domain is a field"
    ]
    try:
        results = std_search_remote(test_queries, num_results=2)
        formatted_results = format_search_results(test_queries, results)
        print(formatted_results)
    except Exception as e:
        print(f"Test failed: {e}")