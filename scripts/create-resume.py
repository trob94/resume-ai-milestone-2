import os
import json
import boto3
from datetime import datetime

# Connect to AWS services
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Get environment variables (GitHub Actions will set these)
bucket_name = os.environ['BUCKET_NAME']
deployment_table = os.environ['DEPLOYMENT_TABLE']
analytics_table = os.environ['ANALYTICS_TABLE']
environment = os.environ.get('ENVIRONMENT', 'beta')
commit_sha = os.environ.get('COMMIT_SHA', 'unknown')

# Step 1: Read the resume file
def read_resume():
    with open('resume.md', 'r') as file:
        return file.read()

# Step 2: Use AI to convert resume to HTML
def generate_html(resume_text):
    prompt = f"""Turn this resume into a nice HTML website.
Make it professional and easy to read.

{resume_text}

Return only the HTML code."""

    request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps(request)
    )
    
    result = json.loads(response['body'].read())
    html = result['content'][0]['text']
    
    # Clean up if AI wrapped it in code blocks
    if '```html' in html:
        html = html.split('```html')[1].split('```')[0]
    
    return html.strip()

# Step 3: Use AI to analyze the resume
def analyze_resume(resume_text):
    prompt = f"""Analyze this resume and give it scores.
Return your answer as JSON in this exact format:
{{
  "ats_score": 85,
  "word_count": 450,
  "strengths": ["Good action verbs", "Clear structure"],
  "improvements": ["Add more metrics", "Include certifications"]
}}

Resume:
{resume_text}"""

    request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps(request)
    )
    
    result = json.loads(response['body'].read())
    analysis = result['content'][0]['text']
    
    # Clean up if AI wrapped it in code blocks
    if '```json' in analysis:
        analysis = analysis.split('```json')[1].split('```')[0]
    
    return json.loads(analysis.strip())

# Step 4: Upload HTML to S3
def upload_to_s3(html_content):
    key = f'{environment}/index.html'
    
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=html_content,
        ContentType='text/html'
    )
    
    url = f'http://{bucket_name}.s3-website-us-east-1.amazonaws.com/{environment}/index.html'
    print(f'Uploaded to: {url}')
    return url

# Step 5: Save deployment info to DynamoDB
def save_deployment(url):
    table = dynamodb.Table(deployment_table)
    
    table.put_item(Item={
        'id': f'{environment}-{commit_sha}',
        'timestamp': datetime.now().isoformat(),
        'environment': environment,
        'url': url,
        'commit': commit_sha
    })
    
    print(f'Saved deployment record')

# Step 6: Save analytics to DynamoDB
def save_analytics(analysis):
    table = dynamodb.Table(analytics_table)
    
    table.put_item(Item={
        'id': commit_sha,
        'timestamp': datetime.now().isoformat(),
        'ats_score': analysis['ats_score'],
        'word_count': analysis['word_count'],
        'strengths': analysis['strengths'],
        'improvements': analysis['improvements']
    })
    
    print(f'ATS Score: {analysis["ats_score"]}/100')

# Main program - run all the steps
print('Starting resume generation...')

resume = read_resume()
print('1. Read resume ✓')

html = generate_html(resume)
print('2. Generated HTML ✓')

analysis = analyze_resume(resume)
print('3. Analyzed resume ✓')

url = upload_to_s3(html)
print('4. Uploaded to S3 ✓')

save_deployment(url)
print('5. Saved deployment ✓')

save_analytics(analysis)
print('6. Saved analytics ✓')

print(f'\n🎉 Done! View your resume at:\n{url}')
