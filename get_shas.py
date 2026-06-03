import urllib.request
import json

def get_sha(repo, tag):
    url = f'https://api.github.com/repos/{repo}/git/refs/tags/{tag}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f'{repo}@{tag} -> {data["object"]["sha"]}')
    except Exception as e:
        print(f'Failed {repo}@{tag}: {e}')

get_sha('actions/checkout', 'v4')
get_sha('actions/setup-python', 'v5')
get_sha('aws-actions/configure-aws-credentials', 'v4')
get_sha('aws-actions/amazon-ecr-login', 'v2')
