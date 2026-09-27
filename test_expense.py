from app import create_app, db
from app.models import User, Expense
import re

app = create_app()
with app.test_client() as c:
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        with c.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
    
    # First GET the form to get CSRF token
    resp = c.get('/expenses/create')
    html = resp.data.decode('utf-8')
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if csrf_match:
        csrf_token = csrf_match.group(1)
        print('CSRF token found:', csrf_token[:20])
        
        # Now POST with CSRF token
        resp = c.post('/expenses/create', data={
            'csrf_token': csrf_token,
            'date': '2024-01-15',
            'category': 'advertisement',
            'sub_category': 'Facebook',
            'description': 'Test expense',
            'amount': '10000'
        }, follow_redirects=False)
        print('POST Status:', resp.status_code)
        if resp.status_code == 302:
            print('SUCCESS! Redirect to:', resp.location)
        else:
            html = resp.data.decode('utf-8')
            if 'text-danger' in html:
                idx = html.find('text-danger')
                print(html[max(0,idx-150):idx+300])
    else:
        print('No CSRF token found')