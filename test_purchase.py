from app import create_app
import re

app = create_app()
with app.test_client() as c:
    from app.models import User
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        with c.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
    
    # Get CSRF token first
    resp = c.get('/purchases/create')
    html = resp.data.decode('utf-8')
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if csrf_match:
        csrf_token = csrf_match.group(1)
        print('CSRF found')
        
        # POST with CSRF
        resp = c.post('/purchases/create', data={
            'csrf_token': csrf_token,
            'purchase_no': 'PO-TEST-001',
            'date': '2024-01-15',
            'supplier_id': '1',
            'product_id[]': '1',
            'quantity[]': '10',
            'unit_price[]': '8000',
            'reference_price[]': '10000',
        }, follow_redirects=False)
        print('POST Status:', resp.status_code)
        if resp.status_code == 200:
            html = resp.data.decode('utf-8')
            if 'text-danger' in html:
                idx = html.find('text-danger')
                print(html[max(0,idx-150):idx+300])
            else:
                print('Form returned 200 but no validation error visible')
        elif resp.status_code == 302:
            print('SUCCESS! Redirect to:', resp.location)
    else:
        print('No CSRF token found')