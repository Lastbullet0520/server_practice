from flask import Flask, request, jsonify, render_template
import os
from pymongo import MongoClient
from ultralytics import YOLO
import cv2
import spoonacular
# from spoonacular.rest import ApiException

app = Flask(__name__)
client = MongoClient("localhost", 27017)
db = client.dbintel

configuration = spoonacular.Configuration(
    host="https://api.spoonacular.com"
)
configuration.api_key['apiKeyScheme'] = "4adcee865a5b4cde8580e088bffdd841"

model = YOLO("yolov8n.pt")
# model.train(data="",epochs=50,patience=30,batch=32,imgsz=416)

# 이미지 저장 경로 설정
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


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
                    x, y, w, h = box.xyxy[0]
                    x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)

                    # 바운딩 박스 그리기
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(img, class_name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 1)

            output_filename = os.path.join(app.config['UPLOAD_FOLDER'], 'output_' + file.filename)
            cv2.imwrite(output_filename, img)

            ingredients = ','.join(set(detected_objects))  # 중복 제거 후 콤마로 구분된 문자열로 변환
            print("Detected ingredients:", ingredients)
            # temp_list = []
            # for i in results:
            #     for box in i.boxes:
                    # print(box.xyxy[0])
                    # temp_list.append(box.xyxy[0])
            return ingredients

        except Exception as e:
            print("YOLOv8 Exception in image recognition: %s\n" % e)
            return jsonify({"error": "YOLO error"}), 500

    return jsonify({"error": "undefined error occurs"}), 500


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
# @app.route("/saverecipe", methods=["GET"])
# def save_recipe():
#     with spoonacular.ApiClient(configuration) as api_client:
#         # Create an instance of the API class
#         api_instance = spoonacular.RecipesApi(api_client)
#         ids = "715538,"+"716429"  # str | A comma-separated list of recipe ids.
#         include_nutrition = True
#
#         try:
#             # Get Recipe Information Bulk
#             api_response = api_instance.get_recipe_information_bulk(ids=str(ids), include_nutrition=bool(include_nutrition))
#             print(f"The response of RecipesApi->get_recipe_information_bulk:\n{api_response}")
#             return jsonify(api_response)
#         except Exception as e:
#             print("Exception when calling RecipesApi->get_recipe_information_bulk: %s\n" % e)
#             return jsonify({"error": str(e)}), 500


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
