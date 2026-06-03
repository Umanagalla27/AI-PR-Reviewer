import os
for root, _, files in os.walk('services'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'async with test_client as client:' in content:
                content = content.replace('async with test_client as client:', 'async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'Fixed test_client in {filepath}')
