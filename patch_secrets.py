import base64
import re
import json
import subprocess

content = open('.env', encoding='utf-8').read()
oai = re.search(r'OPENAI_API_KEY=(.*)', content).group(1).strip()
app_id = re.search(r'GITHUB_APP_ID=(.*)', content).group(1).strip()
pk = re.search(r'GITHUB_APP_PRIVATE_KEY=\"(.*?)\"', content, re.DOTALL).group(1).replace('\\n', '\n')
ws = re.search(r'GITHUB_WEBHOOK_SECRET=(.*)', content).group(1).strip()

patch = {
    'data': {
        'OPENAI_API_KEY': base64.b64encode(oai.encode()).decode(),
        'GITHUB_APP_ID': base64.b64encode(app_id.encode()).decode(),
        'GITHUB_APP_PRIVATE_KEY': base64.b64encode(pk.encode()).decode(),
        'GITHUB_WEBHOOK_SECRET': base64.b64encode(ws.encode()).decode()
    }
}

with open('patch.json', 'w') as f:
    json.dump(patch, f)

subprocess.run(['kubectl', 'patch', 'secret', 'app-secrets', '-n', 'codereview', '--type=merge', '--patch-file', 'patch.json'], check=True)
print("Secrets successfully patched!")
