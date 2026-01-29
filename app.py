from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import re
import requests
from bs4 import BeautifulSoup
import json
from dotenv import load_dotenv
import time
import logging

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

# Configure logging for AI activities
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Company Contact Finder API", version="2.0.0")

# Initialize LangChain LLM (supports both OpenAI and LiteLLM)
openai_api_key = os.getenv("OPENAI_API_KEY")
litellm_base_url = os.getenv("LITELLM_BASE_URL")
model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")  # Default model

if openai_api_key:
    if litellm_base_url:
        # Using LiteLLM proxy
        llm = ChatOpenAI(
            model=model_name,
            temperature=0.3,
            api_key=openai_api_key,
            base_url=litellm_base_url
        )
    else:
        # Using OpenAI directly
        llm = ChatOpenAI(
            model=model_name,
            temperature=0.3,
            api_key=openai_api_key
        )
else:
    llm = None

# Response Models
class ContactInfo(BaseModel):
    email_addresses: List[str] = Field(default_factory=list, description="List of found email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="List of found phone numbers")
    website_url: Optional[str] = Field(None, description="Company website URL")
    company_name: str = Field(..., description="Company name")
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Additional scraped information")
    status: str = Field("success", description="Status of the request")
    message: Optional[str] = Field(None, description="Additional message or error information")

# Helper Functions
def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    # Filter out common non-contact emails
    filtered_emails = [
        email for email in emails 
        if not any(x in email.lower() for x in ['example.com', 'sentry.io', 'mailto:', 'wixpress.com', 'schema.org'])
    ]
    return list(set(filtered_emails))

def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text"""
    # Various phone number patterns (ordered by specificity)
    patterns = [
        # International format with country code (e.g., +919447703636, +91 9447703636, +1-555-123-4567)
        r'\+\d{1,4}[\s.-]?\d{6,14}',  # Simple international: +CC followed by 6-14 digits
        r'\+\d{1,4}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,9}',  # International with separators
        # US/Canada format
        r'\b1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',  # (xxx) xxx-xxxx or xxx-xxx-xxxx
        # Basic format without country code
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # xxx-xxx-xxxx
        r'\b\d{10,15}\b'  # 10-15 consecutive digits
    ]
    
    phone_numbers = []
    matched_positions = set()  # Track positions to avoid duplicate matches
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            # Check if this position was already matched by a previous pattern
            if not any(start < pos < end or pos < start < pos_end for pos, pos_end in matched_positions):
                phone_numbers.append(match.group())
                matched_positions.add((start, end))
    
    # Clean and deduplicate
    cleaned_numbers = []
    for num in phone_numbers:
        # Remove extra spaces and normalize
        cleaned = re.sub(r'\s+', ' ', num).strip()
        digit_count = len(re.sub(r'\D', '', cleaned))
        # Accept numbers with at least 10 digits (or 7+ if it has country code)
        if digit_count >= 10 or (cleaned.startswith('+') and digit_count >= 7):
            cleaned_numbers.append(cleaned)
    
    return list(set(cleaned_numbers))

def find_company_website_with_ai(company_name: str, company_domain: Optional[str], 
                                  company_description: Optional[str], 
                                  linkedin_url: Optional[str]) -> Optional[str]:
    """Use LangChain to determine the most likely company website"""
    if not llm:
        # Fallback: construct from domain or search manually
        if company_domain:
            return f"https://www.{company_domain}" if not company_domain.startswith('http') else company_domain
        return None
    
    try:
        # Create a LangChain prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that identifies company websites. Return only the URL, nothing else."),
            ("user", """Given the following company information, determine the most likely official website URL:
        
Company Name: {company_name}
Company Domain: {company_domain}
Company Description: {company_description}
LinkedIn URL: {linkedin_url}

Based on this information, provide ONLY the most likely official website URL. 
If a domain is provided, construct the full URL from it.
Return only the URL, nothing else. Format: https://www.example.com""")
        ])
        
        # Create a chain with output parser
        chain = prompt_template | llm | StrOutputParser()
        
        # Log AI request
        logger.info(f"[AI_WEBSITE_DISCOVERY] REQUEST -> Model: {model_name} | Company: {company_name} | Domain: {company_domain or 'Not provided'} | Description: {company_description or 'Not provided'} | LinkedIn: {linkedin_url or 'Not provided'}")
        
        # Execute the chain
        website_url = chain.invoke({
            "company_name": company_name,
            "company_domain": company_domain or "Not provided",
            "company_description": company_description or "Not provided",
            "linkedin_url": linkedin_url or "Not provided"
        })
        
        # Log AI response
        logger.info(f"[AI_WEBSITE_DISCOVERY] RESPONSE -> URL: {website_url}")
        
        # Clean up the URL
        website_url = website_url.strip().replace('`', '').strip()
        if website_url and (website_url.startswith('http://') or website_url.startswith('https://')):
            return website_url
            
    except Exception as e:
        print(f"LangChain website discovery error: {e}")
    
    # Fallback
    if company_domain:
        return f"https://www.{company_domain}" if not company_domain.startswith('http') else company_domain
    return None

