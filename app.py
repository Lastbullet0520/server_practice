import mimetypes

import requests
from flask import Flask, request, jsonify, render_template, send_file
import os
from pymongo import MongoClient
from ultralytics import YOLO
import cv2
import spoonacular
from werkzeug.security import safe_join


app = Flask(__name__)
client = MongoClient("localhost", 27017)
db = client.dbintel

configuration = spoonacular.Configuration(
    host="https://api.spoonacular.com"
)
configuration.api_key['apiKeyScheme'] = "4adcee865a5b4cde8580e088bffdd841"
API_KEY = configuration.api_key['apiKeyScheme']

model = YOLO("best.pt")  # train 시킨 모델입니다. onnx 형식, pt 형식 둘 다 있습니다.

# 이미지 저장 경로 설정
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

UPLOAD_LIST = "uploads_list"
os.makedirs(UPLOAD_LIST, exist_ok=True)
app.config["UPLOAD_LIST"] = UPLOAD_LIST


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload_and_find", methods=['POST'])  # 이미지 업로드 하여 식재료 리스트 추출하는 코드 -> 학습모델 필요
def upload_and_find():
    if 'file' not in request.files:
        return jsonify({'error': 'no uploaded file.'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'no selected file.'})

    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        try:
            # YOLOv8 모델을 사용하여 이미지 처리 및 객체 인식
            results = model(filename)

            # YOLOv8 모델의 클래스 이름 리스트 가져오기
            class_names = model.names
            # 이미지 로드
            img = cv2.imread(filename)

            # 객체 이름 추출 및 바운딩 박스 그리기
            detected_objects = []
            # for result in results.xyxy[0].cpu().numpy():

            # 바운딩 박스가 그려진 이미지를 저장

            # 객체 이름 추출
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls)
                    class_name = class_names[class_id]
                    detected_objects.append(class_name)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    # 바운딩 박스 그리기
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 10)
                    cv2.putText(img, class_name, (x1, y1 + 100), cv2.FONT_HERSHEY_SIMPLEX, 5, (255, 0, 0), 10)

            output_filename = os.path.join(app.config['UPLOAD_FOLDER'], 'boxed_' + file.filename)
            cv2.imwrite(output_filename, img)

            ingredients = ','.join(set(detected_objects))  # 중복 제거 후 콤마로 구분된 문자열로 변환
            print("Detected ingredients:", ingredients)

            return jsonify({
                "ingredients": ingredients,
                "output_image": "boxed_" + file.filename
            })

        except Exception as e:
            print("YOLOv8 Exception in image recognition: %s\n" % e)
            return jsonify({"error": "YOLO error"}), 500

    return jsonify({"error": "undefined error occurs"}), 500


@app.route("/download/<path:filename>")  # 바운딩 박스 이미지를 받는 url입니다. 안되면 알려주세요!
def download_file(filename):
    file_path = safe_join(app.config["UPLOAD_FOLDER"],  filename)
    mime_type, _ = mimetypes.guess_type(file_path)
    return send_file(file_path, mimetype=mime_type)


@app.route("/findfoodlist", methods=["GET"])  # 식재료 넣으면 JSON 받는 코드
def find_food_list():
    ingredients = str(request.args.get("ingredients"))
    print(ingredients)

    with spoonacular.ApiClient(configuration) as api_client:
        api_instance = spoonacular.RecipesApi(api_client)
        limit_license = True
        ranking = 1
        ignore_pantry = False

        try:
            api_response = api_instance.search_recipes_by_ingredients(
                ingredients=ingredients,
                number=10,
                limit_license=limit_license,
                ranking=ranking,
                ignore_pantry=ignore_pantry
            )
            response_dict = [result.to_dict() for result in api_response]
            return jsonify(response_dict)
        except Exception as e:
            print("Exception when calling RecipesApi->search_recipes_by_ingredients: %s\n" % e)
            return jsonify({"error": str(e)}), 500


# 이제 레시피 받는 코드, ID를 받는 걸로 진행해야 할 듯
@app.route("/saverecipe/<ids>", methods=["GET"])
def save_recipe(ids):
    try:
        # API 요청 URL 구성
        api_url = f"https://api.spoonacular.com/recipes/informationBulk?apiKey={API_KEY}&ids={ids}"
        # API 호출
        response = requests.get(api_url)
        # 응답 상태 코드 확인
        if response.status_code == 200:
            # JSON 응답을 딕셔너리로 변환
            data = response.json()
            return jsonify(data)
        else:
            # 오류 처리
            return jsonify({"error": "Failed to fetch data from Spoonacular API"}), response.status_code
    except Exception as e:
        print(f"Exception when calling Spoonacular API: {e}")
        return jsonify({"error": str(e)}), 500


# def clean_none_values(data):
#     if isinstance(data, dict):
#         return {k: clean_none_values(v) for k, v in data.items() if v is not None}
#     elif isinstance(data, list):
#         return [clean_none_values(i) for i in data if i is not None]
#     else:
#         return data


# 받은 레시피는 DB에 저장? 그렇게 하고, 파라미터 하나 더 추가. favorite로 명명하자.
# DB에 저장한 것들을 불러오는 것으로 해서 바로바로 불러오기.


if __name__ == '__main__':
    app.run(host='192.168.45.158', port=5000, debug=True)
