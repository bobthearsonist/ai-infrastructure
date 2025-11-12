import http.server
import socketserver

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

print('Starting health server on 0.0.0.0:7009')
with socketserver.TCPServer(("0.0.0.0", 7009), HealthHandler) as httpd:
    print('Health server ready')
    httpd.serve_forever()
