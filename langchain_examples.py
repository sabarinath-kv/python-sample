"""
LangChain Examples for Company Contact Finder API
==================================================

This script demonstrates how LangChain is used in this application.
Run these examples to understand the LangChain components.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY")
)


def example_1_simple_chain():
    """Example 1: Simple LangChain chain with string output"""
    print("\n=== Example 1: Simple Chain ===")
    
    # Create a prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("user", "Tell me about {company_name} in one sentence.")
    ])
    
    # Create a chain using LCEL (LangChain Expression Language)
    chain = prompt | llm | StrOutputParser()
    
    # Invoke the chain
    result = chain.invoke({"company_name": "OpenAI"})
    print(f"Result: {result}")


def example_2_json_output():
    """Example 2: Chain with JSON output parser"""
    print("\n=== Example 2: JSON Output Parser ===")
    
    # Create prompt for JSON output
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Return valid JSON only."),
        ("user", """Generate contact information for a fictional company: {company_name}
        
Return JSON with keys: "emails" (list of 2-3 emails) and "phones" (list of 1-2 phone numbers).""")
    ])
    
    # Create chain with JSON parser
    json_parser = JsonOutputParser()
    chain = prompt | llm | json_parser
    
    # Invoke
    result = chain.invoke({"company_name": "Acme Corp"})
    print(f"Parsed JSON: {result}")
    print(f"Type: {type(result)}")


def example_3_web_loader():
    """Example 3: Using WebBaseLoader to scrape content"""
    print("\n=== Example 3: Web Scraping with LangChain ===")
    
    try:
        # Load web content
        url = "https://www.example.com"
        loader = WebBaseLoader(url)
        documents = loader.load()
        
        print(f"Loaded {len(documents)} document(s)")
        if documents:
            print(f"First 200 chars: {documents[0].page_content[:200]}...")
            
        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        chunks = text_splitter.split_documents(documents)
        print(f"Split into {len(chunks)} chunks")
        
    except Exception as e:
        print(f"Error: {e}")


def example_4_complex_chain():
    """Example 4: Multi-step analysis chain"""
    print("\n=== Example 4: Complex Analysis Chain ===")
    
    # Create a multi-turn conversation chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a business analyst AI."),
        ("user", """Analyze {company_name} and provide:
1. Industry
2. Main products/services
3. Target market

Format as JSON with keys: industry, products, target_market""")
    ])
    
    # Chain with JSON output
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({"company_name": "Tesla"})
        print(f"Analysis: {result}")
    except Exception as e:
        print(f"Error (trying with fallback): {e}")
        # Fallback to string parser
        chain_fallback = prompt | llm | StrOutputParser()
        result = chain_fallback.invoke({"company_name": "Tesla"})
        print(f"Fallback result: {result}")


def example_5_custom_prompt_template():
    """Example 5: Reusable prompt templates"""
    print("\n=== Example 5: Reusable Prompt Template ===")
    
    # Create a reusable template
    website_finder_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at finding company websites. Return only the URL."),
        ("user", """Find the official website for:
Company: {company_name}
Domain hint: {domain}
Description: {description}

Return only the URL in format: https://www.example.com""")
    ])
    
    # Create chain
    chain = website_finder_template | llm | StrOutputParser()
    
    # Use it multiple times with different inputs
    companies = [
        {"company_name": "Microsoft", "domain": "microsoft.com", "description": "Tech company"},
        {"company_name": "Apple", "domain": "apple.com", "description": "Consumer electronics"},
    ]
    
    for company in companies:
        result = chain.invoke(company)
        print(f"{company['company_name']}: {result}")


def main():
    """Run all examples"""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in environment")
        print("Please set it in .env file to run these examples")
        return
    
    print("🦜 LangChain Examples for Company Contact Finder API")
    print("=" * 60)
    
    try:
        example_1_simple_chain()
        example_2_json_output()
        example_3_web_loader()
        example_4_complex_chain()
        example_5_custom_prompt_template()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed!")
        print("\nThese examples show how LangChain is used in app.py:")
        print("- Prompt templates for reusable AI prompts")
        print("- Output parsers for structured responses")
        print("- Web loaders for intelligent scraping")
        print("- LCEL chains for composable workflows")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure your OPENAI_API_KEY is valid and you have internet access")


if __name__ == "__main__":
    main()

