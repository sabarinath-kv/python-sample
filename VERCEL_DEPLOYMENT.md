# Vercel Deployment Fix - Size Optimization

## Problem
Serverless Function exceeded the unzipped maximum size of 250 MB on Vercel.

## Solutions Applied

### 1. ✅ Removed Heavy Dependencies
**Removed from requirements.txt:**
- `litellm[proxy]` - The `[proxy]` extra includes many heavy dependencies (Redis, databases, etc.)
  - Your app only uses LiteLLM as an optional base_url parameter
  - LangChain's OpenAI integration handles the actual API calls
  - If you need LiteLLM proxy, run it separately and just point to its URL

**Also removed unused packages:**
- `httpx` - Not used in code
- `openai` - Already included as dependency of `langchain-openai`
- `langchain` - Not needed; using specific `langchain-*` packages

### 2. ✅ Created .vercelignore
Excludes unnecessary files from deployment:
- Test files (`test_endpoint.py`, `langchain_examples.py`)
- Documentation files
- Development files (`__pycache__`, `.pyc`)
- IDE files
- Git files
- Virtual environments

### 3. ✅ Optimized vercel.json
Added configuration for better resource management:
```json
{
  "functions": {
    "app.py": {
      "memory": 1024,
      "maxDuration": 10
    }
  }
}
```

### 4. ✅ Changed uvicorn to uvicorn[standard]
Includes optimized production dependencies.

## Current Package Size Estimate
After optimization:
- **Before:** ~400-500 MB (with litellm[proxy])
- **After:** ~150-200 MB (without litellm[proxy])

## Deployment Steps

### Option 1: Deploy Now (Recommended)
```bash
# Commit changes
git add .
git commit -m "Fix: Optimize dependencies for Vercel deployment"
git push

# Vercel will auto-deploy
```

### Option 2: Test Locally First
```bash
# Recreate virtual environment with new dependencies
rm -rf venv
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install optimized dependencies
pip install -r requirements.txt

# Test the app
uvicorn app:app --reload

# If working, deploy
git add .
git commit -m "Fix: Optimize dependencies for Vercel deployment"
git push
```

## If You Need LiteLLM Proxy

If you actually need LiteLLM proxy features, consider these alternatives:

### Option A: Deploy LiteLLM Separately
1. Deploy LiteLLM proxy as a separate Vercel/Railway/Render service
2. Set `LITELLM_BASE_URL` environment variable to point to it
3. Keep your main app lightweight

### Option B: Use LiteLLM Without Proxy Extras
```txt
# In requirements.txt, use base litellm only:
litellm  # Without [proxy]
```
This gives you LiteLLM SDK without the heavy proxy server dependencies.

### Option C: Use OpenAI Directly
Your app already works with OpenAI directly. Just don't set `LITELLM_BASE_URL`:
```bash
# Environment variables
OPENAI_API_KEY=your_key_here
MODEL_NAME=gpt-4o-mini
# Don't set LITELLM_BASE_URL
```

## Environment Variables for Vercel

Make sure these are set in Vercel Dashboard:
```
OPENAI_API_KEY=your_openai_api_key
MODEL_NAME=gpt-4o-mini
# Optional: LITELLM_BASE_URL=https://your-litellm-proxy.com
```

## Monitoring Deployment Size

To check your deployment size:
1. Go to Vercel Dashboard
2. Click on your project
3. Go to "Deployments"
4. Click on a deployment
5. Check "Build Logs" for size information

## Additional Optimization Tips

If still too large, consider:

1. **Remove lxml if not needed:**
   - BeautifulSoup can use `html.parser` instead
   - Change in app.py: `BeautifulSoup(html, 'html.parser')`

2. **Use lighter alternatives:**
   ```txt
   # Instead of langchain-community (large)
   # Only install what you need from langchain
   ```

3. **Split into microservices:**
   - Deploy web scraping as separate function
   - Deploy AI analysis as separate function
   - Use Vercel's multi-function support

## Troubleshooting

### Still getting size error?
```bash
# Check actual package sizes locally
pip list --format=freeze | xargs pip show | grep -E 'Name|Size'
```

### Build fails?
- Check Vercel build logs for specific errors
- Ensure Python version matches (3.9+ recommended)
- Verify all imports work with new dependencies

### Function timeout?
- Increase `maxDuration` in vercel.json (max 60s on Pro plan)
- Optimize scraping to be faster
- Add caching for repeated requests

## Success Indicators

✅ Build completes without size errors
✅ Function deploys successfully
✅ API endpoints respond correctly
✅ LangChain features work as expected
✅ OpenAI API calls succeed

## Support

If issues persist:
1. Check Vercel build logs
2. Test locally with exact same dependencies
3. Consider upgrading to Vercel Pro for larger limits
4. Use edge functions for lighter workloads