def scrape_website_with_langchain(url: str) -> Dict[str, Any]:
    """Use LangChain's WebBaseLoader to scrape website content"""
    emails = set()
    phones = set()
    
    try:
        # Use LangChain's WebBaseLoader
        loader = WebBaseLoader(url)
        documents = loader.load()
        
        # Split text into chunks for better processing
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        
        # Extract emails and phones from each chunk
        for doc in splits:
            text_content = doc.page_content
            page_emails = extract_emails(text_content)
            page_phones = extract_phone_numbers(text_content)
            
            emails.update(page_emails)
            phones.update(page_phones)
        
        return {
            'emails': list(emails),
            'phones': list(phones),
            'pages_scraped': 1,
            'chunks_processed': len(splits)
        }
        
    except Exception as e:
        print(f"LangChain scraping error for {url}: {e}")
        return {'emails': [], 'phones': [], 'pages_scraped': 0}

def scrape_website_for_contacts(url: str, max_pages: int = 5) -> Dict[str, Any]:
    """Scrape website to find contact information"""
    emails = set()
    phones = set()
    visited_urls = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    def scrape_page(page_url: str, depth: int = 0):
        if depth >= max_pages or page_url in visited_urls:
            return
        
        try:
            visited_urls.add(page_url)
            response = requests.get(page_url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract text content
            text_content = soup.get_text()
            
            # Find emails and phones
            page_emails = extract_emails(text_content)
            page_phones = extract_phone_numbers(text_content)
            
            emails.update(page_emails)
            phones.update(page_phones)
            
            # Look for contact page links if we haven't found enough info
            if depth < 2 and (len(emails) < 2 or len(phones) < 1):
                contact_keywords = ['contact', 'about', 'contact-us', 'reach-us', 'get-in-touch']
                links = soup.find_all('a', href=True)
                
                for link in links[:20]:  # Limit links to check
                    href = link['href']
                    link_text = link.get_text().lower()
                    
                    if any(keyword in href.lower() or keyword in link_text for keyword in contact_keywords):
                        # Convert relative URL to absolute
                        if href.startswith('/'):
                            next_url = f"{page_url.rstrip('/')}{href}"
                        elif href.startswith('http'):
                            next_url = href
                        else:
                            continue
                        
                        # Only scrape same domain
                        if page_url.split('/')[2] in next_url:
                            scrape_page(next_url, depth + 1)
            
        except Exception as e:
            print(f"Error scraping {page_url}: {e}")
    
    # Start scraping from main URL
    scrape_page(url)
    
    return {
        'emails': list(emails),
        'phones': list(phones),
        'pages_scraped': len(visited_urls)
    }

def enhance_results_with_ai(company_info: Dict[str, Any], scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """Use LangChain to enhance and validate the scraped results"""
    if not llm or not scraped_data.get('emails') and not scraped_data.get('phones'):
        return scraped_data

    try:
        # Create a prompt template with JSON output parser
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that filters contact information. Return only valid JSON with keys 'emails' and 'phones'."),
            ("user", """Given the following scraped contact information for {company_name}:

Emails found: {emails_list}
Phone numbers found: {phones_list}

Filter and return only the most likely OFFICIAL business contact information.
Remove any personal emails, spam, or irrelevant contacts.
Return as JSON with keys: "emails" (list) and "phones" (list).
Keep only the most relevant 3-5 of each.""")
        ])
        
        # Create a chain with JSON output parser
        json_parser = JsonOutputParser()
        chain = prompt_template | llm | json_parser
        
        # Log AI request
        logger.info(f"[AI_CONTACT_FILTER] REQUEST -> Model: {model_name} | Company: {company_info.get('company_name')} | Emails: {len(scraped_data.get('emails', []))} found | Phones: {len(scraped_data.get('phones', []))} found")
        
        # Execute the chain
        enhanced = chain.invoke({
            "company_name": company_info.get('company_name'),
            "emails_list": ', '.join(scraped_data.get('emails', [])[:10]),
            "phones_list": ', '.join(scraped_data.get('phones', [])[:10])
        })
        
        # Log AI response
        logger.info(f"[AI_CONTACT_FILTER] RESPONSE -> Filtered Emails: {enhanced.get('emails', [])} | Filtered Phones: {enhanced.get('phones', [])}")
        
        return {
            'emails': enhanced.get('emails', scraped_data.get('emails', [])),
            'phones': enhanced.get('phones', scraped_data.get('phones', [])),
            'pages_scraped': scraped_data.get('pages_scraped', 0)
        }
        
    except Exception as e:
        print(f"LangChain enhancement error: {e}")
        # Fallback: try to parse manually if JSON parsing fails
        try:
            prompt_template_fallback = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant that filters contact information. Return only valid JSON."),
                ("user", """Given the following scraped contact information for {company_name}:

Emails found: {emails_list}
Phone numbers found: {phones_list}

Filter and return only the most likely OFFICIAL business contact information.
Remove any personal emails, spam, or irrelevant contacts.
Return as JSON with keys: "emails" (list) and "phones" (list).
Keep only the most relevant 3-5 of each.""")
            ])
            
            chain_fallback = prompt_template_fallback | llm | StrOutputParser()
            
            # Log fallback AI request
            logger.info(f"[AI_CONTACT_FILTER_FALLBACK] REQUEST -> Model: {model_name} | Company: {company_info.get('company_name')} | Emails: {len(scraped_data.get('emails', []))} found | Phones: {len(scraped_data.get('phones', []))} found")
            
            result_text = chain_fallback.invoke({
                "company_name": company_info.get('company_name'),
                "emails_list": ', '.join(scraped_data.get('emails', [])[:10]),
                "phones_list": ', '.join(scraped_data.get('phones', [])[:10])
            })
            
            # Log fallback AI response
            logger.info(f"[AI_CONTACT_FILTER_FALLBACK] RESPONSE -> Raw text: {result_text[:200]}...")
            
            # Extract JSON from response
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            enhanced = json.loads(result_text)
            return {
                'emails': enhanced.get('emails', scraped_data.get('emails', [])),
                'phones': enhanced.get('phones', scraped_data.get('phones', [])),
                'pages_scraped': scraped_data.get('pages_scraped', 0)
            }
        except Exception as inner_e:
            print(f"LangChain fallback enhancement error: {inner_e}")
            return scraped_data

