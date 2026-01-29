#!/usr/bin/env python3
"""
Test script for the Company Contact Finder API with LangChain
Run this after starting your server: uvicorn app:app --reload
"""

import requests
import json
from typing import Dict, Any

# Base URL - change if deployed
BASE_URL = "http://localhost:8000"

def test_company_address(params: Dict[str, Any]):
    """Test the /company-address endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing with: {params['company_name']}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.get(
            f"{BASE_URL}/company-address",
            params=params,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2))
        
        return response.json()
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server.")
        print("Make sure the server is running: uvicorn app:app --reload")
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_analyze_company(params: Dict[str, Any]):
    """Test the /analyze-company endpoint (LangChain-powered)"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {params['company_name']}")
    print(f"Analysis Type: {params.get('analysis_type', 'summary')}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.get(
            f"{BASE_URL}/analyze-company",
            params=params,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        result = response.json()
        
        # Pretty print with limited analysis length
        if 'analysis' in result and len(result['analysis']) > 300:
            display_result = result.copy()
            display_result['analysis'] = result['analysis'][:300] + "...\n[truncated]"
            print(json.dumps(display_result, indent=2))
        else:
            print(json.dumps(result, indent=2))
        
        return result
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server.")
        print("Make sure the server is running: uvicorn app:app --reload")
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out.")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run test cases"""
    
    print("🦜 Company Contact Finder API - LangChain Test Suite")
    print("=" * 60)
    
    # Test Case 1: Company with domain
    test_cases = [
        {
            "company_name": "Stripe",
            "company_domain": "stripe.com",
            "industry": "Financial Technology",
            "location": "San Francisco, CA"
        },
        {
            "company_name": "Vercel",
            "company_domain": "vercel.com",
            "industry": "Web Development",
            "location": "San Francisco, CA",
            "company_description": "Platform for frontend developers"
        },
        {
            "company_name": "Anthropic",
            "company_domain": "anthropic.com",
            "industry": "AI Research",
            "location": "San Francisco, CA"
        }
    ]
    
    print("\n📋 Running test cases...")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n🧪 Test Case {i}/{len(test_cases)}")
        result = test_company_address(test_case)
        
        if result:
            print(f"\n✅ Found {len(result.get('email_addresses', []))} emails")
            print(f"✅ Found {len(result.get('phone_numbers', []))} phone numbers")
    
    # Test the new LangChain-powered analysis endpoint
    print("\n\n🦜 Testing LangChain Analysis Endpoint")
    print("=" * 60)
    
    analysis_tests = [
        {
            "company_name": "OpenAI",
            "company_domain": "openai.com",
            "analysis_type": "summary"
        },
        {
            "company_name": "Anthropic",
            "company_domain": "anthropic.com",
            "analysis_type": "contacts"
        },
        {
            "company_name": "LangChain",
            "company_domain": "langchain.com",
            "analysis_type": "full"
        }
    ]
    
    for i, test_case in enumerate(analysis_tests, 1):
        print(f"\n\n🧪 Analysis Test {i}/{len(analysis_tests)}")
        result = test_analyze_company(test_case)
        
        if result and result.get('status') == 'success':
            print(f"\n✅ Analysis completed successfully")
            print(f"✅ Powered by: {result.get('powered_by', 'LangChain')}")
    
    print(f"\n\n{'='*60}")
    print("✅ All tests complete!")
    print(f"{'='*60}\n")
    print("\n📚 Learn more about LangChain integration:")
    print("   - Read LANGCHAIN_GUIDE.md")
    print("   - Run: python langchain_examples.py")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

