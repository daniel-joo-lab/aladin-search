import http.server
import socketserver
import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import re
import os

PORT = int(os.environ.get('PORT', 8000))

def scrape_aladin(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=UsedStore&KeyWord={encoded_keyword}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        
        first_item = soup.select_one('div.ss_book_box')
        if not first_item:
            return {'bookName': keyword, 'bestStores': [], 'otherStores': [], 'error': '검색 결과가 없습니다.'}
            
        item_id = first_item.get('itemid')
        title_elem = first_item.select_one('a.bo3')
        if not title_elem:
            title_elem = first_item.select_one('b')
        title = title_elem.text.strip() if title_elem else keyword
        
        # Get used stores
        url_stores = f"https://www.aladin.co.kr/shop/UsedShop/wuseditemall.aspx?ItemId={item_id}&TabType=3"
        req_stores = urllib.request.Request(url_stores, headers={'User-Agent': 'Mozilla/5.0'})
        html_stores = urllib.request.urlopen(req_stores).read()
        
        soup_stores = BeautifulSoup(html_stores, 'html.parser')
        rows = soup_stores.select('.Ere_store_name')

        stores_data = []
        for row in rows:
            parent = row.find_parent('td')
            if parent:
                tr = parent.find_parent('tr')
                if tr:
                    store_name = row.text.replace('중고매장', '').strip()
                    quality = 'Unknown'
                    tds = tr.find_all('td')
                    if len(tds) > 2:
                        q_text = tds[2].text.strip()
                        if '최상' in q_text: quality = '최상'
                        elif '상' in q_text: quality = '상'
                        elif '중' in q_text: quality = '중'
                    
                    price = 'Unknown'
                    price_elem = tr.select_one('.price, .Ere_fs20')
                    if price_elem:
                        # Extract only the price part, eg "19,600원"
                        price_text = price_elem.text.strip()
                        price = price_text.split('\n')[0].strip()
                        
                    stores_data.append({'store': store_name, 'quality': quality, 'price': price})

        def group_stores(quality):
            filtered = [s for s in stores_data if s['quality'] == quality]
            grouped = {}
            for s in filtered:
                key = (s['store'], s['price'])
                grouped[key] = grouped.get(key, 0) + 1
            return [{'store': k[0], 'price': k[1], 'count': v} for k, v in grouped.items()]

        best_stores = group_stores('최상')
        good_stores = group_stores('상')
        other_stores = list(set([s['store'] for s in stores_data if s['quality'] not in ('최상', '상')]))
        
        # Sort other stores for better readability
        other_stores.sort()

        return {
            'bookName': title,
            'bestStores': best_stores,
            'goodStores': good_stores,
            'otherStores': other_stores
        }
    except Exception as e:
        return {'bookName': keyword, 'bestStores': [], 'goodStores': [], 'otherStores': [], 'error': str(e)}

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/search':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                keywords = json.loads(post_data).get('books', [])
                results = []
                for kw in keywords:
                    if kw.strip():
                        results.append(scrape_aladin(kw.strip()))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            super().do_POST()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()