# Routes
@app.get("/")
def root():
    return {
        "message": "Welcome to Company Contact Finder API with LangChain!",
        "version": "2.0.0",
        "powered_by": "LangChain + OpenAI",
        "endpoints": {
            "/company-address": "GET - Find company contact information (LangChain-powered)",
            "/analyze-company": "GET - AI-powered company analysis with LangChain",
            "/docs": "API Documentation"
        }
    }

@app.get("/analyze-company")
async def analyze_company(
    company_name: str = Query(..., description="Company name"),
    company_domain: Optional[str] = Query(None, description="Company domain"),
    analysis_type: str = Query("summary", description="Type of analysis: summary, contacts, or full")
):
    """
    LangChain-powered endpoint for comprehensive company analysis.
    
    This endpoint uses LangChain chains to:
    1. Analyze company information
    2. Generate insights about the company
    3. Provide structured analysis using AI
    """
    if not llm:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        )
    
    try:
        # Determine website
        website_url = None
        if company_domain:
            website_url = f"https://www.{company_domain}" if not company_domain.startswith('http') else company_domain
        
        # Create analysis prompt template
        if analysis_type == "summary":
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are a business analyst AI that provides concise company summaries."),
                ("user", """Provide a brief summary and insights about {company_name}.
                
Company Name: {company_name}
Website: {website}

Include:
- Brief company overview
- Industry/sector
- Key business focus
- Notable facts (if known)

Keep response concise and informative.""")
            ])
        elif analysis_type == "contacts":
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are a business intelligence AI that helps find contact information strategies."),
                ("user", """For the company {company_name}, suggest the best strategies to find their contact information.

Company Name: {company_name}
Website: {website}

Provide:
- Best pages to check for contacts (e.g., /contact, /about)
- Typical contact formats they might use
- Alternative contact methods
- Social media presence recommendations""")
            ])
        else:  # full analysis
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are a comprehensive business intelligence AI."),
                ("user", """Provide a comprehensive analysis of {company_name}.

Company Name: {company_name}
Website: {website}

Include:
- Company overview
- Industry and market position
- Products/services
- Contact information strategies
- Key facts and insights

Be thorough but concise.""")
            ])
        
        # Create and execute the chain
        chain = prompt_template | llm | StrOutputParser()
        
        # Log AI request
        logger.info(f"[AI_COMPANY_ANALYSIS] REQUEST -> Model: {model_name} | Company: {company_name} | Website: {website_url or 'Not provided'} | Analysis Type: {analysis_type}")
        
        analysis = chain.invoke({
            "company_name": company_name,
            "website": website_url or "Not provided"
        })
        
        # Log AI response
        logger.info(f"[AI_COMPANY_ANALYSIS] RESPONSE -> Analysis length: {len(analysis)} chars | Preview: {analysis[:150]}...")
        
        return {
            "company_name": company_name,
            "website": website_url,
            "analysis_type": analysis_type,
            "analysis": analysis,
            "status": "success",
            "powered_by": "LangChain + GPT-4o-mini"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis error: {str(e)}"
        )

