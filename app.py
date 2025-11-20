import os
import requests
import json
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- CẤU HÌNH ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Nếu chạy trên máy cá nhân mà chưa set biến môi trường thì báo lỗi hoặc dùng key tạm (không khuyến khích)
if not API_KEY:
    # Chỉ dùng dòng này khi test ở máy nhà, KHÔNG UP LÊN GITHUB dòng chứa key thật
    print("Cảnh báo: Chưa tìm thấy API Key trong biến môi trường!")

# --- HÀM GỌI GOOGLE GEMINI TRỰC TIẾP ---
# Hàm này gửi yêu cầu thẳng lên server Google, bỏ qua thư viện Python để tránh lỗi
def call_google_ai_search(topic_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Prompt (Câu lệnh) chi tiết
    final_prompt = f"""
    Bạn là chuyên gia phân tích chính sách và pháp luật Việt Nam.
    Chủ đề cần nghiên cứu: "{topic_text}"
    
    YÊU CẦU BẮT BUỘC:
    1. Sử dụng Google Search tích hợp để tìm dữ liệu MỚI NHẤT.
    2. Chỉ chắt lọc thông tin từ các nguồn chính thống: 
        - site:gov.vn
        - site:dangcongsan.vn
        - site:quochoi.vn
        - site:baochinhphu.vn
        - site:tapchicongsan.org.vn

    HÃY TRẢ VỀ KẾT QUẢ THEO ĐỊNH DẠNG MARKDOWN:
    ## I. Hiện trạng và Vấn đề pháp lý
    - Tổng quan tình hình thực tế (nêu số liệu mới nhất nếu có).
    - Chỉ rõ các điểm nghẽn về cơ chế, chính sách, quy định pháp luật đang tồn tại.
    
    ## II. Kiến nghị Hoàn thiện thể chế
    - Đề xuất 3-5 giải pháp cụ thể (sửa đổi luật nào, ban hành chính sách gì).
    
    ## III. Nguồn tham khảo
    - Liệt kê các đường link chính thống đã sử dụng.

    QUY ĐỊNH NGHIÊM NGẶT VỀ OUTPUT (QUAN TRỌNG):
    - KHÔNG ĐƯỢC có lời chào, lời dẫn nhập hay kết luận xã giao (như "Tuyệt vời", "Dưới đây là kết quả...").
    - Trả về kết quả TRỰC TIẾP bắt đầu ngay bằng tiêu đề hoặc mục "I. Hiện trạng...".
    - Chỉ xuất ra nội dung phân tích.
    - Ở các đường link chính thống phải ghi mô tả trang web
    """

    # Payload JSON chuẩn để kích hoạt Google Search (Grounding)
    payload = {
        "contents": [{
            "parts": [{"text": final_prompt}]
        }],
        "tools": [{
            "google_search": {}  # Đây là cú pháp chuẩn để bật Search server-side
        }]
    }

    try:
        # Gửi request
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Lỗi từ Google ({response.status_code}): {response.text}"
            
        data = response.json()
        
        # Xử lý kết quả trả về
        try:
            candidates = data.get('candidates', [])
            if not candidates:
                return "Không tìm thấy kết quả nào (có thể do bộ lọc an toàn)."
            
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            
            if not parts:
                return "AI không trả lời văn bản."
                
            # 1. Lấy văn bản thô từ AI
            raw_text = parts[0].get('text', 'Lỗi định dạng văn bản.')

            # -------------------------------------------------------
            # 2. BƯỚC HẬU XỬ LÝ (POST-PROCESSING) ĐỂ CẮT LỜI DẪN
            # -------------------------------------------------------
            # Định nghĩa điểm bắt đầu mong muốn (dựa trên prompt của bạn)
            start_marker = "##I. Hiện trạng"
            
            # Kiểm tra xem marker có tồn tại trong văn bản không
            if start_marker in raw_text:
                # Tách văn bản làm 2 phần và chỉ lấy phần sau
                # split(..., 1) đảm bảo chỉ cắt ở lần xuất hiện đầu tiên
                parts_split = raw_text.split(start_marker, 1)
                
                # Ghép lại marker vào đầu vì split đã làm mất nó
                clean_text = start_marker + parts_split[1]
                
                # Loại bỏ khoảng trắng thừa ở đầu/cuối (nếu có)
                return clean_text.strip()
            else:
                # Nếu AI không trả về đúng format mong muốn, trả về nguyên gốc
                return raw_text.strip()
            # -------------------------------------------------------
            
        except Exception as parse_error:
            return f"Lỗi đọc dữ liệu: {str(parse_error)}"

    except Exception as e:
        return f"Lỗi kết nối mạng: {str(e)}"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    topic = data.get('topic', '')

    if not topic:
        return jsonify({"error": "Vui lòng nhập chủ đề"}), 400

    # Gọi hàm xử lý
    result_text = call_google_ai_search(topic)
    
    return jsonify({"result": result_text})

# --- GIAO DIỆN HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Phân tích Chính sách (Google Grounding)</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f0f2f5; }
        .chat-container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        h1 { color: #d63031; text-align: center; margin-bottom: 10px; }
        p.desc { text-align: center; color: #555; margin-bottom: 30px; font-style: italic;}
        
        .input-section { display: flex; gap: 15px; margin-bottom: 30px; }
        input { flex: 1; padding: 15px; border: 2px solid #eee; border-radius: 8px; font-size: 16px; transition: 0.3s; }
        input:focus { border-color: #d63031; outline: none; }
        
        button { padding: 15px 40px; background: #d63031; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; transition: 0.3s; }
        button:hover { background: #b71c1c; transform: translateY(-2px); }
        
        #result { line-height: 1.8; color: #2d3436; text-align: justify; }
        
        /* Markdown Styles */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        h2 { color: #d63031; /* Màu đỏ đậm */
            font-size: 1.6em; /* Chữ to hơn */
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee; /* ĐƯỜNG KẺ NGĂN CÁCH */
            border-color: #d63031; }
        h3 { color: #34495e; margin-top: 20px; font-size: 1.2em; }
        ul { padding-left: 20px; padding-right: 20px;}
        ol { padding-left: 20px; padding-right: 20px;}
        li { margin-bottom: 10px; line-height: 1.6; }
        p { line-height: 1.6; text-align: justify; padding-right: 20px; }
        strong { color: #000; font-weight: 600; }
        a { color: #0984e3; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .app-footer {
            text-align: center;
            padding: 25px 0;
            margin-top: 30px; /* Tạo khoảng cách với nội dung bên trên */
            color: #48565c; /* Màu xám nhạt */
            font-size: 0.95em;
            font-weight: 500;
        }
        .loader { display: none; text-align: center; margin-top: 20px; color: #d63031; font-weight: 500; }
        @media (max-width: 768px) {
            body { 
                padding: 15px; /* Giảm lề body */
            }
            h1.main-title { 
                font-size: 1.5rem; /* Chữ tiêu đề nhỏ lại chút */
            }
            
            /* Chuyển thanh input thành hàng dọc */
            .input-section { 
                flex-direction: column;
                padding: 15px;
                gap: 15px;
            }
            input { 
                width: 90%;
                padding: 15px;
            }
            button { 
                width: 100%;
                padding: 15px;
                margin-top: 5px; 
            }

            /* Tối ưu hộp kết quả trên mobile */
            .result{
                padding: 25px 20px; /* Giảm padding để nội dung rộng hơn */
            }
            .result h2 {
                font-size: 1.2rem; /* Tiêu đề mục nhỏ lại cho cân đối */
            }
            .result li, .result p {
                font-size: 0.95rem; /* Chữ nội dung vừa mắt */
            }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
    <div class="chat-container">
        <h1>Hệ thống Phân tích & Hoàn thiện Thể chế</h1>
        <p class="desc">Nhóm 6 - UIT SS006.Q13</p>
        
        <div class="input-section">
            <input type="text" id="topicInput" placeholder="Nhập chủ đề (VD: Kinh tế số, Thủ tục đầu tư nước ngoài, Luật đất đai, ...)" onkeypress="if(event.key==='Enter') analyze()">
            <button onclick="analyze()">Phân tích ngay</button>
        </div>

        <div class="loader" id="loader">
            Đang phân tích...<br>
        </div>
        <div id="result"></div>
    </div>

    <script>
        async function analyze() {
            const topic = document.getElementById('topicInput').value;
            const resultDiv = document.getElementById('result');
            const loader = document.getElementById('loader');
            
            if (!topic.trim()) return alert("Vui lòng nhập chủ đề cần tra cứu!");

            resultDiv.innerHTML = "";
            loader.style.display = "block";

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: topic })
                });
                
                const data = await response.json();
                loader.style.display = "none";
                
                // Render Markdown
                resultDiv.innerHTML = marked.parse(data.result);
                
            } catch (err) {
                loader.style.display = "none";
                resultDiv.innerHTML = `<p style="color:red; text-align:center;">Lỗi kết nối đến hệ thống: ${err.message}</p>`;
            }
        }
    </script>
</body>
<footer class="app-footer">
                Developed by Nguyên Phát
</footer>    
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, port=5000)