@app.get("/company-address", response_model=ContactInfo)
async def get_company_address(
    company_name: str = Query(..., description="Company name"),
    location: Optional[str] = Query(None, description="Company location"),
    industry: Optional[str] = Query(None, description="Company industry"),
    linkedin_url: Optional[str] = Query(None, description="LinkedIn profile URL"),
    company_domain: Optional[str] = Query(None, description="Company domain (e.g., example.com)"),
    company_description: Optional[str] = Query(None, description="Company description"),
):
    """
    AI-powered endpoint to find company contact information.
    
    This endpoint:
    1. Uses AI to identify the company's official website
    2. Scrapes the website and related pages for contact information
    3. Extracts email addresses and phone numbers
    4. Returns structured JSON response
    
    **Note:** Set OPENAI_API_KEY environment variable for AI-powered website discovery.
    """
    try:
        # Step 1: Find company website using AI
        website_url = find_company_website_with_ai(
            company_name=company_name,
            company_domain=company_domain,
            company_description=company_description,
            linkedin_url=linkedin_url
        )
        
        if not website_url:
            return ContactInfo(
                company_name=company_name,
                status="error",
                message="Could not determine company website. Please provide company_domain.",
                email_addresses=[],
                phone_numbers=[],
                website_url=None
            )
        
        # Step 2: Scrape website for contact information using LangChain
        # Try LangChain loader first
        scraped_data = scrape_website_with_langchain(website_url)
        
        # If LangChain didn't find much, fallback to traditional scraping
        if len(scraped_data.get('emails', [])) < 2 or len(scraped_data.get('phones', [])) < 1:
            traditional_data = scrape_website_for_contacts(website_url, max_pages=3)
            # Combine results
            all_emails = set(scraped_data.get('emails', [])) | set(traditional_data.get('emails', []))
            all_phones = set(scraped_data.get('phones', [])) | set(traditional_data.get('phones', []))
            scraped_data = {
                'emails': list(all_emails),
                'phones': list(all_phones),
                'pages_scraped': scraped_data.get('pages_scraped', 0) + traditional_data.get('pages_scraped', 0)
            }
        
        # Step 3: Enhance results with AI (optional filtering)
        company_info = {
            'company_name': company_name,
            'location': location,
            'industry': industry
        }
        enhanced_data = enhance_results_with_ai(company_info, scraped_data)
        
        # Step 4: Return structured response
        return ContactInfo(
            company_name=company_name,
            website_url=website_url,
            email_addresses=enhanced_data.get('emails', []),
            phone_numbers=enhanced_data.get('phones', []),
            additional_info={
                'location': location,
                'industry': industry,
                'linkedin_url': linkedin_url,
                'pages_scraped': enhanced_data.get('pages_scraped', 0)
            },
            status="success",
            message=f"Found {len(enhanced_data.get('emails', []))} email(s) and {len(enhanced_data.get('phones', []))} phone number(s)"
        )
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error accessing website: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Keep existing routes for backward compatibility
@app.get("/items/")
def items():
    return {"message": "Welcome to the items route!"}

@app.get("/items/update/")
def update_item():
    return {"message": "Welcome to the update item route!"}
